"""Unit tests for the provisional-dataclass -> canonical-contract ledger mapping.

`src/hoya_agent/evidence/types.py` (the data/evidence layer's frozen dataclasses)
and `src/hoya_agent/models.py` (the canonical Pydantic contracts) coexist on
`main`. This mapping is the seam between them, and it must lose nothing silently:

- `metric_name` / `metric_value` exist on the dataclass but not on
  `models.EvidenceItem` (16 fields, `extra="forbid"`), so they are preserved in a
  side index rather than dropped — `evidence-contracts.md` §16.4 requires a
  quantified invalidation threshold to equal a value carried by its evidence.
- anything that cannot be mapped is disclosed as a degradation event, never
  dropped quietly.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.evidence.types import EvidenceItem as WorkerItem
from hoya_agent.evidence.types import EvidenceLedger as WorkerLedger
from hoya_agent.models import AnalysisRequest, Asset, Reliability, RunContext, RunMode, SourceType
from hoya_agent.orchestration.pipeline import to_contract_ledger

ANALYSIS_AS_OF = datetime(2026, 5, 31, tzinfo=UTC)


def _context(assets: tuple[Asset, ...] = (Asset.BTC,)) -> RunContext:
    return RunContext(
        run_id="run_20260531_000000_map1",
        request=AnalysisRequest(
            run_id="run_20260531_000000_map1",
            question="BTC 近期市場行為可以由哪些因素解釋？",
            assets=list(assets),
            requested_at=ANALYSIS_AS_OF,
            analysis_as_of=ANALYSIS_AS_OF,
            deadline_seconds=900,
            run_mode=RunMode.rehearsal,
        ),
        analysis_as_of=ANALYSIS_AS_OF,
        started_at=ANALYSIS_AS_OF,
        started_monotonic=0.0,
        deadline_monotonic=900.0,
    )


def _worker_item(
    *,
    evidence_id: str = "ev_001",
    asset: str | None = "BTC",
    source_type: str = "market",
    reliability: str = "high",
    metric_name: str | None = "return_14d",
    metric_value: float | None = -0.0488,
) -> WorkerItem:
    return WorkerItem(
        evidence_id=evidence_id,
        content_hash="a" * 64,
        asset=asset,
        source_type=source_type,
        source_name="public_market_data",
        source_url=None,
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, 0, 1, tzinfo=UTC),
        query_or_parameters="metric=return_14d; window=14",
        content_reference="14-bar return over 2026-05-17..2026-05-31",
        normalized_fact="BTC 近 14 日報酬為 -4.88%（截至 2026-05-31 UTC）",
        reliability=reliability,
        independence_group="organizer-public-market-data",
        metric_name=metric_name,
        metric_value=metric_value,
    )


def test_mapping_produces_a_schema_valid_contract_ledger() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(items=[_worker_item()], dropped_duplicates=0), context=_context()
    )

    assert mapped.ledger.run_id == "run_20260531_000000_map1"
    assert mapped.ledger.analysis_as_of == ANALYSIS_AS_OF
    assert mapped.ledger.run_mode is RunMode.rehearsal
    item = mapped.ledger.items[0]
    assert item.evidence_id == "ev_001"
    assert item.asset is Asset.BTC
    assert item.source_type is SourceType.market
    assert item.reliability is Reliability.high
    assert item.content_hash == "a" * 64


def test_metric_values_are_preserved_in_the_side_index() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(items=[_worker_item()], dropped_duplicates=0), context=_context()
    )
    assert mapped.metric_index["ev_001"].metric_name == "return_14d"
    assert mapped.metric_index["ev_001"].metric_value == pytest.approx(-0.0488)
    # The canonical model must not have grown the field behind the contract's back.
    assert "metric_value" not in type(mapped.ledger.items[0]).model_fields


def test_market_wide_evidence_keeps_a_null_asset() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(items=[_worker_item(asset=None, source_type="macro", reliability="low")], dropped_duplicates=0),
        context=_context(),
    )
    assert mapped.ledger.items[0].asset is None


def test_dropped_duplicates_are_disclosed_as_a_degradation_event() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(items=[_worker_item()], dropped_duplicates=3), context=_context()
    )
    messages = [event.message for event in mapped.ledger.degradation_events]
    assert any("3" in message for message in messages)


def test_worker_degradation_messages_become_degradation_events() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(items=[_worker_item()], dropped_duplicates=0),
        context=_context(),
        degradation_messages=["realized_vol_30d unavailable: not enough bars"],
    )
    assert any(
        "realized_vol_30d" in event.message for event in mapped.ledger.degradation_events
    )
    assert all(event.timestamp.tzinfo is not None for event in mapped.ledger.degradation_events)


def test_unmappable_enum_values_are_disclosed_not_silently_kept() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(
            items=[_worker_item(), _worker_item(evidence_id="ev_002", source_type="rumour")],
            dropped_duplicates=0,
        ),
        context=_context(),
    )
    assert [item.evidence_id for item in mapped.ledger.items] == ["ev_001"]
    assert "ev_002" in mapped.unmapped
    assert any("ev_002" in event.message for event in mapped.ledger.degradation_events)


def test_unsupported_asset_is_disclosed_not_silently_kept() -> None:
    mapped = to_contract_ledger(
        WorkerLedger(items=[_worker_item(asset="DOGE")], dropped_duplicates=0),
        context=_context(),
    )
    assert mapped.ledger.items == []
    assert "ev_001" in mapped.unmapped


def test_empty_ledger_still_validates_because_it_carries_a_reason() -> None:
    mapped = to_contract_ledger(WorkerLedger(items=[], dropped_duplicates=0), context=_context())
    # models.EvidenceLedger rejects an empty ledger with no degradation events.
    assert mapped.ledger.items == []
    assert mapped.ledger.degradation_events


def test_items_stay_sorted_by_evidence_id() -> None:
    items = [_worker_item(evidence_id=f"ev_{n:03d}") for n in (3, 1, 2)]
    mapped = to_contract_ledger(WorkerLedger(items=items, dropped_duplicates=0), context=_context())
    ids = [item.evidence_id for item in mapped.ledger.items]
    assert ids == sorted(ids)
