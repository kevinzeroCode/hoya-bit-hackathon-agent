"""Unit tests for the bounded Planner stage."""

from __future__ import annotations

import asyncio
import time
import unittest

from _stubs import BoomError, FakeLLM, FakeRegistry, Plan, Request, Step

from hoya_agent.reasoning.planner import (
    MAX_PLANNED_STEPS,
    Planner,
    default_plan_payload,
    plan_violations,
)

OPERATIONS = ("organizer_csv.daily_bars", "binance.klines", "cryptopanic.posts")


def make_plan(operations=("binance.klines",), assets=("BTC",), **overrides):
    return Plan(
        assets=list(assets),
        planned_steps=[
            Step(step_id=f"s{i}", tool_operation=op)
            for i, op in enumerate(operations, start=1)
        ],
        **overrides,
    )


def run_planner(llm, registry=None, request=None):
    planner = Planner(
        llm=llm,
        plan_schema=Plan,
        tool_registry=registry or FakeRegistry(OPERATIONS),
    )
    return asyncio.run(
        planner.run(request=request or Request(), deadline=time.monotonic() + 30)
    )


class ViolationTests(unittest.TestCase):
    def test_allowlisted_plan_has_no_violations(self):
        self.assertEqual(plan_violations(make_plan(), OPERATIONS, ["BTC"]), [])

    def test_operation_outside_the_allowlist_is_rejected(self):
        violations = plan_violations(
            make_plan(operations=("evil.fetch_arbitrary_url",)), OPERATIONS, ["BTC"]
        )
        self.assertTrue(any("non-allowlisted" in v for v in violations))

    def test_empty_plan_is_rejected(self):
        self.assertTrue(plan_violations(make_plan(operations=()), OPERATIONS, ["BTC"]))

    def test_too_many_steps_is_rejected(self):
        plan = make_plan(operations=("binance.klines",) * (MAX_PLANNED_STEPS + 1))
        violations = plan_violations(plan, OPERATIONS, ["BTC"])
        self.assertTrue(any("more than" in v for v in violations))

    def test_changing_the_requested_assets_is_rejected(self):
        violations = plan_violations(make_plan(assets=("ETH",)), OPERATIONS, ["BTC"])
        self.assertTrue(any("changed the requested assets" in v for v in violations))

    def test_non_positive_lookback_is_rejected(self):
        violations = plan_violations(make_plan(lookback_days=0), OPERATIONS, ["BTC"])
        self.assertTrue(any("positive integer" in v for v in violations))

    def test_a_real_research_plan_with_matching_assets_has_no_violations(self):
        """`_stubs.Plan.assets` is `list[str]`, unlike the real `models.ResearchPlan`,
        whose `assets` field is `list[Asset]`. `application.py` wires the real model
        as `plan_schema`, so an Asset-enum-typed plan is exactly what production sees.

        Regression for a real bug: `str(Asset.BTC)` returns `'Asset.BTC'`, not
        `'BTC'`, under Python's Enum `__str__` for a `(str, Enum)` mixin, so
        comparing `str(asset)` on each side made every real plan look like it had
        changed the requested assets, discarding every LLM-generated plan on the
        script-driven live path (`docs/rehearsals/run-log.md`, 2026-08-02).
        """
        from hoya_agent.models import Asset, ResearchPlan, ResearchStep

        real_plan = ResearchPlan(
            assets=[Asset.BTC],
            question_summary="BTC 近期表現",
            planned_steps=[
                ResearchStep(
                    step_id="s1",
                    tool_operation="binance.klines",
                    rationale="market baseline",
                )
            ],
        )
        # Planner.run() always passes plain strings here (ReasoningRequest.assets is
        # `tuple[str, ...]`, built from `asset.value`), never Asset enum members.
        violations = plan_violations(real_plan, OPERATIONS, ["BTC"])
        self.assertEqual(violations, [])


class DefaultPlanTests(unittest.TestCase):
    def test_default_plan_only_uses_allowlisted_operations(self):
        payload = default_plan_payload(assets=["BTC"], allowed_operations=OPERATIONS)
        used = {step["tool_operation"] for step in payload["planned_steps"]}
        self.assertTrue(used <= set(OPERATIONS))

    def test_default_plan_is_capped(self):
        payload = default_plan_payload(
            assets=["BTC"], allowed_operations=tuple(f"op_{i}" for i in range(20))
        )
        self.assertLessEqual(len(payload["planned_steps"]), MAX_PLANNED_STEPS)

    def test_default_plan_records_its_reason(self):
        payload = default_plan_payload(
            assets=["BTC"], allowed_operations=OPERATIONS, reason="模型逾時"
        )
        self.assertIn("模型逾時", payload["notes"])

    def test_default_plan_is_schema_valid(self):
        Plan.model_validate(
            default_plan_payload(assets=["BTC"], allowed_operations=OPERATIONS)
        )


class PlannerRunTests(unittest.TestCase):
    def test_valid_plan_is_returned(self):
        plan, notes = run_planner(FakeLLM([make_plan()]))
        self.assertEqual(plan.planned_steps[0].tool_operation, "binance.klines")
        self.assertEqual(notes, [])

    def test_provider_failure_falls_back_to_the_default_plan(self):
        plan, notes = run_planner(FakeLLM([BoomError("bedrock down")]))
        self.assertEqual(plan.plan_version, "deterministic-default-v1")
        self.assertTrue(any("決定論預設計畫" in note for note in notes))

    def test_plan_naming_an_unapproved_tool_is_discarded(self):
        rogue = make_plan(operations=("attacker.exfiltrate",))
        plan, notes = run_planner(FakeLLM([rogue]))
        self.assertEqual(plan.plan_version, "deterministic-default-v1")
        used = {step.tool_operation for step in plan.planned_steps}
        self.assertTrue(used <= set(OPERATIONS), "fallback must stay inside the allowlist")
        self.assertTrue(any("允許清單" in note for note in notes))

    def test_plan_switching_assets_is_discarded(self):
        plan, _ = run_planner(FakeLLM([make_plan(assets=("ETH",))]))
        self.assertEqual(plan.assets, ["BTC"], "the frozen request wins")

    def test_asset_question_mismatch_is_surfaced(self):
        plan = make_plan()
        plan.asset_question_mismatch_warning = "題目提及 ETH，實際分析 BTC"
        _, notes = run_planner(FakeLLM([plan]))
        self.assertTrue(any("不一致" in note for note in notes))

    def test_prompt_offers_only_the_allowlist(self):
        llm = FakeLLM([make_plan()])
        run_planner(llm)
        text = llm.calls[0]["messages"][0]["content"][0]["text"]
        for operation in OPERATIONS:
            self.assertIn(operation, text)
        self.assertEqual(llm.calls[0]["operation"], "planner")

    def test_exactly_one_generation_is_attempted(self):
        llm = FakeLLM([make_plan()])
        run_planner(llm)
        self.assertEqual(len(llm.calls), 1)

    def test_prompt_version_is_exposed_for_run_config(self):
        planner = Planner(
            llm=FakeLLM([]), plan_schema=Plan, tool_registry=FakeRegistry(OPERATIONS)
        )
        self.assertEqual(planner.prompt_version, "planner-v1")


if __name__ == "__main__":
    unittest.main()
