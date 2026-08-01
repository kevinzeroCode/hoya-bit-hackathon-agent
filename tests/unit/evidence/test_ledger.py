"""Tests for evidence/ledger.py — conflict detection, query API, Arbiter selection."""

from __future__ import annotations

from datetime import datetime, timezone

from hoya_agent.evidence.ledger import (
    confidence_signals_for_claim,
    detect_material_conflict,
    distinct_independence_groups,
    distinct_source_types,
    filter_by_asset,
    filter_by_source_type,
    has_first_hand_source,
    select_for_arbiter,
    select_for_arbiter_dual,
    source_coverage_gaps,
)
from hoya_agent.evidence.policies import max_confidence
from hoya_agent.evidence.processor import build_ledger
from hoya_agent.evidence.types import EvidenceDraft, EvidenceLedger

UTC = timezone.utc


def _draft(
    fact: str,
    *,
    asset: str | None = "BTC",
    reliability: str = "low",
    source_type: str = "news",
    source_name: str = "CoinDesk",
    group: str = "coindesk.com",
    published: datetime | None = None,
    is_stale: bool = False,
) -> EvidenceDraft:
    return EvidenceDraft(
        asset=asset,
        source_type=source_type,
        source_name=source_name,
        source_url="https://example.com/x",
        published_at=published or datetime(2026, 5, 30, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
        query_or_parameters="params",
        content_reference="ref",
        normalized_fact=fact,
        reliability=reliability,
        independence_group=group,
        is_stale=is_stale,
    )


def _build(*drafts: EvidenceDraft) -> EvidenceLedger:
    return build_ledger(list(drafts))


# ---------------------------------------------------------------------------
# Filter API tests
# ---------------------------------------------------------------------------


class TestFilterByAsset:
    def test_filters_matching_asset(self):
        ledger = _build(
            _draft("btc fact", asset="BTC"),
            _draft("eth fact", asset="ETH"),
            _draft("another btc", asset="BTC"),
        )
        result = filter_by_asset(ledger, "BTC")
        assert len(result) == 2
        assert all(i.asset == "BTC" for i in result)

    def test_case_insensitive(self):
        ledger = _build(_draft("btc fact", asset="BTC"))
        assert len(filter_by_asset(ledger, "btc")) == 1

    def test_excludes_none_asset(self):
        ledger = _build(
            _draft("market-wide", asset=None),
            _draft("btc fact", asset="BTC"),
        )
        result = filter_by_asset(ledger, "BTC")
        assert len(result) == 1


class TestFilterBySourceType:
    def test_filters_matching_source_type(self):
        ledger = _build(
            _draft("market", source_type="market", reliability="high", group="binance.com"),
            _draft("news", source_type="news"),
            _draft("social", source_type="social", group="reddit.com"),
        )
        result = filter_by_source_type(ledger, "news")
        assert len(result) == 1
        assert result[0].source_type == "news"


class TestDistinctSets:
    def test_distinct_source_types(self):
        ledger = _build(
            _draft("a", source_type="market", reliability="high", group="binance.com"),
            _draft("b", source_type="news"),
            _draft("c", source_type="news", source_name="Block", group="theblock.co"),
        )
        types = distinct_source_types(ledger)
        assert types == {"market", "news"}

    def test_distinct_independence_groups(self):
        ledger = _build(
            _draft("a", group="binance.com", reliability="high", source_type="market"),
            _draft("b", group="coindesk.com"),
            _draft("c", group="coindesk.com", source_name="CD2"),
        )
        groups = distinct_independence_groups(ledger)
        assert groups == {"binance.com", "coindesk.com"}


class TestHasFirstHandSource:
    def test_true_with_high_reliability(self):
        ledger = _build(
            _draft("high", reliability="high", source_type="market", group="binance.com"),
            _draft("low", reliability="low"),
        )
        assert has_first_hand_source(ledger) is True

    def test_false_without_high_reliability(self):
        ledger = _build(
            _draft("med", reliability="medium"),
            _draft("low", reliability="low", group="alt.me"),
        )
        assert has_first_hand_source(ledger) is False


class TestSourceCoverageGaps:
    def test_no_gaps_when_targets_met(self):
        ledger = _build(
            _draft("m", reliability="high", source_type="market", group="binance.com"),
            _draft("n", source_type="news", group="coindesk.com"),
            _draft("s", source_type="social", group="alternative.me"),
        )
        assert source_coverage_gaps(ledger) == []

    def test_reports_missing_source_type_diversity(self):
        ledger = _build(
            _draft("m", reliability="high", source_type="market", group="binance.com"),
            _draft("n", source_type="market", reliability="high", group="organizer"),
        )
        gaps = source_coverage_gaps(ledger)
        assert any("來源類型" in g for g in gaps)

    def test_reports_missing_independence_groups(self):
        ledger = _build(
            _draft("a", reliability="high", source_type="market", group="binance.com"),
            _draft("b", source_type="news", group="binance.com"),
            _draft("c", source_type="social", group="binance.com"),
        )
        gaps = source_coverage_gaps(ledger)
        assert any("獨立來源" in g for g in gaps)

    def test_reports_missing_first_hand(self):
        ledger = _build(
            _draft("a", source_type="market", group="a.com"),
            _draft("b", source_type="news", group="b.com"),
            _draft("c", source_type="social", group="c.com"),
        )
        gaps = source_coverage_gaps(ledger)
        assert any("第一手" in g for g in gaps)


# ---------------------------------------------------------------------------
# Material Conflict Detection tests
# ---------------------------------------------------------------------------


class TestDetectMaterialConflict:
    def test_no_conflict_without_opposing(self):
        ledger = _build(
            _draft("sup1", reliability="high", source_type="market", group="binance.com"),
            _draft("sup2", reliability="medium", group="coindesk.com"),
        )
        result = detect_material_conflict(
            "cl_001",
            supporting_evidence_ids=["ev_001", "ev_002"],
            opposing_evidence_ids=[],
            ledger=ledger,
        )
        assert result.is_material is False

    def test_material_conflict_both_sides_different_groups(self):
        ledger = _build(
            _draft("sup", reliability="high", source_type="market", group="binance.com"),
            _draft("opp", reliability="medium", group="coindesk.com"),
        )
        result = detect_material_conflict(
            "cl_001",
            supporting_evidence_ids=["ev_001"],
            opposing_evidence_ids=["ev_002"],
            ledger=ledger,
        )
        assert result.is_material is True
        assert result.claim_id == "cl_001"
        assert "ev_001" in result.supporting_ids
        assert "ev_002" in result.opposing_ids

    def test_no_conflict_same_independence_group(self):
        ledger = _build(
            _draft("sup", reliability="high", source_type="market", group="binance.com"),
            _draft("opp", reliability="medium", group="binance.com",
                   source_name="Binance News"),
        )
        result = detect_material_conflict(
            "cl_001",
            supporting_evidence_ids=["ev_001"],
            opposing_evidence_ids=["ev_002"],
            ledger=ledger,
        )
        assert result.is_material is False

    def test_no_conflict_low_reliability_opposing(self):
        ledger = _build(
            _draft("sup", reliability="high", source_type="market", group="binance.com"),
            _draft("opp", reliability="low", group="reddit.com"),
        )
        result = detect_material_conflict(
            "cl_001",
            supporting_evidence_ids=["ev_001"],
            opposing_evidence_ids=["ev_002"],
            ledger=ledger,
        )
        assert result.is_material is False

    def test_nonexistent_evidence_ids_ignored(self):
        ledger = _build(
            _draft("sup", reliability="high", source_type="market", group="binance.com"),
        )
        result = detect_material_conflict(
            "cl_001",
            supporting_evidence_ids=["ev_001"],
            opposing_evidence_ids=["ev_999"],  # doesn't exist
            ledger=ledger,
        )
        assert result.is_material is False


# ---------------------------------------------------------------------------
# Confidence Signals tests
# ---------------------------------------------------------------------------


class TestConfidenceSignals:
    def test_two_independent_groups_high_reliability_allows_high(self):
        ledger = _build(
            _draft("a", reliability="high", source_type="market", group="binance.com"),
            _draft("b", reliability="high", source_type="market",
                   source_name="csv", group="organizer"),
        )
        signals = confidence_signals_for_claim(
            supporting_evidence_ids=["ev_001", "ev_002"],
            ledger=ledger,
        )
        assert signals.supporting_groups == 2
        assert signals.max_supporting_reliability == "high"
        assert max_confidence(signals) == "high"

    def test_single_group_caps_medium(self):
        ledger = _build(
            _draft("a", reliability="high", source_type="market", group="binance.com"),
            _draft("b", reliability="high", source_type="market",
                   source_name="endpoint2", group="binance.com"),
        )
        signals = confidence_signals_for_claim(
            supporting_evidence_ids=["ev_001", "ev_002"],
            ledger=ledger,
        )
        assert signals.supporting_groups == 1
        assert max_confidence(signals) == "medium"

    def test_material_conflict_caps_low(self):
        ledger = _build(
            _draft("a", reliability="high", source_type="market", group="binance.com"),
        )
        signals = confidence_signals_for_claim(
            supporting_evidence_ids=["ev_001"],
            ledger=ledger,
            has_material_conflict=True,
        )
        assert max_confidence(signals) == "low"

    def test_only_stale_cache_caps_low(self):
        ledger = _build(
            _draft("a", reliability="high", source_type="market",
                   group="binance.com", is_stale=True),
        )
        signals = confidence_signals_for_claim(
            supporting_evidence_ids=["ev_001"],
            ledger=ledger,
        )
        assert signals.only_stale_cache is True
        assert max_confidence(signals) == "low"

    def test_no_evidence_means_insufficient_data(self):
        ledger = _build(_draft("a", reliability="high", source_type="market", group="x"))
        signals = confidence_signals_for_claim(
            supporting_evidence_ids=[],
            ledger=ledger,
        )
        assert signals.insufficient_data is True
        assert max_confidence(signals) == "low"


# ---------------------------------------------------------------------------
# Arbiter Selection tests
# ---------------------------------------------------------------------------


class TestSelectForArbiter:
    def test_returns_all_when_under_cap(self):
        ledger = _build(
            _draft("a", reliability="high", source_type="market", group="binance.com"),
            _draft("b"),
        )
        result = select_for_arbiter(ledger, max_items=30)
        assert len(result) == 2

    def test_respects_max_items(self):
        drafts = [_draft(f"fact {i}", group=f"g{i}.com") for i in range(10)]
        ledger = build_ledger(drafts)
        result = select_for_arbiter(ledger, max_items=5)
        assert len(result) == 5

    def test_high_reliability_always_included(self):
        drafts = [
            _draft("high1", reliability="high", source_type="market", group="a.com"),
            _draft("high2", reliability="high", source_type="market", group="b.com"),
        ] + [_draft(f"low{i}", group=f"g{i}.com") for i in range(10)]
        ledger = build_ledger(drafts)
        result = select_for_arbiter(ledger, max_items=5)
        high_facts = [i.normalized_fact for i in result if i.reliability == "high"]
        assert len(high_facts) == 2

    def test_diversity_preferred_for_remaining_slots(self):
        drafts = [
            _draft("high", reliability="high", source_type="market", group="binance.com"),
            _draft("low1", group="coindesk.com"),
            _draft("low2", group="coindesk.com", source_name="CD2"),
            _draft("low3", group="theblock.co"),
        ]
        ledger = build_ledger(drafts)
        result = select_for_arbiter(ledger, max_items=3)
        groups = {i.independence_group for i in result}
        # Should prefer diverse groups
        assert len(groups) >= 2


class TestSelectForArbiterDual:
    def test_both_assets_get_representation(self):
        drafts = [
            _draft(f"btc{i}", asset="BTC", reliability="high",
                   source_type="market", group=f"btc{i}.com")
            for i in range(6)
        ] + [
            _draft(f"eth{i}", asset="ETH", reliability="high",
                   source_type="market", group=f"eth{i}.com")
            for i in range(6)
        ]
        ledger = build_ledger(drafts)
        result = select_for_arbiter_dual(ledger, assets=["BTC", "ETH"], max_items=8)
        btc_count = sum(1 for i in result if i.asset == "BTC")
        eth_count = sum(1 for i in result if i.asset == "ETH")
        # Both assets should have items
        assert btc_count >= 1
        assert eth_count >= 1

    def test_market_wide_items_always_included(self):
        drafts = [
            _draft("fng", asset=None, source_type="social", group="alternative.me"),
            _draft("btc1", asset="BTC", reliability="high",
                   source_type="market", group="binance.com"),
            _draft("eth1", asset="ETH", reliability="high",
                   source_type="market", group="eth.com"),
        ]
        ledger = build_ledger(drafts)
        result = select_for_arbiter_dual(ledger, assets=["BTC", "ETH"], max_items=10)
        none_items = [i for i in result if i.asset is None]
        assert len(none_items) == 1

    def test_single_asset_falls_back_to_standard(self):
        drafts = [_draft(f"f{i}", group=f"g{i}.com") for i in range(5)]
        ledger = build_ledger(drafts)
        result = select_for_arbiter_dual(ledger, assets=["BTC"], max_items=3)
        assert len(result) == 3
