"""Deterministic fact-grounding golden tests (no LLM, no network)."""

from __future__ import annotations

from datetime import datetime, timezone

from hoya_agent.evidence.grounding import (
    GroundingStatus,
    ground_drafts,
    ground_fact,
)
from hoya_agent.evidence.types import EvidenceDraft

UTC = timezone.utc


def _draft(fact: str, source: str, *, source_type: str = "news") -> EvidenceDraft:
    return EvidenceDraft(
        asset="BTC",
        source_type=source_type,
        source_name="Example News",
        source_url="https://example.com/a",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 21, tzinfo=UTC),
        query_or_parameters="q=BTC",
        content_reference=source,
        normalized_fact=fact,
        reliability="medium",
        independence_group="example.com",
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
