"""Deterministic fact-grounding golden tests (no LLM, no network)."""

from __future__ import annotations

from datetime import datetime, timezone

from hoya_agent.evidence.drafts import PendingEvidence, pending
from hoya_agent.evidence.grounding import (
    GroundingStatus,
    ground_drafts,
    ground_fact,
)
from hoya_agent.evidence.policies import SourceClass

UTC = timezone.utc


def _draft(fact: str, source: str, *, source_type: str = "news") -> PendingEvidence:
    return pending(
        source_class=SourceClass.ORIGINAL_NEWS_PAGE,
        original_publisher="example.com",
        asset="BTC",
        source_type=source_type,
        source_name="Example News",
        source_url="https://example.com/a",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 21, tzinfo=UTC),
        query_or_parameters="q=BTC",
        content_reference=source,
        normalized_fact=fact,
    )


def test_percent_present_is_verified():
    v = ground_fact("BTC 下跌 8%", "Bitcoin fell 8% on Tuesday.")
    assert v.status is GroundingStatus.verified


def test_cross_language_numeric_atom_grounds():
    # English source, Chinese fact — the % atom is language-invariant.
    v = ground_fact("BTC 當日下跌 8%", "Bitcoin tumbled 8% amid ETF outflows.")
    assert v.status is GroundingStatus.verified


def test_rounding_tolerance():
    v = ground_fact("BTC 約下跌 8%", "Bitcoin fell 7.9% on the day.")
    assert v.status is GroundingStatus.verified


def test_fabricated_percentage_is_partial_and_flagged():
    v = ground_fact("BTC 下跌 8%", "Bitcoin fell sharply amid ETF outflows.")
    assert v.status is GroundingStatus.partial
    assert "8%" in v.unverified_atoms


def test_precise_date_not_in_source_is_flagged():
    v = ground_fact("BTC 於 2026-05-20 下跌 8%", "Bitcoin fell 8% on Tuesday.")
    assert v.status is GroundingStatus.partial
    assert "2026-05-20" in v.unverified_atoms


def test_iso_date_present_is_verified():
    v = ground_fact("2026-05-20 BTC 下跌", "On 2026-05-20 Bitcoin declined.")
    assert v.status is GroundingStatus.verified


def test_money_amount_grounds():
    v = ground_fact("ETF 流出 $200", "The ETF saw net redemptions of $200 million.")
    assert v.status is GroundingStatus.verified


def test_purely_qualitative_is_unverified_pending_semantic_check():
    v = ground_fact("市場情緒轉為謹慎", "Sentiment turned cautious across the market.")
    assert v.status is GroundingStatus.unverified
    assert v.unverified_atoms == ()


def test_require_grounding_excludes_ungrounded_support_from_confidence():
    from hoya_agent.evidence.ledger import confidence_signals_for_claim
    from hoya_agent.models import EvidenceItem, EvidenceLedger, RunMode

    def _item(eid, fact, source, group):
        return EvidenceItem(
            evidence_id=eid, content_hash=eid.encode().hex().ljust(64, "0"), asset="BTC",
            source_type="news",
            source_name=f"src-{eid}", source_url="https://x/y",
            published_at=datetime(2026, 5, 20, tzinfo=UTC),
            fetched_at=datetime(2026, 5, 21, tzinfo=UTC), query_or_parameters="q",
            content_reference=source, normalized_fact=fact,
            reliability="medium", independence_group=group,
        )

    grounded = _item("ev_001", "BTC 下跌 8%", "Bitcoin fell 8%.", "coindesk.com")
    ungrounded = _item("ev_002", "BTC 下跌 8%", "Bitcoin fell sharply.", "theblock.co")  # 8% fabricated
    ledger = EvidenceLedger(
        run_id="run_20260531_000000_grd1",
        analysis_as_of=datetime(2026, 5, 31, tzinfo=UTC),
        run_mode=RunMode.rehearsal,
        items=[grounded, ungrounded],
    )
    ids = ["ev_001", "ev_002"]

    # Without grounding: two independent groups -> could reach high.
    assert confidence_signals_for_claim(supporting_evidence_ids=ids, ledger=ledger).supporting_groups == 2
    # With grounding: the fabricated-value item drops out -> only one group.
    gated = confidence_signals_for_claim(
        supporting_evidence_ids=ids, ledger=ledger, require_grounding=True
    )
    assert gated.supporting_groups == 1


def test_semantic_status_rescues_a_purely_qualitative_fact_but_never_a_fabricated_number():
    """Task 16 / G1: a purely-qualitative fact (no hard atom, `unverified`) can be
    rescued by a `"verified"` semantic recheck; a numerically-fabricated fact
    (`partial`) is never rescued by one, regardless of what it says."""
    from hoya_agent.evidence.ledger import confidence_signals_for_claim
    from hoya_agent.models import EvidenceItem, EvidenceLedger, RunMode

    def _item(eid, fact, source, group):
        return EvidenceItem(
            evidence_id=eid, content_hash=eid.encode().hex().ljust(64, "0"), asset="BTC",
            source_type="news",
            source_name=f"src-{eid}", source_url="https://x/y",
            published_at=datetime(2026, 5, 20, tzinfo=UTC),
            fetched_at=datetime(2026, 5, 21, tzinfo=UTC), query_or_parameters="q",
            content_reference=source, normalized_fact=fact,
            reliability="medium", independence_group=group,
        )

    qualitative = _item("ev_001", "市場情緒轉為謹慎", "Sentiment turned cautious.", "coindesk.com")
    fabricated_number = _item("ev_002", "BTC 下跌 8%", "Bitcoin fell sharply.", "theblock.co")
    ledger = EvidenceLedger(
        run_id="run_20260531_000000_sem1",
        analysis_as_of=datetime(2026, 5, 31, tzinfo=UTC),
        run_mode=RunMode.rehearsal,
        items=[qualitative, fabricated_number],
    )
    ids = ["ev_001", "ev_002"]

    # No semantic_status supplied: exact prior behavior, both drop out.
    assert confidence_signals_for_claim(
        supporting_evidence_ids=ids, ledger=ledger, require_grounding=True
    ).supporting_groups == 0

    # A "verified" semantic recheck rescues the qualitative fact...
    rescued = confidence_signals_for_claim(
        supporting_evidence_ids=ids, ledger=ledger, require_grounding=True,
        semantic_status={"ev_001": "verified", "ev_002": "verified"},
    )
    # ...but never the fabricated number, even though its entry also says "verified".
    assert rescued.supporting_groups == 1

    # A "contradicted" semantic verdict does not rescue it either.
    contradicted = confidence_signals_for_claim(
        supporting_evidence_ids=ids, ledger=ledger, require_grounding=True,
        semantic_status={"ev_001": "contradicted"},
    )
    assert contradicted.supporting_groups == 0


def test_ground_drafts_skips_market_and_collects_notes():
    drafts = [
        _draft("BTC 收盤 73674.39", "deterministic bar", source_type="market"),
        _draft("BTC 下跌 8%", "Bitcoin fell sharply."),  # fabricated 8% -> partial
        _draft("BTC 下跌 8%", "Bitcoin fell 8%."),        # grounded
    ]
    results, notes = ground_drafts(drafts)
    statuses = [v.status for _, v in results]
    assert statuses[0] is GroundingStatus.verified   # market skipped -> verified
    assert statuses[1] is GroundingStatus.partial
    assert statuses[2] is GroundingStatus.verified
    assert len(notes) == 1 and "8%" in notes[0]
