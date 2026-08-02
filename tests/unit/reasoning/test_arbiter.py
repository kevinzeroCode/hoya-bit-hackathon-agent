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


def ev(
    evidence_id,
    reliability="medium",
    group="g1",
    source_type="news",
    published=None,
    fact="14 日報酬為 -4.9%",
    asset="BTC",
):
    return Evidence(
        evidence_id=evidence_id,
        reliability=reliability,
        independence_group=group,
        source_type=source_type,
        published_at=published or "2026-07-16T00:00:00Z",
        normalized_fact=fact,
        asset=asset,
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


class NumberProvenanceTests(unittest.TestCase):
    """Claim 與 direct_answer 中的數字必須溯源自連結證據（prompt 鐵律一的程式化）。"""

    def ledger(self):
        return {
            "ev_001": ev("ev_001", "high", "one.com", fact="14 日報酬為 -4.9%"),
            "ev_002": ev("ev_002", "high", "two.com", fact="成交量 z-score 為 +1.8"),
        }

    def test_grounded_numbers_pass(self):
        self.assertEqual(
            structural_violations(
                good_result(), {"ev_001", "ev_002"}, evidence_by_id=self.ledger()
            ),
            [],
        )

    def test_fabricated_number_is_a_violation(self):
        result = good_result()
        result.claims[0].text = "報酬為 -12.5%"
        violations = structural_violations(
            result, {"ev_001", "ev_002"}, evidence_by_id=self.ledger()
        )
        self.assertTrue(any("12.5" in v and "cl_001" in v for v in violations))

    def test_thousand_separator_matches_plain_form(self):
        ledger = dict(self.ledger())
        ledger["ev_001"] = ev("ev_001", "high", "one.com", fact="收盤價 68000 美元")
        result = good_result()
        result.claims[0].text = "收盤價為 68,000"
        self.assertEqual(
            structural_violations(result, {"ev_001", "ev_002"}, evidence_by_id=ledger),
            [],
        )

    def test_upstream_claim_evidence_grounds_inference_numbers(self):
        # cl_002 依賴 cl_001；-4.9 由 cl_001 連結的 ev_001 溯源，即使 cl_002
        # 自己的 link（ev_002）不含該數字。
        result = good_result()
        result.claims[1].text = "跌幅 -4.9% 伴隨量能放大，屬帶量整理"
        self.assertEqual(
            structural_violations(
                result, {"ev_001", "ev_002"}, evidence_by_id=self.ledger()
            ),
            [],
        )

    def test_time_range_dates_are_exempt(self):
        result = good_result()
        result.claims[0].time_range = {"start": "2026-07-03", "end": "2026-07-16"}
        result.claims[0].text = "2026-07-03 至 2026-07-16 期間報酬為 -4.9%"
        self.assertEqual(
            structural_violations(
                result, {"ev_001", "ev_002"}, evidence_by_id=self.ledger()
            ),
            [],
        )

    def test_internal_evidence_ids_are_not_treated_as_numbers(self):
        result = good_result()
        result.claims[1].text = "如 ev_002 所示，量能高於自身基準"
        self.assertEqual(
            structural_violations(
                result, {"ev_001", "ev_002"}, evidence_by_id=self.ledger()
            ),
            [],
        )

    def test_direct_answer_numbers_must_be_grounded(self):
        result = good_result()
        result.direct_answer = "跌幅達 -20%，市場疲弱。"
        violations = structural_violations(
            result, {"ev_001", "ev_002"}, evidence_by_id=self.ledger()
        )
        self.assertTrue(any("direct_answer" in v and "20" in v for v in violations))

    def test_check_is_skipped_without_an_evidence_map(self):
        result = good_result()
        result.claims[0].text = "報酬為 -12.5%"
        self.assertEqual(structural_violations(result, {"ev_001", "ev_002"}), [])


class AssetConsistencyTests(unittest.TestCase):
    """Claim 宣稱的資產必須與其連結證據的資產有交集（market-wide 例外）。"""

    def test_claim_with_no_matching_asset_evidence_is_a_violation(self):
        result = good_result()
        result.claims[0].assets = ["BTC"]
        ledger = {
            "ev_001": ev("ev_001", "high", "one.com", asset="ETH"),
            "ev_002": ev("ev_002", "high", "two.com", asset="ETH"),
        }
        violations = structural_violations(
            result, {"ev_001", "ev_002"}, evidence_by_id=ledger
        )
        self.assertTrue(any("cl_001" in v and "asset" in v for v in violations))

    def test_market_wide_evidence_grounds_any_asset(self):
        result = good_result()
        result.claims[0].assets = ["BTC"]
        ledger = {
            "ev_001": ev("ev_001", "high", "one.com", asset=None),
            "ev_002": ev("ev_002", "high", "two.com"),
        }
        self.assertEqual(
            structural_violations(result, {"ev_001", "ev_002"}, evidence_by_id=ledger),
            [],
        )

    def test_one_matching_link_among_several_passes(self):
        result = good_result()
        result.claims[0].assets = ["BTC"]
        result.claim_evidence_links.append(
            Link(claim_id="cl_001", evidence_id="ev_003", stance="supports")
        )
        ledger = {
            "ev_001": ev("ev_001", "high", "one.com", asset="ETH"),
            "ev_002": ev("ev_002", "high", "two.com"),
            "ev_003": ev("ev_003", "high", "three.com", asset="BTC"),
        }
        self.assertEqual(
            structural_violations(
                result, {"ev_001", "ev_002", "ev_003"}, evidence_by_id=ledger
            ),
            [],
        )

    def test_dual_asset_claim_matches_either_asset(self):
        result = good_result()
        result.claims[0].assets = ["BTC", "ETH"]
        ledger = {
            "ev_001": ev("ev_001", "high", "one.com", asset="ETH"),
            "ev_002": ev("ev_002", "high", "two.com"),
        }
        self.assertEqual(
            structural_violations(result, {"ev_001", "ev_002"}, evidence_by_id=ledger),
            [],
        )

    def test_neutral_only_links_are_not_asset_checked(self):
        result = good_result()
        result.claims[0].assets = ["BTC"]
        result.claim_evidence_links[0].stance = "neutral"
        ledger = {
            "ev_001": ev("ev_001", "high", "one.com", asset="ETH"),
            "ev_002": ev("ev_002", "high", "two.com"),
        }
        violations = structural_violations(
            result, {"ev_001", "ev_002"}, evidence_by_id=ledger
        )
        self.assertFalse(any("share no asset" in v for v in violations))


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

    def test_one_bad_conclusion_is_repaired_not_fully_discarded(self):
        # Facts + inference + a good conclusion + a conclusion whose only link is
        # neutral. The bad conclusion must be dropped while the valid reasoning
        # layers survive — not collapsed into the fact-only fallback.
        gen = Result(
            direct_answer="帶量整理。",
            claims=[
                Claim(claim_id="cl_001", claim_type="fact", text="報酬為 -4.9%"),
                Claim(
                    claim_id="cl_002", claim_type="inference",
                    text="回落有承接", based_on_claim_ids=["cl_001"],
                ),
                Claim(
                    claim_id="cl_003", claim_type="conclusion",
                    text="屬整理非崩跌", based_on_claim_ids=["cl_002"],
                ),
                Claim(
                    claim_id="cl_004", claim_type="conclusion",
                    text="無支持的結論", based_on_claim_ids=["cl_002"],
                ),
            ],
            claim_evidence_links=[
                Link(claim_id="cl_001", evidence_id="ev_001", stance="supports"),
                Link(claim_id="cl_002", evidence_id="ev_001", stance="supports"),
                Link(claim_id="cl_003", evidence_id="ev_002", stance="supports"),
                Link(claim_id="cl_004", evidence_id="ev_002", stance="neutral"),
            ],
            confidence="medium",
        )
        ledger = Ledger(items=[ev("ev_001", "high", "a.com"), ev("ev_002", "high", "b.com")])
        result, notes = run_arbiter(FakeLLM([gen]), ledger)
        self.assertFalse(result.insufficient_data)
        kept = {c.claim_id for c in result.claims}
        self.assertEqual(kept, {"cl_001", "cl_002", "cl_003"})
        self.assertTrue(any(c.claim_type == "conclusion" for c in result.claims))
        self.assertTrue(any("部分不合規" in note for note in notes))

    def test_fabricated_number_on_leaf_conclusion_is_repaired_away(self):
        # 只有 cl_004 引用了證據裡不存在的數字：修剪它、保留其餘推理層。
        gen = Result(
            direct_answer="帶量整理。",
            claims=[
                Claim(claim_id="cl_001", claim_type="fact", text="報酬為 -4.9%"),
                Claim(
                    claim_id="cl_002", claim_type="inference",
                    text="回落有承接", based_on_claim_ids=["cl_001"],
                ),
                Claim(
                    claim_id="cl_003", claim_type="conclusion",
                    text="屬整理非崩跌", based_on_claim_ids=["cl_002"],
                ),
                Claim(
                    claim_id="cl_004", claim_type="conclusion",
                    text="下一步看 123456", based_on_claim_ids=["cl_002"],
                ),
            ],
            claim_evidence_links=[
                Link(claim_id="cl_001", evidence_id="ev_001", stance="supports"),
                Link(claim_id="cl_002", evidence_id="ev_001", stance="supports"),
                Link(claim_id="cl_003", evidence_id="ev_002", stance="supports"),
                Link(claim_id="cl_004", evidence_id="ev_002", stance="supports"),
            ],
            confidence="medium",
        )
        ledger = Ledger(items=[ev("ev_001", "high", "a.com"), ev("ev_002", "high", "b.com")])
        result, notes = run_arbiter(FakeLLM([gen]), ledger)
        self.assertFalse(result.insufficient_data)
        kept = {c.claim_id for c in result.claims}
        self.assertEqual(kept, {"cl_001", "cl_002", "cl_003"})
        self.assertTrue(any("部分不合規" in note for note in notes))

    def test_fabricated_number_generation_falls_back(self):
        # 偽造數字出現在唯一的 fact 上：修剪會連鎖清空整張圖，只能 fallback。
        bad = good_result()
        bad.claims[0].text = "報酬為 -99.9%"
        ledger = Ledger(items=[ev("ev_001", "high"), ev("ev_002", "high")])
        result, notes = run_arbiter(FakeLLM([bad]), ledger)
        self.assertTrue(result.insufficient_data)
        self.assertTrue(any("結構驗證" in note for note in notes))

    def test_ungrounded_direct_answer_cannot_be_repaired(self):
        # direct_answer 不是 claim，修剪救不了它：數字無法溯源就 fallback。
        bad = good_result()
        bad.direct_answer = "跌幅達 -20%，市場疲弱。"
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
