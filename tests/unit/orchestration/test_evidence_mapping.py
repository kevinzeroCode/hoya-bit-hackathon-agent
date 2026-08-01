"""The Evidence stage seam: pending evidence in, canonical ledger out.

The provisional dataclass bridge this file used to test is gone. Producers now emit
`models.EvidenceDraft` wrapped in `PendingEvidence`, and the processor is the only
place that assigns `reliability`, `independence_group`, `content_hash` and the
`ev_NNN` ids. What still needs pinning is everything that could be lost silently at
that boundary:

- reliability comes from the static class, so a producer cannot state its own;
- `metric_name`/`metric_value` survive in a side index, because `EvidenceItem` has
  `extra="forbid"` and §16.4 needs a threshold that equals a value its evidence
  carries — and they must be **re-keyed** when a merge renumbers ids;
- an unsupported asset or source type is rejected where it is produced, not
  quietly dropped at ledger time;
- research drafts that cannot state a source class are counted as rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.evidence.drafts import PendingEvidence, pending
from hoya_agent.evidence.policies import SourceClass
from hoya_agent.models import AnalysisRequest, Asset, Reliability, RunContext, RunMode, SourceType
from hoya_agent.orchestration.pipeline import _merge_research_drafts, to_contract_ledger

ANALYSIS_AS_OF = datetime(2026, 5, 31, tzinfo=UTC)


def _context(assets: tuple[Asset, ...] = (Asset.BTC,)) -> RunContext:
    request = AnalysisRequest(
        run_id="run_20260531_000000_map1",
        run_mode=RunMode.rehearsal,
        question="BTC 近期市場行為可以由哪些因素解釋？",
        assets=list(assets),
        requested_at=ANALYSIS_AS_OF,
        analysis_as_of=ANALYSIS_AS_OF,
        deadline_seconds=900,
    )

    class Clock:
        def now_utc(self):
            return ANALYSIS_AS_OF

        def monotonic(self):
            return 1000.0

    return build_run_context(request, Clock())


def _market(
    *,
    fact: str = "BTC 近 14 日報酬為 -4.88%（截至 2026-05-31 UTC）",
    asset: str | None = "BTC",
    source_type: str = "market",
    source_class: SourceClass = SourceClass.DETERMINISTIC_CALC,
    metric_name: str | None = "return_14d",
    metric_value: float | None = -0.0488,
) -> PendingEvidence:
    return pending(
        source_class=source_class,
        original_publisher="organizer-public-market-data",
        asset=asset,
        source_type=source_type,
        source_name="public_market_data",
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, 0, 1, tzinfo=UTC),
        query_or_parameters="metric=return_14d; window=14",
        content_reference="14-bar return over 2026-05-17..2026-05-31",
        normalized_fact=fact,
        metric_name=metric_name,
        metric_value=metric_value,
    )


def test_mapping_produces_a_schema_valid_contract_ledger() -> None:
    mapped = to_contract_ledger([_market()], context=_context())

    assert mapped.ledger.run_id == "run_20260531_000000_map1"
    assert mapped.ledger.analysis_as_of == ANALYSIS_AS_OF
    assert mapped.ledger.run_mode is RunMode.rehearsal
    item = mapped.ledger.items[0]
    assert item.evidence_id == "ev_001"
    assert item.asset is Asset.BTC
    assert item.source_type is SourceType.market
    assert item.reliability is Reliability.high  # from the static class, not the producer
    assert len(item.content_hash) == 64


def test_reliability_is_assigned_by_policy_not_by_the_producer() -> None:
    """A draft has no reliability field at all — that is the point of the split."""
    draft = _market().draft
    assert "reliability" not in type(draft).model_fields
    assert "independence_group" not in type(draft).model_fields

    aggregator = to_contract_ledger(
        [_market(source_class=SourceClass.NEWS_AGGREGATOR, source_type="news")],
        context=_context(),
    )
    assert aggregator.ledger.items[0].reliability is Reliability.low


def test_metric_values_are_preserved_in_the_side_index() -> None:
    mapped = to_contract_ledger([_market()], context=_context())

    assert mapped.metric_index["ev_001"].metric_name == "return_14d"
    assert mapped.metric_index["ev_001"].metric_value == pytest.approx(-0.0488)
    # The canonical model must not have grown the field behind the contract's back.
    assert "metric_value" not in type(mapped.ledger.items[0]).model_fields


def test_market_wide_evidence_keeps_a_null_asset() -> None:
    mapped = to_contract_ledger(
        [_market(asset=None, source_type="macro", source_class=SourceClass.SECONDARY_COMMENTARY)],
        context=_context(),
    )
    assert mapped.ledger.items[0].asset is None


def test_duplicate_facts_collapse_and_are_disclosed() -> None:
    mapped = to_contract_ledger([_market(), _market()], context=_context())

    assert len(mapped.ledger.items) == 1
    assert any("去重" in event.message for event in mapped.ledger.degradation_events)


def test_worker_degradation_messages_become_degradation_events() -> None:
    mapped = to_contract_ledger(
        [_market()],
        context=_context(),
        degradation_messages=["realized_vol_30d unavailable: not enough bars"],
    )

    assert any("realized_vol_30d" in event.message for event in mapped.ledger.degradation_events)
    assert all(event.timestamp.tzinfo is not None for event in mapped.ledger.degradation_events)


def test_unsupported_source_type_is_rejected_where_it_is_produced() -> None:
    """Previously this failed silently at ledger time; now it cannot be built."""
    with pytest.raises(ValueError):
        _market(source_type="rumour")


def test_unsupported_asset_is_rejected_where_it_is_produced() -> None:
    with pytest.raises(ValueError):
        _market(asset="DOGE")


def test_empty_ledger_still_validates_because_it_carries_a_reason() -> None:
    mapped = to_contract_ledger([], context=_context())

    # models.EvidenceLedger rejects an empty ledger with no degradation events.
    assert mapped.ledger.items == []
    assert mapped.ledger.degradation_events


def test_items_stay_sorted_by_evidence_id() -> None:
    drafts = [_market(fact=f"BTC 事實 {n}") for n in range(3)]
    mapped = to_contract_ledger(drafts, context=_context())

    ids = [item.evidence_id for item in mapped.ledger.items]
    assert ids == sorted(ids)


def _research(fact: str) -> PendingEvidence:
    return pending(
        source_class=SourceClass.OFFICIAL_ANNOUNCEMENT,
        original_publisher="bitcoin.org",
        asset="BTC",
        source_type="official",
        source_name="official_project_feed",
        source_url="https://blog.bitcoin.org/post",
        published_at=datetime(2026, 5, 30, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
        query_or_parameters="official feed=https://blog.bitcoin.org/feed.xml",
        content_reference="官方公告（2026-05-30）",
        normalized_fact=fact,
    )


def test_research_merge_folds_evidence_into_one_ledger() -> None:
    context = _context()
    initial = to_contract_ledger([_market()], context=context)

    merged, rejected = _merge_research_drafts(
        context, initial.ledger, [_research("官方公告說明升級時程。")],
        metric_index=initial.metric_index,
    )

    assert rejected == 0
    facts = [item.normalized_fact for item in merged.items]
    assert "官方公告說明升級時程。" in facts
    assert any("報酬" in fact for fact in facts), "market evidence must survive the merge"
    # Ids stay contiguous across the merged set.
    assert [item.evidence_id for item in merged.items] == ["ev_001", "ev_002"]


def test_metric_index_is_rekeyed_when_a_merge_renumbers_ids() -> None:
    """A metric keyed to a stale id would point at the wrong evidence."""
    context = _context()
    initial = to_contract_ledger([_market()], context=context)

    merged, _ = _merge_research_drafts(
        context, initial.ledger, [_research("官方公告 A。"), _research("官方公告 B。")],
        metric_index=initial.metric_index,
    )

    market_item = next(item for item in merged.items if item.source_type is SourceType.market)
    # The market fact may now hold a different id; the metric must follow the hash.
    from hoya_agent.evidence.processor import build_ledger

    rebuilt = build_ledger(
        [],
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        existing=merged.items,
        existing_metrics={market_item.evidence_id: initial.metric_index["ev_001"]},
    )
    followed = rebuilt.metric_index[
        next(i.evidence_id for i in rebuilt.ledger.items if i.content_hash == market_item.content_hash)
    ]
    assert followed.metric_name == "return_14d"


def test_a_draft_without_a_source_class_is_rejected_and_counted() -> None:
    context = _context()
    initial = to_contract_ledger([_market()], context=context)
    # A bare namespace cannot state its source class, so its reliability cannot be
    # decided for it — it is disclosed as rejected rather than admitted.
    raw = SimpleNamespace(
        asset=Asset.BTC,
        source_type=SourceType.news,
        source_name="unknown",
        normalized_fact="無來源類別的主張。",
    )

    merged, rejected = _merge_research_drafts(context, initial.ledger, [raw])

    assert rejected == 1
    assert all("無來源類別" not in item.normalized_fact for item in merged.items)


def test_merge_preserves_earlier_degradation_events() -> None:
    context = _context()
    initial = to_contract_ledger(
        [_market()], context=context, degradation_messages=["volume_zscore_30d unavailable"]
    )

    merged, _ = _merge_research_drafts(context, initial.ledger, [_research("官方公告。")])

    assert any("volume_zscore_30d" in event.message for event in merged.degradation_events)
