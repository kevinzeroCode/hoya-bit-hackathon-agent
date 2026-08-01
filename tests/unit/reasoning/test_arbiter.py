"""Unit tests for the bounded Arbiter stage."""

from __future__ import annotations

import asyncio
import time
import unittest

from _stubs import (
    BoomError,
    Claim,
    Evidence,
    FakeLLM,
    Indicator,
    Invalidation,
    Ledger,
    Link,
    Request,
    Result,
)

from hoya_agent.reasoning.arbiter import (
    MAX_EVIDENCE_FOR_ARBITER,
    Arbiter,
    ArbiterSettings,
    apply_confidence_caps,
    build_evidence_payload,
    detect_cycle,
    select_evidence,
    structural_violations,
)


def ev(evidence_id, reliability="medium", group="g1", source_type="news", published=None):
    return Evidence(
        evidence_id=evidence_id,
        reliability=reliability,
        independence_group=group,
        source_type=source_type,
        published_at=published or "2026-07-16T00:00:00Z",
    )


def good_result():
    return Result(
        direct_answer="市場處於帶量整理。",
        claims=[
            Claim(claim_id="cl_001", claim_type="fact", text="報酬為 -4.9%"),
            Claim(
                claim_id="cl_002",
                claim_type="conclusion",
                text="屬於整理而非趨勢下跌",
                based_on_claim_ids=["cl_001"],
                confidence="high",
            ),
        ],
        claim_evidence_links=[
            Link(claim_id="cl_001", evidence_id="ev_001", stance="supports"),
            Link(claim_id="cl_002", evidence_id="ev_002", stance="supports"),
        ],
        confidence="high",
    )


def corroborated_result():
    """Same shape as ``good_result`` but the conclusion has two independent groups."""
    result = good_result()
    result.claim_evidence_links.append(
        Link(claim_id="cl_002", evidence_id="ev_003", stance="supports")
    )
    return result


def corroborated_ledger():
    return {
        "ev_001": ev("ev_001", "high", "one.com"),
        "ev_002": ev("ev_002", "high", "two.com"),
        "ev_003": ev("ev_003", "high", "three.com"),
    }


def run_arbiter(llm, ledger, indicators=(), settings=None):
    arbiter = Arbiter(
        llm=llm, result_schema=Result, settings=settings or ArbiterSettings()
    )
    return asyncio.run(
        arbiter.run(
            request=Request(),
            ledger=ledger,
            indicators=indicators,
            deadline=time.monotonic() + 30,
        )
    )


class SelectionTests(unittest.TestCase):
    def test_short_ledger_is_returned_whole(self):
        items = [ev(f"ev_{i:03d}") for i in range(5)]
        self.assertEqual(len(select_evidence(items, [], 30)), 5)

    def test_selection_never_exceeds_the_hard_maximum(self):
        items = [ev(f"ev_{i:03d}") for i in range(80)]
        self.assertEqual(
            len(select_evidence(items, [], 999)), MAX_EVIDENCE_FOR_ARBITER
        )

    def test_all_high_reliability_evidence_survives_truncation(self):
        highs = [ev(f"hi_{i}", reliability="high") for i in range(6)]
        lows = [ev(f"lo_{i}", reliability="low") for i in range(30)]
        chosen = {e.evidence_id for e in select_evidence(highs + lows, [], 10)}
        for item in highs:
            self.assertIn(item.evidence_id, chosen)

    def test_conflicting_evidence_survives_truncation(self):
        highs = [ev(f"hi_{i}", reliability="high") for i in range(8)]
        conflict_pair = [ev("con_a", reliability="low"), ev("con_b", reliability="low")]
        noise = [ev(f"n_{i}", reliability="low") for i in range(30)]
        indicator = Indicator(
            claim_id="cl_001",
            supporting_evidence_ids=["con_a"],
            opposing_evidence_ids=["con_b"],
        )
        chosen = {
            e.evidence_id
            for e in select_evidence(highs + conflict_pair + noise, [indicator], 12)
        }
        self.assertIn("con_a", chosen)
        self.assertIn("con_b", chosen)

    def test_remaining_slots_spread_across_independence_groups(self):
        crowd = [ev(f"a_{i}", reliability="low", group="loud.com") for i in range(20)]
        others = [
            ev("b_1", reliability="low", group="quiet-one.com"),
            ev("c_1", reliability="low", group="quiet-two.com"),
        ]
        groups = {
            e.independence_group for e in select_evidence(crowd + others, [], 5)
        }
        self.assertIn("quiet-one.com", groups)
        self.assertIn("quiet-two.com", groups)

    def test_payload_exposes_only_bounded_fields(self):
        payload = build_evidence_payload([ev("ev_001")])[0]
        self.assertEqual(
            set(payload),
            {
                "evidence_id", "asset", "source_type", "source_name", "reliability",
                "independence_group", "published_at", "is_stale", "normalized_fact",
                "content_reference",
            },
        )
        self.assertNotIn("content_hash", payload)
        self.assertNotIn("query_or_parameters", payload)


class CycleTests(unittest.TestCase):
    def test_acyclic_graph_passes(self):
        claims = [
            Claim(claim_id="a", claim_type="fact"),
            Claim(claim_id="b", claim_type="inference", based_on_claim_ids=["a"]),
        ]
        self.assertFalse(detect_cycle(claims))

    def test_direct_cycle_is_detected(self):
        claims = [
            Claim(claim_id="a", claim_type="inference", based_on_claim_ids=["b"]),
            Claim(claim_id="b", claim_type="inference", based_on_claim_ids=["a"]),
        ]
        self.assertTrue(detect_cycle(claims))

    def test_self_reference_is_detected(self):
        claims = [Claim(claim_id="a", claim_type="inference", based_on_claim_ids=["a"])]
        self.assertTrue(detect_cycle(claims))


class StructuralValidationTests(unittest.TestCase):
    def test_well_formed_result_has_no_violations(self):
        self.assertEqual(
            structural_violations(good_result(), {"ev_001", "ev_002"}), []
        )

    def test_unknown_evidence_reference_is_a_violation(self):
        violations = structural_violations(good_result(), {"ev_001"})
        self.assertTrue(any("unknown evidence ev_002" in v for v in violations))

    def test_unknown_claim_reference_is_a_violation(self):
        result = good_result()
        result.claim_evidence_links.append(
            Link(claim_id="cl_999", evidence_id="ev_001", stance="supports")
        )
        violations = structural_violations(result, {"ev_001", "ev_002"})
        self.assertTrue(any("unknown claim cl_999" in v for v in violations))

    def test_fact_with_dependencies_is_a_violation(self):
        result = good_result()
        result.claims[0].based_on_claim_ids = ["cl_002"]
        violations = structural_violations(result, {"ev_001", "ev_002"})
        self.assertTrue(any("must not depend" in v for v in violations))

    def test_conclusion_without_upstream_claim_is_a_violation(self):
        result = good_result()
        result.claims[1].based_on_claim_ids = []
        violations = structural_violations(result, {"ev_001", "ev_002"})
        self.assertTrue(any("no upstream claim" in v for v in violations))

    def test_conclusion_without_evidence_link_is_a_violation(self):
        result = good_result()
        result.claim_evidence_links = [
            Link(claim_id="cl_001", evidence_id="ev_001", stance="supports")
        ]
        violations = structural_violations(result, {"ev_001", "ev_002"})
        self.assertTrue(any("no non-neutral evidence link" in v for v in violations))

    def test_neutral_link_cannot_support_a_conclusion(self):
        result = good_result()
        result.claim_evidence_links[1].stance = "neutral"
        violations = structural_violations(result, {"ev_001", "ev_002"})
        self.assertTrue(any("no non-neutral evidence link" in v for v in violations))

    def test_insufficient_data_result_needs_no_conclusion_evidence(self):
        result = good_result()
        result.insufficient_data = True
        result.claim_evidence_links = []
        self.assertEqual(structural_violations(result, {"ev_001", "ev_002"}), [])

    def test_invalidation_threshold_must_cite_real_evidence(self):
        result = good_result()
        result.invalidation_conditions = [
            Invalidation(
                text="跌破 68000", metric="close", operator="lt",
                threshold=68000, basis_evidence_id="ev_404",
            )
        ]
        violations = structural_violations(result, {"ev_001", "ev_002"})
        self.assertTrue(any("cites unknown evidence ev_404" in v for v in violations))

    def test_qualitative_invalidation_needs_no_evidence_id(self):
        result = good_result()
        result.invalidation_conditions = [Invalidation(text="官方延後主網升級")]
        self.assertEqual(structural_violations(result, {"ev_001", "ev_002"}), [])


class ConfidenceCapTests(unittest.TestCase):
    def test_material_conflict_forces_the_claim_to_low(self):
        payload = good_result().model_dump()
        capped, notes = apply_confidence_caps(payload, [Indicator(claim_id="cl_002")])
        self.assertEqual(capped["claims"][1]["confidence"], "low")
        self.assertTrue(notes)

    def test_material_conflict_caps_overall_confidence_at_medium(self):
        payload = good_result().model_dump()
        capped, _ = apply_confidence_caps(payload, [Indicator(claim_id="cl_002")])
        self.assertEqual(capped["confidence"], "medium")

    def test_insufficient_data_forces_overall_low(self):
        payload = good_result().model_dump()
        payload["insufficient_data"] = True
        capped, _ = apply_confidence_caps(payload, [])
        self.assertEqual(capped["confidence"], "low")

    def test_single_independence_group_cannot_stay_high(self):
        payload = good_result().model_dump()
        ledger = {
            "ev_001": ev("ev_001", "high", "same.com"),
            "ev_002": ev("ev_002", "high", "same.com"),
        }
        capped, _ = apply_confidence_caps(payload, [], ledger)
        self.assertEqual(capped["claims"][1]["confidence"], "medium")

    def test_two_independence_groups_may_stay_high(self):
        # The cap is per claim, so cl_002 needs two supporting groups of its own.
        payload = corroborated_result().model_dump()
        capped, _ = apply_confidence_caps(payload, [], corroborated_ledger())
        self.assertEqual(capped["claims"][1]["confidence"], "high")

    def test_only_low_reliability_support_forces_low(self):
        payload = good_result().model_dump()
        ledger = {
            "ev_001": ev("ev_001", "low", "one.com"),
            "ev_002": ev("ev_002", "low", "two.com"),
        }
        capped, _ = apply_confidence_caps(payload, [], ledger)
        self.assertEqual(capped["claims"][1]["confidence"], "low")

    def test_caps_never_raise_confidence(self):
        payload = good_result().model_dump()
        payload["confidence"] = "low"
        payload["claims"][1]["confidence"] = "low"
        ledger = {
            "ev_001": ev("ev_001", "high", "one.com"),
            "ev_002": ev("ev_002", "high", "two.com"),
        }
        capped, _ = apply_confidence_caps(payload, [], ledger)
        self.assertEqual(capped["confidence"], "low")
        self.assertEqual(capped["claims"][1]["confidence"], "low")


class ArbiterRunTests(unittest.TestCase):
    def test_valid_generation_is_returned(self):
        ledger = Ledger(items=list(corroborated_ledger().values()))
        result, notes = run_arbiter(FakeLLM([corroborated_result()]), ledger)
        self.assertFalse(result.insufficient_data)
        self.assertEqual(result.claims[1].claim_type, "conclusion")
        self.assertEqual(result.claims[1].confidence, "high")
        self.assertEqual(notes, [], "a well-supported result needs no cap or note")

    def test_provider_failure_falls_back_deterministically(self):
        ledger = Ledger(items=[ev("ev_001", "high"), ev("ev_002", "high")])
        result, notes = run_arbiter(FakeLLM([BoomError("bedrock down")]), ledger)
        self.assertTrue(result.insufficient_data)
        self.assertEqual(result.confidence, "low")
        self.assertTrue(all(c.claim_type == "fact" for c in result.claims))
        self.assertTrue(any("決定論後備" in note for note in notes))

    def test_fallback_claims_only_cite_real_evidence(self):
        ledger = Ledger(items=[ev("ev_001", "high"), ev("ev_002", "high")])
        result, _ = run_arbiter(FakeLLM([BoomError("down")]), ledger)
        cited = {link.evidence_id for link in result.claim_evidence_links}
        self.assertTrue(cited <= {"ev_001", "ev_002"})

    def test_structurally_invalid_generation_falls_back(self):
        bad = good_result()
        bad.claim_evidence_links[0].evidence_id = "ev_ghost"
        ledger = Ledger(items=[ev("ev_001", "high"), ev("ev_002", "high")])
        result, notes = run_arbiter(FakeLLM([bad]), ledger)
        self.assertTrue(result.insufficient_data)
        self.assertTrue(any("結構驗證" in note for note in notes))

    def test_empty_ledger_short_circuits_without_calling_the_model(self):
        llm = FakeLLM([])
        result, notes = run_arbiter(llm, Ledger(items=[]))
        self.assertEqual(llm.calls, [], "no evidence means nothing to reason about")
        self.assertTrue(result.insufficient_data)
        self.assertTrue(any("為空" in note for note in notes))

    def test_truncation_is_disclosed(self):
        ledger = Ledger(items=[ev(f"ev_{i:03d}", "high") for i in range(40)])
        _, notes = run_arbiter(
            FakeLLM([BoomError("x")]), ledger, settings=ArbiterSettings(max_evidence=10)
        )
        self.assertTrue(any("截斷" in note for note in notes))

    def test_prompt_carries_evidence_ids_not_raw_pages(self):
        ledger = Ledger(items=[ev("ev_001", "high"), ev("ev_002", "high")])
        llm = FakeLLM([good_result()])
        run_arbiter(llm, ledger)
        text = llm.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn("ev_001", text)
        self.assertNotIn("content_hash", text)
        self.assertEqual(llm.calls[0]["operation"], "arbiter")

    def test_system_prompt_is_the_versioned_arbiter_prompt(self):
        ledger = Ledger(items=[ev("ev_001", "high")])
        llm = FakeLLM([good_result()])
        run_arbiter(llm, ledger)
        self.assertIn("Arbiter", llm.calls[0]["system_prompt"])

    def test_exactly_one_generation_is_attempted(self):
        ledger = Ledger(items=[ev("ev_001", "high"), ev("ev_002", "high")])
        llm = FakeLLM([good_result()])
        run_arbiter(llm, ledger)
        self.assertEqual(len(llm.calls), 1, "repair belongs to the client, not here")

    def test_cap_adjustments_reach_the_degradation_notes(self):
        ledger = Ledger(
            items=[ev("ev_001", "high", "same.com"), ev("ev_002", "high", "same.com")]
        )
        result, _ = run_arbiter(FakeLLM([good_result()]), ledger)
        self.assertEqual(result.claims[1].confidence, "medium")
        self.assertTrue(any("獨立來源群" in note for note in result.degradation_notes))


if __name__ == "__main__":
    unittest.main()
