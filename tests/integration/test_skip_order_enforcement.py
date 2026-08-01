"""S4 skip-order enforcement: the plan handed to Research loses skipped steps.

The policy lives in `deadline.plan_optional_work`; this file proves the pipeline
actually acts on it. Enforcement uses the existing interface — the pipeline trims
the `ResearchPlan` before handing it over — so the frozen
`reasoning/research_agent.py` needs no change.

Baseline research is never skipped. Only operations the caller declared optional
are, and every skip is disclosed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    ResearchPlan,
    ResearchStep,
    RunContext,
    RunMode,
    SourceType,
    TerminalState,
)
from hoya_agent.orchestration.deadline import OptionalWork, skip_note
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, PipelineOutcome

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, tzinfo=UTC)

BASELINE_OP = "fetch_rss_news"
OPTIONAL_OP = "fetch_fear_greed"
COUNTER_OP = "fetch_counter_signal"


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


class ImmediateMarket:
    async def execute(self, context: RunContext, emit) -> PipelineOutcome:
        del emit
        from tests.integration.test_fork_join import _ledger

        return PipelineOutcome(
            ledger=_ledger(context),
            result=None,
            terminal_state=TerminalState.completed,
        )


class RecordingResearch:
    """Captures the plan it was handed, so trimming is observable."""

    def __init__(self) -> None:
        self.plans: list[ResearchPlan] = []

    async def run(self, *, plan, request, deadline):
        del request, deadline
        self.plans.append(plan)
        return type("Outcome", (), {"drafts": [], "degradation_events": []})()

    @property
    def operations(self) -> list[str]:
        assert self.plans, "the research branch never ran"
        return [step.tool_operation for step in self.plans[-1].planned_steps]


def _plan(*operations: str) -> ResearchPlan:
    return ResearchPlan(
        assets=[Asset.BTC],
        question_summary="BTC 近期市場行為",
        required_evidence_types=[SourceType.news],
        planned_steps=[
            ResearchStep(
                step_id=f"st_{index:03d}",
                tool_operation=operation,
                rationale=f"execute {operation}",
            )
            for index, operation in enumerate(operations, start=1)
        ],
    )


class Planner:
    def __init__(self, plan: ResearchPlan) -> None:
        self._plan = plan

    async def run(self, *, request, deadline):
        del request, deadline
        return self._plan, []


def _context(deadline_seconds: int) -> RunContext:
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        requested_at=NOW,
        analysis_as_of=NOW,
        deadline_seconds=deadline_seconds,
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_sk01",
    )
    return build_run_context(request, Clock())


def _pipeline(research: RecordingResearch, planner: Planner) -> DeadlineAwarePipeline:
    return DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=ImmediateMarket(),
        planner=planner,
        research_agent=research,
        optional_operations=(OPTIONAL_OP,),
        counter_signal_operations=(COUNTER_OP,),
    )


async def test_a_generous_window_keeps_every_planned_optional_step() -> None:
    research = RecordingResearch()
    plan = _plan(BASELINE_OP, OPTIONAL_OP, COUNTER_OP)

    outcome = await _pipeline(research, Planner(plan)).execute(
        _context(900), lambda event: None
    )

    assert research.operations == [BASELINE_OP, OPTIONAL_OP, COUNTER_OP]
    assert not [note for note in outcome.degradation_notes if "略過" in note]


async def test_a_tight_window_surrenders_optional_context_before_the_counter_signal() -> None:
    # 200 s request -> 140 s analysis window -> ~52 s acquisition window, which
    # affords one 45 s optional call but not two.
    research = RecordingResearch()
    plan = _plan(BASELINE_OP, OPTIONAL_OP, COUNTER_OP)
    events = []

    outcome = await _pipeline(research, Planner(plan)).execute(_context(200), events.append)

    assert research.operations == [BASELINE_OP, COUNTER_OP], "optional context goes first"
    assert skip_note(OptionalWork.optional_context) in outcome.degradation_notes
    assert skip_note(OptionalWork.counter_signal_second_search) not in outcome.degradation_notes
    assert any(event.stage == OptionalWork.optional_context.value for event in events)
    assert outcome.terminal_state is TerminalState.degraded


async def test_the_trimmed_plan_is_still_a_valid_research_plan() -> None:
    research = RecordingResearch()
    plan = _plan(BASELINE_OP, OPTIONAL_OP, COUNTER_OP)

    await _pipeline(research, Planner(plan)).execute(_context(200), lambda event: None)

    trimmed = research.plans[-1]
    # model_copy skips validation, so prove the result would still pass it.
    ResearchPlan.model_validate(trimmed.model_dump())
    assert trimmed.assets == [Asset.BTC]
    assert trimmed.question_summary == plan.question_summary


async def test_baseline_research_is_never_surrendered() -> None:
    research = RecordingResearch()
    # No time for any optional call, but the baseline step must survive.
    plan = _plan(BASELINE_OP, OPTIONAL_OP, COUNTER_OP)

    await _pipeline(research, Planner(plan)).execute(_context(100), lambda event: None)

    assert research.operations == [BASELINE_OP]


async def test_an_all_optional_plan_with_no_time_skips_the_research_branch() -> None:
    research = RecordingResearch()
    plan = _plan(OPTIONAL_OP, COUNTER_OP)

    outcome = await _pipeline(research, Planner(plan)).execute(
        _context(100), lambda event: None
    )

    assert research.plans == [], "no step survived, so the branch must not start"
    assert skip_note(OptionalWork.optional_context) in outcome.degradation_notes
    assert skip_note(OptionalWork.counter_signal_second_search) in outcome.degradation_notes
    # The market branch's evidence still ships.
    assert [item.evidence_id for item in outcome.ledger.items] == ["ev_001"]


async def test_h3_is_never_scheduled_so_it_is_never_reported_as_skipped() -> None:
    research = RecordingResearch()
    plan = _plan(BASELINE_OP, OPTIONAL_OP, COUNTER_OP)

    outcome = await _pipeline(research, Planner(plan)).execute(
        _context(100), lambda event: None
    )

    assert skip_note(OptionalWork.conditional_debate) not in outcome.degradation_notes
