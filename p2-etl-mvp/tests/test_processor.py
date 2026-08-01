"""Tests for the Evidence Processor: merge many sources into one clean ledger."""

from __future__ import annotations

from datetime import datetime, timezone

from evidence.processor import build_ledger
from evidence.types import EvidenceDraft, EvidenceItem, EvidenceLedger

UTC = timezone.utc


def _draft(
    fact: str,
    *,
    reliability: str = "low",
    source_type: str = "news",
    source_name: str = "CoinDesk",
    group: str = "coindesk.com",
    published: datetime | None = None,
) -> EvidenceDraft:
    return EvidenceDraft(
        asset="BTC",
        source_type=source_type,
        source_name=source_name,
        source_url="https://example.com/x",
        published_at=published or datetime(2026, 5, 30, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
        query_or_parameters="params",
        content_reference="ref",
        normalized_fact=fact,
        reliability=reliability,  # type: ignore[arg-type]
        independence_group=group,
    )


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
    ledger = build_ledger(drafts)
    facts = [i.normalized_fact for i in ledger.items]
    assert facts.count("Same headline reposted") == 1
    assert ledger.dropped_duplicates == 1


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
    assert ledger.source_type_count == 3      # market / news / social
    assert ledger.independence_group_count == 3


def test_top_returns_first_n_for_arbiter():
    drafts = [_draft(f"fact {i}") for i in range(5)]
    ledger = build_ledger(drafts)
    assert len(ledger.top(2)) == 2
