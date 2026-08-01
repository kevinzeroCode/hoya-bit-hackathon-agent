"""Tests for the Evidence Processor: merge many sources into one clean ledger."""

from __future__ import annotations

from datetime import datetime, timezone

from hoya_agent.evidence.drafts import PendingEvidence, pending
from hoya_agent.evidence.ledger import (
    distinct_independence_groups,
    distinct_source_types,
    select_for_arbiter,
)
from hoya_agent.evidence.policies import SourceClass
from hoya_agent.evidence.processor import build_ledger as _build_ledger
from hoya_agent.models import EvidenceItem, EvidenceLedger, RunMode

UTC = timezone.utc

_CLASS_FOR_RELIABILITY = {
    "high": SourceClass.DETERMINISTIC_CALC,
    "medium": SourceClass.ORIGINAL_NEWS_PAGE,
    "low": SourceClass.NEWS_AGGREGATOR,
}


def _draft(
    fact: str,
    *,
    reliability: str = "low",
    source_type: str = "news",
    source_name: str = "CoinDesk",
    group: str = "coindesk.com",
    published: datetime | None = None,
) -> PendingEvidence:
    return pending(
        # A producer names its static source class; the processor decides reliability.
        source_class=_CLASS_FOR_RELIABILITY[reliability],
        original_publisher=group,
        asset="BTC",
        source_type=source_type,
        source_name=source_name,
        source_url="https://example.com/x",
        published_at=published or datetime(2026, 5, 30, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
        query_or_parameters="params",
        content_reference="ref",
        normalized_fact=fact,
    )


def build_ledger(drafts) -> EvidenceLedger:
    """Test seam: the processor needs the run identity the pipeline supplies."""
    return _build_ledger(
        list(drafts),
        run_id="run_20260531_000000_prc1",
        analysis_as_of=datetime(2026, 5, 31, tzinfo=UTC),
        run_mode=RunMode.rehearsal,
    ).ledger


def test_merges_sources_into_one_ledger_with_stable_ids():
    drafts = [
        _draft("News fact A"),
        _draft("BTC 14d return was -4.88%", reliability="high", source_type="market",
               source_name="public_market_data", group="organizer-public-market-data"),
        _draft("News fact B", source_name="The Block", group="theblock.co"),
    ]
    ledger = build_ledger(drafts)
    assert isinstance(ledger, EvidenceLedger)
    assert all(isinstance(i, EvidenceItem) for i in ledger.items)
    assert [i.evidence_id for i in ledger.items] == ["ev_001", "ev_002", "ev_003"]
    # every item carries a 64-hex content hash
    assert all(len(i.content_hash) == 64 for i in ledger.items)


def test_ranks_high_reliability_first():
    drafts = [
        _draft("low fact", reliability="low"),
        _draft("high fact", reliability="high", source_type="market"),
    ]
    ledger = build_ledger(drafts)
    assert ledger.items[0].reliability == "high"
    assert ledger.items[0].evidence_id == "ev_001"


def test_dedup_collapses_identical_facts():
    drafts = [
        _draft("Same headline reposted", source_name="CoinDesk", group="coindesk.com"),
        _draft("Same headline reposted", source_name="Aggregator", group="aggregator.com"),
        _draft("Unique fact"),
    ]
    build = _build_ledger(
        drafts,
        run_id="run_20260531_000000_prc1",
        analysis_as_of=datetime(2026, 5, 31, tzinfo=UTC),
        run_mode=RunMode.rehearsal,
    )
    facts = [i.normalized_fact for i in build.ledger.items]
    assert facts.count("Same headline reposted") == 1
    assert build.dropped_duplicates == 1
    # The collapse is disclosed in the ledger itself, not only in a return value.
    assert any("去重" in event.message for event in build.ledger.degradation_events)


def test_identical_fact_same_hash_regardless_of_whitespace_case():
    a = _draft("Bitcoin ETF Inflows Hit Record")
    b = _draft("  bitcoin etf inflows hit record  ")
    ledger = build_ledger([a, b])
    assert len(ledger.items) == 1  # collapsed by canonicalized hash


def test_source_and_independence_diversity_stats():
    drafts = [
        _draft("m", reliability="high", source_type="market", group="binance.com"),
        _draft("n", source_type="news", group="coindesk.com"),
        _draft("s", source_type="social", group="alternative.me"),
    ]
    ledger = build_ledger(drafts)
    assert len(distinct_source_types(ledger)) == 3      # market / news / social
    assert len(distinct_independence_groups(ledger)) == 3


def test_top_returns_first_n_for_arbiter():
    drafts = [_draft(f"fact {i}") for i in range(5)]
    ledger = build_ledger(drafts)
    assert len(select_for_arbiter(ledger, max_items=2)) == 2
