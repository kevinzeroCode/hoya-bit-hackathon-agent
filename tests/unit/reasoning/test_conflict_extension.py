"""Unit tests for the disabled H3 conditional-debate seam."""

from __future__ import annotations

import asyncio
import unittest

from _stubs import Indicator, Ledger, Request

from hoya_agent.reasoning.conflict_extension import (
    ARBITER_ROUTE,
    DISABLED_STATUS,
    UNIMPLEMENTED_LABEL,
    ConflictExtensionResult,
    DisabledConflictExtension,
)


def evaluate(indicators=(), context=None):
    return asyncio.run(
        DisabledConflictExtension().evaluate(
            ledger=Ledger(items=[]), indicators=list(indicators), context=context
        )
    )


class DisabledExtensionTests(unittest.TestCase):
    def test_always_reports_disabled(self):
        result = evaluate()
        self.assertEqual(result.status, DISABLED_STATUS)
        self.assertTrue(result.is_disabled)

    def test_always_routes_to_the_arbiter(self):
        self.assertEqual(evaluate().route, ARBITER_ROUTE)

    def test_indicators_pass_through_untouched(self):
        indicators = [Indicator(claim_id="cl_001", supporting_evidence_ids=["ev_001"])]
        result = evaluate(indicators)
        self.assertEqual(len(result.indicators), 1)
        self.assertEqual(result.indicators[0].claim_id, "cl_001")

    def test_requesting_the_debate_is_recorded_as_ignored(self):
        result = evaluate(context=Request(enable_conditional_debate=True))
        joined = " ".join(result.notes)
        self.assertIn("ignored", joined)
        self.assertEqual(result.route, ARBITER_ROUTE, "the flag must not change routing")

    def test_not_requesting_the_debate_adds_no_ignored_note(self):
        result = evaluate(context=Request(enable_conditional_debate=False))
        self.assertNotIn("ignored", " ".join(result.notes))

    def test_unimplemented_label_is_always_present(self):
        self.assertIn(UNIMPLEMENTED_LABEL, evaluate().notes)

    def test_result_is_immutable(self):
        result = evaluate()
        with self.assertRaises(Exception):
            result.status = "enabled"  # type: ignore[misc]

    def test_no_debate_participant_exists_in_the_module(self):
        import hoya_agent.reasoning.conflict_extension as module

        source = module.__doc__ or ""
        names = dir(module)
        for banned in ("Bull", "Bear", "Judge"):
            self.assertNotIn(
                banned, names, f"{banned} must not exist while H3 is unimplemented"
            )
        self.assertIn("never debates", source)

    def test_result_dataclass_exposes_the_expected_shape(self):
        result = ConflictExtensionResult(
            status=DISABLED_STATUS, route=ARBITER_ROUTE, indicators=()
        )
        self.assertTrue(result.is_disabled)
        self.assertEqual(result.notes, ())


if __name__ == "__main__":
    unittest.main()
