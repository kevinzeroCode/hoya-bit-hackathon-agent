"""S10 deadline budget — the clock is a hard constraint, proved on a fake clock.

Two guarantees the competition depends on:

1. non-essential work is surrendered and external calls are cancelled by
   **minute 12** (720 s) of a 900-second run;
2. the deterministic finalize starts **before** the reserved tail, so the four
   artifacts land inside the artifact deadline even when analysis ran long.

Nothing here sleeps. Budgets are pure arithmetic over `time.monotonic()`, so a
fake clock proves them exactly, and the one end-to-end case drives the real
`ApplicationService` with a deadline small enough that the hard stop fires
immediately.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.fakes import FixedClock

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.clock import build_run_context
from hoya_agent.models import Asset, RunContext, RunMode, TerminalState
from hoya_agent.orchestration.deadline import (
    ANALYSIS_HARD_STOP_SECONDS,
    SKIP_ORDER,
    DeadlineExceeded,
    DeadlineManager,
    OptionalWork,
    Stage,
    plan_optional_work,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES, RUN_CONFIG

pytestmark = pytest.mark.acceptance

NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)
COMPETITION_SECONDS = 900.0
MINUTE_12 = 720.0
ARTIFACT_DEADLINE_SECONDS = 780.0


def _manager(*, total_seconds: float = COMPETITION_SECONDS, monotonic: float = 1000.0):
    clock = FixedClock(NOW, monotonic_value=monotonic)
    return clock, DeadlineManager(clock, total_seconds, started_monotonic=monotonic)


def test_the_analysis_hard_stop_lands_on_minute_12():
    """900 s request → 180 s finalize reserve → 720 s of analysis."""
    _, manager = _manager()

    assert manager.finalize_reserve_seconds == pytest.approx(180.0)
    assert manager.analysis_window_seconds == pytest.approx(MINUTE_12)
    assert manager.analysis_window_seconds == pytest.approx(ANALYSIS_HARD_STOP_SECONDS)
    assert manager.budget_seconds()["analysis_hard_stop"] == pytest.approx(MINUTE_12)


def test_artifact_finalization_starts_before_the_reserved_deadline():
    """The artifact milestone must leave the whole reserve intact behind it."""
    _, manager = _manager()
    offsets = manager.budget_seconds()

    artifact_start = offsets[Stage.artifact.value]
    assert artifact_start == pytest.approx(630.0)
    assert artifact_start < MINUTE_12, "finalize must begin before the analysis hard stop"
    assert COMPETITION_SECONDS - artifact_start >= manager.finalize_reserve_seconds
    assert artifact_start < ARTIFACT_DEADLINE_SECONDS, "and before the 13-minute artifact deadline"

    # Stage milestones are monotonically ordered — no stage may overtake another.
    ordered = [offsets[stage.value] for stage in Stage]
    assert ordered == sorted(ordered)


def test_every_external_call_is_refused_once_the_clock_reaches_minute_12():
    """At 720 s the budget is gone, so a call is cancelled rather than started."""
    clock, manager = _manager()
    started = manager.started_monotonic

    assert manager.can_start()
    clock.advance(MINUTE_12)
    assert clock.monotonic() == started + MINUTE_12

    assert manager.remaining() == 0.0
    assert manager.can_start() is False
    for stage in Stage:
        assert manager.budget_for(stage, timeout_seconds=45.0) == 0.0


async def test_a_call_arriving_after_the_hard_stop_never_runs():
    """`DeadlineManager.run` closes the coroutine instead of awaiting it."""
    clock, manager = _manager()
    clock.advance(MINUTE_12 + 1.0)
    started = False

    async def external_call() -> str:
        nonlocal started
        started = True
        return "should never happen"

    with pytest.raises(DeadlineExceeded):
        await manager.run(external_call(), stage=Stage.gather, timeout_seconds=45.0)

    assert started is False, "an expired budget must not even enter the call"


def test_optional_work_is_surrendered_in_the_fixed_skip_order():
    """H3 → optional context → counter-signal second search, and disclosed."""
    pending = list(OptionalWork)

    # Enough room for the last item only: the first two are given up, in order.
    plan = plan_optional_work(pending, remaining_seconds=45.0, default_cost_seconds=45.0)
    assert plan.skipped == SKIP_ORDER[:2]
    assert plan.keep == (OptionalWork.counter_signal_second_search,)
    assert len(plan.reasons) == len(plan.skipped)
    assert all(reason.strip() for reason in plan.reasons)

    # No room at all: everything is surrendered, still in the fixed order.
    nothing_fits = plan_optional_work(pending, remaining_seconds=0.0, default_cost_seconds=45.0)
    assert nothing_fits.skipped == SKIP_ORDER
    assert nothing_fits.keep == ()

    # Plenty of room: nothing is surrendered and nothing is disclosed.
    all_fit = plan_optional_work(pending, remaining_seconds=1000.0, default_cost_seconds=45.0)
    assert all_fit.skipped == ()
    assert all_fit.keep == SKIP_ORDER


def test_baseline_work_is_never_surrendered_to_the_clock():
    """Only the three named optional items are skippable; baseline work is not."""
    with pytest.raises(ValueError):
        plan_optional_work(["market_worker"], remaining_seconds=0.0, default_cost_seconds=45.0)


class _HangingMarket:
    """Never finishes, so the acquisition window has to cancel it."""

    def __init__(self) -> None:
        self.cancelled = False

    async def execute(self, context: RunContext, emit) -> None:
        del context, emit
        try:
            await asyncio.sleep(60.0)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class _RealtimeClock:
    """Wall-clock UTC frozen, monotonic real — the hard stop must actually fire."""

    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return asyncio.get_running_loop().time()


async def test_the_hard_stop_still_delivers_four_artifacts_through_the_public_entry_point(tmp_path):
    """The end-to-end promise: time runs out, the run still ships four files.

    A one-second deadline puts the acquisition window in the sub-second range,
    so the market branch is cancelled with no evidence — the worst case — and
    the deterministic finalize still has to complete.
    """
    market = _HangingMarket()
    clock = _RealtimeClock()
    request = build_request(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix="dl01",
        deadline_seconds=1,
    )
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=clock,
        pipeline=DeadlineAwarePipeline(clock=clock, market_pipeline=market),
        configured_sources=["public_market_data"],
        stdout=io.StringIO(),
    )

    summary = await service.run(request)
    run_dir = Path(summary.artifact_dir)

    assert market.cancelled, "the non-essential branch must be cancelled by the hard stop"
    assert sorted(path.name for path in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    assert summary.missing_artifacts == []
    assert summary.terminal_state is TerminalState.cancelled
    assert summary.insufficient_data is True

    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    assert config["run_id"] == request.run_id
    assert config["missing_artifacts"] == []


def test_a_short_rehearsal_scales_its_budgets_instead_of_keeping_competition_sizes():
    """A 300 s rehearsal must not hand one stage a competition-sized budget."""
    _, small = _manager(total_seconds=300.0)
    _, full = _manager()

    assert small.analysis_window_seconds < full.analysis_window_seconds
    assert small.finalize_reserve_seconds == pytest.approx(60.0)
    assert small.analysis_window_seconds == pytest.approx(240.0)
    for stage in Stage:
        assert small.budget_seconds()[stage.value] < full.budget_seconds()[stage.value]


def test_the_run_context_drives_the_budget_rather_than_a_resampled_clock():
    """`for_run` must reuse the frozen run start, not sample the clock again."""
    clock = FixedClock(NOW, monotonic_value=500.0)
    request = build_request(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix="dl02",
        deadline_seconds=900,
    )
    context = build_run_context(request, clock)

    clock.advance(30.0)  # time passes before the pipeline builds its manager
    manager = DeadlineManager.for_run(context, clock)

    assert manager.started_monotonic == pytest.approx(context.started_monotonic)
    assert manager.analysis_window_seconds == pytest.approx(MINUTE_12)
    assert manager.remaining() == pytest.approx(MINUTE_12 - 30.0)
