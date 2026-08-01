"""Multi-fact research extraction: one article becomes several stanceless facts.

The bounded LLM call proposes facts and a relevance verdict; everything that
carries authority — reliability, independence group, timestamps, provenance — is
completed deterministically here. A fact citing a record that was never fetched
is dropped, not repaired.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.evidence.drafts import pending
from hoya_agent.evidence.policies import SourceClass, reliability_for
from hoya_agent.evidence.processor import build_ledger
from hoya_agent.models import Asset, RawSourceRecord, RunMode, SourceType
from hoya_agent.reasoning.research_extractor import (
    MAX_FACTS_PER_RECORD,
    ExtractedFact,
    ResearchExtraction,
    complete_extracted_drafts,
)

NOW = datetime(2026, 5, 31, tzinfo=UTC)
PUBLISHED = datetime(2026, 5, 30, tzinfo=UTC)


def _record(
    record_id: str = "coindesk-abc123",
    *,
    source_type: SourceType = SourceType.news,
    source_name: str = "CoinDesk",
    source_url: str | None = "https://www.coindesk.com/markets/story",
    content: str = "Spot ETFs recorded outflows of 8% over the week.",
    metadata: dict | None = None,
) -> RawSourceRecord:
    return RawSourceRecord(
        record_id=record_id,
        source_name=source_name,
        source_type=source_type,
        source_url=source_url,
        asset=Asset.BTC,
        published_at=PUBLISHED,
        fetched_at=NOW,
        title="ETF outflows continue",
        content=content,
        query_or_parameters="rss feed=https://www.coindesk.com/arc/outboundfeeds/rss/",
        metadata=metadata or {},
    )


def _fact(text: str, *, record_id: str = "coindesk-abc123", relevant: bool = True) -> ExtractedFact:
    return ExtractedFact(
        record_id=record_id,
        normalized_fact=text,
        relevant=relevant,
        event_type="etf_flow",
        asset=Asset.BTC,
    )


def test_one_record_yields_one_draft_per_extracted_fact() -> None:
    extraction = ResearchExtraction(
        drafts=[
            _fact("現貨 ETF 單週淨流出約 8%。"),
            _fact("同期交易所餘額下降。"),
        ]
    )
    drafts, notes = complete_extracted_drafts(
        extraction.drafts, records=[_record()], fetched_at=NOW
    )

    assert len(drafts) == 2
    assert [d.normalized_fact for d in drafts] == [
        "現貨 ETF 單週淨流出約 8%。",
        "同期交易所餘額下降。",
    ]
    assert notes == []


def test_reliability_and_group_come_from_static_policy_not_the_model() -> None:
    drafts, _ = complete_extracted_drafts(
        [_fact("現貨 ETF 單週淨流出約 8%。")], records=[_record()], fetched_at=NOW
    )

    draft = drafts[0]
    # Feed item only: the original page was not fetched, so the static class keeps
    # it `low`. The draft itself has no reliability field — the processor assigns it.
    assert draft.source_class is SourceClass.NEWS_AGGREGATOR
    assert reliability_for(draft.source_class) == "low"
    # The group itself is the processor's decision; with no named publisher in the
    # record's metadata it falls back to the article URL's registered domain.
    ledger = build_ledger(
        drafts,
        run_id="run_20260531_000000_rx03",
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
    ).ledger
    assert ledger.items[0].independence_group == "coindesk.com"
    assert draft.source_type == "news"
    assert draft.source_name == "CoinDesk"
    assert draft.published_at == PUBLISHED
    assert draft.fetched_at == NOW


def test_official_announcement_keeps_its_high_source_class() -> None:
    record = _record(
        record_id="official-xyz",
        source_type=SourceType.official,
        source_name="Ethereum Foundation Blog",
        source_url="https://blog.ethereum.org/2026/05/30/update",
    )
    drafts, _ = complete_extracted_drafts(
        [_fact("官方公告說明升級時程。", record_id="official-xyz")],
        records=[record],
        fetched_at=NOW,
    )

    assert reliability_for(drafts[0].source_class) == "high"
    ledger = build_ledger(
        drafts,
        run_id="run_20260531_000000_rx02",
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
    ).ledger
    assert ledger.items[0].independence_group == "ethereum.org"


def test_irrelevant_record_is_filtered_and_disclosed() -> None:
    drafts, notes = complete_extracted_drafts(
        [_fact("與該資產無關的產業新聞。", relevant=False)],
        records=[_record()],
        fetched_at=NOW,
    )

    assert drafts == []
    assert any("未達相關性" in note for note in notes)


def test_fact_citing_an_unfetched_record_is_dropped() -> None:
    drafts, notes = complete_extracted_drafts(
        [_fact("捏造的事實。", record_id="never-fetched")],
        records=[_record()],
        fetched_at=NOW,
    )

    assert drafts == []
    assert any("never-fetched" in note for note in notes)


def test_facts_per_record_are_capped() -> None:
    facts = [_fact(f"事實 {i}。") for i in range(MAX_FACTS_PER_RECORD + 2)]
    drafts, notes = complete_extracted_drafts(facts, records=[_record()], fetched_at=NOW)

    assert len(drafts) == MAX_FACTS_PER_RECORD
    assert any("上限" in note for note in notes)


def test_content_reference_quotes_the_source_so_grounding_can_check_it() -> None:
    drafts, _ = complete_extracted_drafts(
        [_fact("現貨 ETF 單週淨流出約 8%。")],
        records=[_record(content="Spot ETFs recorded outflows of 8% over the week.")],
        fetched_at=NOW,
    )

    reference = drafts[0].content_reference
    assert "8%" in reference
    assert "ETF outflows continue" in reference
    assert len(reference) <= 600, "content_reference must stay a bounded quotation"


def test_query_parameters_record_the_prompt_version_and_record_id() -> None:
    drafts, _ = complete_extracted_drafts(
        [_fact("現貨 ETF 單週淨流出約 8%。")], records=[_record()], fetched_at=NOW
    )

    assert "coindesk-abc123" in drafts[0].query_or_parameters
    assert "research-extraction" in drafts[0].query_or_parameters


def test_already_complete_drafts_pass_through_untouched() -> None:
    """Market evidence arrives as `PendingEvidence` and must not be re-derived."""
    complete = pending(
        source_class=SourceClass.DETERMINISTIC_CALC,
        original_publisher="organizer-public-market-data",
        asset="BTC",
        source_type="market",
        source_name="public_market_data",
        published_at=PUBLISHED,
        fetched_at=NOW,
        query_or_parameters="asset=BTC",
        content_reference="close series",
        normalized_fact="BTC 的 14 日報酬為 -4.88%。",
    )
    drafts, notes = complete_extracted_drafts([complete], records=[], fetched_at=NOW)

    assert drafts == [complete]
    assert notes == []


def test_blank_fact_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValueError):
        ExtractedFact(
            record_id="coindesk-abc123",
            normalized_fact="   ",
            relevant=True,
            event_type="etf_flow",
        )


def test_schema_forbids_undeclared_fields() -> None:
    with pytest.raises(ValueError):
        ExtractedFact(
            record_id="coindesk-abc123",
            normalized_fact="事實。",
            relevant=True,
            event_type="etf_flow",
            reliability="high",
        )
