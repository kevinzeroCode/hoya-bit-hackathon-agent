"""S4 deadline budgeting: stage milestones, proportional scaling, finalize reserve.

The absolute milestones for a 900-second run are fixed by `docs/Features.md` §5.6
(from `design.md` §6.1): Planner 30 s, parallel acquisition 270 s, Evidence
Processor 360 s, Arbiter + render 510 s, artifact verification target 630 s and
the analysis hard stop at 720 s. A shorter request deadline must scale all of
them rather than keep competition-sized budgets, and the tail of the run belongs
to the deterministic finalize.

Every budget here is driven by an injected fake clock. No test sleeps for real
wall-clock stage time; the only real awaits are sub-50-millisecond ones that
prove `asyncio.wait_for` is actually wired to the computed budget.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from tests.fakes import FixedClock

from hoya_agent.clock import build_run_context
from hoya_agent.models import AnalysisRequest, Asset, RunMode
from hoya_agent.orchestration.deadline import (
    ANALYSIS_HARD_STOP_SECONDS,
    FINALIZE_RESERVE_MIN_SECONDS,
    DeadlineExceeded,
    DeadlineManager,
    Stage,
)

NOW = datetime(2026, 5, 31, tzinfo=UTC)
START = 1000.0


def _manager(total_seconds: float) -> tuple[DeadlineManager, FixedClock]:
    clock = FixedClock(NOW, monotonic_value=START)
    return DeadlineManager(clock, total_seconds), clock


def test_official_budget_reproduces_the_approved_stage_milestones() -> None:
    manager, _ = _manager(900.0)

    assert manager.deadline_for(Stage.planner) == pytest.approx(START + 30.0)
    assert manager.deadline_for(Stage.gather) == pytest.approx(START + 270.0)
    assert manager.deadline_for(Stage.evidence) == pytest.approx(START + 360.0)
    assert manager.deadline_for(Stage.reason) == pytest.approx(START + 510.0)
    assert manager.deadline_for(Stage.artifact) == pytest.approx(START + 630.0)
    assert manager.analysis_deadline == pytest.approx(START + ANALYSIS_HARD_STOP_SECONDS)


def test_stage_deadlines_are_monotonic_and_never_pass_the_analysis_deadline() -> None:
    manager, _ = _manager(900.0)

    deadlines = [manager.deadline_for(stage) for stage in Stage]
    assert deadlines == sorted(deadlines)
    assert max(deadlines) <= manager.analysis_deadline


def test_a_short_deadline_scales_every_stage_proportionally() -> None:
    # 450 s request: reserve 20% = 90 s, so the analysis window is 360 s (half of 720).
    manager, _ = _manager(450.0)

    assert manager.finalize_reserve_seconds == pytest.approx(90.0)
    assert manager.analysis_window_seconds == pytest.approx(360.0)
    assert manager.deadline_for(Stage.planner) == pytest.approx(START + 15.0)
    assert manager.deadline_for(Stage.gather) == pytest.approx(START + 135.0)
    assert manager.deadline_for(Stage.reason) == pytest.approx(START + 255.0)
    assert manager.analysis_deadline == pytest.approx(START + 360.0)


def test_finalize_reserve_is_at_least_sixty_seconds_when_the_run_can_afford_it() -> None:
    # 20% of 300 s is exactly the 60-second floor; below that the floor wins.
    assert _manager(300.0)[0].finalize_reserve_seconds == pytest.approx(
        FINALIZE_RESERVE_MIN_SECONDS
    )
    assert _manager(200.0)[0].finalize_reserve_seconds == pytest.approx(
        FINALIZE_RESERVE_MIN_SECONDS
    )


def test_finalize_reserve_never_claims_more_than_half_of_a_tiny_run() -> None:
    manager, _ = _manager(100.0)

    assert manager.finalize_reserve_seconds == pytest.approx(50.0)
    assert manager.analysis_window_seconds == pytest.approx(50.0)


def test_analysis_never_runs_past_the_twelve_minute_hard_stop() -> None:
    manager, _ = _manager(1800.0)

    assert manager.analysis_window_seconds == pytest.approx(ANALYSIS_HARD_STOP_SECONDS)
    assert manager.analysis_deadline == pytest.approx(START + ANALYSIS_HARD_STOP_SECONDS)


def test_remaining_is_stage_scoped_and_counts_down_with_the_clock() -> None:
    manager, clock = _manager(900.0)

    assert manager.remaining(Stage.planner) == pytest.approx(30.0)
    clock.advance(20.0)
    assert manager.remaining(Stage.planner) == pytest.approx(10.0)
    assert manager.remaining(Stage.gather) == pytest.approx(250.0)


def test_remaining_never_goes_negative() -> None:
    manager, clock = _manager(900.0)
    clock.advance(5000.0)

    assert manager.remaining(Stage.planner) == 0.0
    assert manager.remaining() == 0.0


def test_remaining_without_a_stage_counts_down_to_the_analysis_hard_stop() -> None:
    manager, clock = _manager(900.0)
    clock.advance(700.0)

    assert manager.remaining() == pytest.approx(20.0)


def test_can_start_respects_the_finalize_reserve() -> None:
    manager, clock = _manager(900.0)
    clock.advance(700.0)

    assert manager.can_start(reserve_seconds=10.0) is True
    assert manager.can_start(reserve_seconds=30.0) is False


def test_run_clamps_the_await_to_the_stage_budget() -> None:
    # 1 s total: reserve 0.5 s, analysis window 0.5 s, planner budget ~21 ms.
    manager, _ = _manager(1.0)
    assert manager.remaining(Stage.planner) < 0.05

    async def slow() -> None:
        await asyncio.sleep(30.0)

    async def exercise() -> None:
        with pytest.raises(DeadlineExceeded):
            await manager.run(slow(), stage=Stage.planner)

    asyncio.run(exercise())


def test_run_clamps_to_the_smaller_of_stage_budget_and_call_timeout() -> None:
    manager, _ = _manager(900.0)

    assert manager.budget_for(Stage.gather, timeout_seconds=45.0) == pytest.approx(45.0)
    assert manager.budget_for(Stage.planner, timeout_seconds=45.0) == pytest.approx(30.0)


def test_run_refuses_to_start_once_the_budget_is_exhausted() -> None:
    manager, clock = _manager(900.0)
    clock.advance(900.0)
    entered: list[bool] = []

    async def never_runs() -> None:
        entered.append(True)

    async def exercise() -> None:
        with pytest.raises(DeadlineExceeded):
            await manager.run(never_runs(), stage=Stage.reason)

    asyncio.run(exercise())
    assert entered == [], "an exhausted budget must not start the call at all"


def test_for_run_takes_its_window_from_the_frozen_run_context() -> None:
    clock = FixedClock(NOW, monotonic_value=START)
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        requested_at=NOW,
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_dl01",
    )
    context = build_run_context(request, clock)

    manager = DeadlineManager.for_run(context, clock)

    assert manager.total_seconds == pytest.approx(900.0)
    assert manager.analysis_deadline == pytest.approx(
        context.started_monotonic + ANALYSIS_HARD_STOP_SECONDS
    )


def test_budget_seconds_is_reportable_as_offsets_from_run_start() -> None:
    manager, _ = _manager(900.0)

    budgets = manager.budget_seconds()

    assert budgets[Stage.gather.value] == pytest.approx(270.0)
    assert budgets["analysis_hard_stop"] == pytest.approx(720.0)
    assert budgets["finalize_reserve"] == pytest.approx(180.0)
