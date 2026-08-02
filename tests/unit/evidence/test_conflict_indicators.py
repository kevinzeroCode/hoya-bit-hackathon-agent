"""Deterministic ConflictIndicator generation (evidence-contracts §9).

A material conflict exists exactly when a claim carries both a `supports` and an
`opposes` link, both sides hold reliability `high`/`medium`, and at least one
supporting/opposing pair comes from different `independence_group` values. The
indicator is produced by deterministic code over the ledger and the links — no
LLM, and H3 never has to execute for the conflict to be preserved.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hoya_agent.evidence.ledger import CONFLICT_RULE_VERSION, build_conflict_indicators
from hoya_agent.models import (
    Asset,
    ClaimEvidenceLink,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunMode,
    SourceType,
    Stance,
)

NOW = datetime(2026, 5, 31, tzinfo=UTC)


def _item(
    evidence_id: str,
    *,
    reliability: Reliability,
    group: str,
    source_type: SourceType = SourceType.news,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        asset=Asset.BTC,
        source_type=source_type,
        source_name=f"source-{evidence_id}",
        source_url=f"https://example.test/{evidence_id}",
        published_at=NOW,
        fetched_at=NOW,
        query_or_parameters=f"id={evidence_id}",
        content_reference=f"quote {evidence_id}",
        normalized_fact=f"fact {evidence_id}",
        reliability=reliability,
        independence_group=group,
        content_hash=evidence_id.encode().hex().ljust(64, "0"),
    )


def _ledger(*items: EvidenceItem) -> EvidenceLedger:
    return EvidenceLedger(
        run_id="run_20260531_000000_cf01",
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
        items=sorted(items, key=lambda item: item.evidence_id),
    )


def _link(claim_id: str, evidence_id: str, stance: Stance) -> ClaimEvidenceLink:
    return ClaimEvidenceLink(
        claim_id=claim_id,
        evidence_id=evidence_id,
        stance=stance,
        reason="fixture link",
    )


def test_opposing_sides_from_different_groups_are_material() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_003", "ev_001", Stance.supports),
            _link("cl_003", "ev_002", Stance.opposes),
        ],
        ledger=ledger,
    )

    assert len(indicators) == 1
    indicator = indicators[0]
    assert indicator.claim_id == "cl_003"
    assert indicator.supporting_evidence_ids == ["ev_001"]
    assert indicator.opposing_evidence_ids == ["ev_002"]
    assert indicator.independence_groups == ["coindesk.com", "organizer-public-market-data"]
    assert indicator.rule_version == CONFLICT_RULE_VERSION


def test_low_reliability_opposition_is_not_material() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _item("ev_002", reliability=Reliability.low, group="cryptopanic.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_002", Stance.opposes),
        ],
        ledger=ledger,
    )
    assert indicators == []


def test_same_independence_group_on_both_sides_is_not_material() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.medium, group="coindesk.com"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_002", Stance.opposes),
        ],
        ledger=ledger,
    )
    assert indicators == []


def test_identical_group_sets_with_two_groups_are_material() -> None:
    """§9 條件三看的是「存在跨群組的支持/反對配對」，不是兩側群組集合不同。

    supports 與 opposes 各自橫跨 {binance.com, coindesk.com} 時，
    (binance 支持, coindesk 反對) 就是一組跨群組配對，必須判為 material。
    """
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="binance.com"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
        _item("ev_003", reliability=Reliability.medium, group="binance.com"),
        _item("ev_004", reliability=Reliability.medium, group="coindesk.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_004", Stance.supports),
            _link("cl_001", "ev_002", Stance.opposes),
            _link("cl_001", "ev_003", Stance.opposes),
        ],
        ledger=ledger,
    )

    assert len(indicators) == 1
    assert indicators[0].claim_id == "cl_001"
    assert indicators[0].supporting_evidence_ids == ["ev_001", "ev_004"]
    assert indicators[0].opposing_evidence_ids == ["ev_002", "ev_003"]


def test_support_only_claim_has_no_indicator() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_002", Stance.supports),
        ],
        ledger=ledger,
    )
    assert indicators == []


def test_neutral_links_cannot_create_a_conflict() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_002", Stance.neutral),
        ],
        ledger=ledger,
    )
    assert indicators == []


def test_unresolvable_evidence_id_is_ignored_rather_than_assumed() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_099", Stance.opposes),
        ],
        ledger=ledger,
    )
    assert indicators == []


def test_indicators_are_deterministically_ordered_by_claim_id() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
        _item("ev_003", reliability=Reliability.medium, group="decrypt.co"),
    )
    links = [
        _link("cl_004", "ev_002", Stance.supports),
        _link("cl_004", "ev_003", Stance.opposes),
        _link("cl_002", "ev_001", Stance.supports),
        _link("cl_002", "ev_002", Stance.opposes),
    ]
    first = build_conflict_indicators(claim_evidence_links=links, ledger=ledger)
    second = build_conflict_indicators(claim_evidence_links=list(reversed(links)), ledger=ledger)

    assert [indicator.claim_id for indicator in first] == ["cl_002", "cl_004"]
    assert first == second


def test_multiple_opposing_items_are_all_listed_sorted() -> None:
    ledger = _ledger(
        _item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _item("ev_003", reliability=Reliability.medium, group="decrypt.co"),
        _item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
    )
    indicators = build_conflict_indicators(
        claim_evidence_links=[
            _link("cl_001", "ev_001", Stance.supports),
            _link("cl_001", "ev_003", Stance.opposes),
            _link("cl_001", "ev_002", Stance.opposes),
        ],
        ledger=ledger,
    )
    assert indicators[0].opposing_evidence_ids == ["ev_002", "ev_003"]
