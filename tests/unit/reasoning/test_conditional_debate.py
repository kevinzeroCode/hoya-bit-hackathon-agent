"""Unit tests for the opt-in H3 conditional debate (Task 17)."""

from __future__ import annotations

import asyncio
import time
import unittest

from _stubs import BoomError, FakeLLM

from hoya_agent.models import Asset, Claim, ClaimType, ConflictIndicator, Reliability, TimeRange
from hoya_agent.reasoning.conditional_debate import (
    ACTIVE_STATUS,
    DEBATE_ROUTE,
    ConditionalDebateExtension,
    DebateArgument,
    DebateVerdict,
)
from hoya_agent.reasoning.conflict_extension import ARBITER_ROUTE, DISABLED_STATUS


def _run(coro):
    return asyncio.run(coro)


def _claim(claim_id="cl_004", claim_type=ClaimType.conclusion, text="BTC 呈現區間整理。") -> Claim:
    return Claim(
        claim_id=claim_id,
        claim_type=claim_type,
        assets=[Asset.BTC],
        time_range=TimeRange(start="2026-05-01", end="2026-05-31"),
        text=text,
        based_on_claim_ids=["cl_003"] if claim_type != ClaimType.fact else [],
        confidence=Reliability.high,
        limitations=[],
        invalidation_conditions=[],
    )


def _indicator(supporting=("ev_001",), opposing=("ev_002",)) -> ConflictIndicator:
    return ConflictIndicator(
        claim_id="cl_004",
        supporting_evidence_ids=list(supporting),
        opposing_evidence_ids=list(opposing),
        independence_groups=["binance.com", "news.example.com"],
    )


class _Item:
    def __init__(self, evidence_id, fact, reliability="medium", group="g"):
        self.evidence_id = evidence_id
        self.normalized_fact = fact
        self.reliability = reliability
        self.independence_group = group


class _Ledger:
    def __init__(self, items):
        self.items = items


def _ledger() -> _Ledger:
    return _Ledger(
        [
            _Item("ev_001", "BTC 過去 14 日報酬 -4.9%。"),
            _Item("ev_002", "BTC 現貨資金淨流入連續五日為正。"),
        ]
    )


class EvaluateTests(unittest.TestCase):
    """`evaluate()` never calls the LLM — every assertion here holds for a
    `FakeLLM([])` (an LLM that raises `AssertionError` if it is ever called)."""

    def test_disabled_when_flag_is_off_even_with_a_real_conflict(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([]))
        context = type("Ctx", (), {"enable_conditional_debate": False})()
        result = _run(ext.evaluate(ledger=_ledger(), indicators=[_indicator()], context=context))
        self.assertEqual(result.status, DISABLED_STATUS)
        self.assertEqual(result.route, ARBITER_ROUTE)

    def test_disabled_when_flag_is_on_but_no_conflict(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([]))
        context = type("Ctx", (), {"enable_conditional_debate": True})()
        result = _run(ext.evaluate(ledger=_ledger(), indicators=[], context=context))
        self.assertEqual(result.status, DISABLED_STATUS)
        self.assertEqual(result.route, ARBITER_ROUTE)
        self.assertTrue(any("ignored" in n or "routed directly" in n for n in result.notes))

    def test_active_when_flag_is_on_and_a_real_conflict_exists(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([]))
        context = type("Ctx", (), {"enable_conditional_debate": True})()
        result = _run(ext.evaluate(ledger=_ledger(), indicators=[_indicator()], context=context))
        self.assertEqual(result.status, ACTIVE_STATUS)
        self.assertEqual(result.route, DEBATE_ROUTE)

    def test_no_context_at_all_behaves_like_flag_off(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([]))
        result = _run(ext.evaluate(ledger=_ledger(), indicators=[_indicator()], context=None))
        self.assertEqual(result.status, DISABLED_STATUS)


class RunDebateTests(unittest.TestCase):
    def test_a_successful_debate_revises_confidence_and_text(self):
        llm = FakeLLM(
            [
                DebateArgument(argument="14 日報酬轉負，支持整理說。", cited_evidence_ids=["ev_001"]),
                DebateArgument(argument="資金淨流入連續為正，與整理說方向相反。", cited_evidence_ids=["ev_002"]),
                DebateVerdict(
                    text="儘管報酬轉負，但資金持續流入，故結論改為信心受限的區間整理。",
                    confidence="low",
                    limitations=["雙方訊號方向相反，殘留不確定性"],
                    confidence_rationale="反方的資金流入訊號直接牴觸正方的報酬轉負論點",
                ),
            ]
        )
        ext = ConditionalDebateExtension(llm=llm)
        outcome = _run(
            ext.run_debate(
                claim=_claim(), indicator=_indicator(), ledger=_ledger(), deadline=time.monotonic() + 30
            )
        )
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.revised_claim.confidence, Reliability.low)
        self.assertIn("資金", outcome.revised_claim.text)
        self.assertIn("雙方訊號方向相反，殘留不確定性", outcome.revised_claim.limitations)
        # Identity/scope fields are never touched by the debate.
        self.assertEqual(outcome.revised_claim.claim_id, "cl_004")
        self.assertEqual(outcome.revised_claim.claim_type, ClaimType.conclusion)
        self.assertEqual(outcome.revised_claim.assets, [Asset.BTC])
        self.assertEqual(outcome.revised_claim.based_on_claim_ids, ["cl_003"])

    def test_non_conclusion_claim_is_skipped_without_calling_the_llm(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([]))
        outcome = _run(
            ext.run_debate(
                claim=_claim(claim_type=ClaimType.fact),
                indicator=_indicator(),
                ledger=_ledger(),
                deadline=time.monotonic() + 30,
            )
        )
        self.assertFalse(outcome.succeeded)

    def test_missing_evidence_in_the_ledger_skips_without_calling_the_llm(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([]))
        outcome = _run(
            ext.run_debate(
                claim=_claim(),
                indicator=_indicator(supporting=("ev_999",)),
                ledger=_ledger(),
                deadline=time.monotonic() + 30,
            )
        )
        self.assertFalse(outcome.succeeded)

    def test_bull_failure_aborts_the_whole_debate(self):
        ext = ConditionalDebateExtension(llm=FakeLLM([BoomError("provider unavailable")]))
        outcome = _run(
            ext.run_debate(
                claim=_claim(), indicator=_indicator(), ledger=_ledger(), deadline=time.monotonic() + 30
            )
        )
        self.assertFalse(outcome.succeeded)

    def test_judge_failure_aborts_and_keeps_the_original_claim(self):
        llm = FakeLLM(
            [
                DebateArgument(argument="正方論述。", cited_evidence_ids=["ev_001"]),
                DebateArgument(argument="反方論述。", cited_evidence_ids=["ev_002"]),
                BoomError("judge timed out"),
            ]
        )
        ext = ConditionalDebateExtension(llm=llm)
        outcome = _run(
            ext.run_debate(
                claim=_claim(), indicator=_indicator(), ledger=_ledger(), deadline=time.monotonic() + 30
            )
        )
        self.assertFalse(outcome.succeeded)

    def test_debate_never_produces_high_confidence(self):
        """The Judge's own schema forbids `high` (Literal["medium", "low"]) —
        this proves that constraint actually rejects a model that tries."""
        with self.assertRaises(Exception):
            DebateVerdict(text="x", confidence="high", confidence_rationale="y")


if __name__ == "__main__":
    unittest.main()
