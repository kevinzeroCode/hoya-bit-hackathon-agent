"""S4 run state: stage lifecycle, WorkerStatus mapping and terminal derivation.

Terminal state is decided here so the UI never has to infer it. The distinction
the acceptance criteria turn on: one cancelled branch alongside a completed
sibling is a *degraded* run, while cancelling the run itself is `cancelled`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.fakes import FixedClock

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    ExecutionEvent,
    RunMode,
    StageState,
    TerminalState,
    WorkerStatus,
)
from hoya_agent.orchestration.run_state import (
    RunStateMachine,
    derive_terminal_state,
    stage_state_for,
)

NOW = datetime(2026, 5, 31, tzinfo=UTC)


def _machine() -> tuple[RunStateMachine, FixedClock, list[ExecutionEvent]]:
    clock = FixedClock(NOW, monotonic_value=500.0)
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        requested_at=NOW,
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_rs01",
    )
    context = build_run_context(request, clock)
    events: list[ExecutionEvent] = []
    return RunStateMachine(context=context, clock=clock, emit=events.append), clock, events


# -- WorkerStatus -> StageState -------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (WorkerStatus.completed, StageState.completed),
        (WorkerStatus.partial, StageState.degraded),
        (WorkerStatus.failed, StageState.failed),
    ],
)
def test_worker_status_maps_onto_the_stage_lifecycle(
    status: WorkerStatus, expected: StageState
) -> None:
    assert stage_state_for(status) is expected


def test_worker_status_accepts_the_raw_string_a_worker_reported() -> None:
    assert stage_state_for("partial") is StageState.degraded


def test_an_unknown_worker_status_is_rejected_rather_than_guessed() -> None:
    with pytest.raises(ValueError, match="worker status"):
        stage_state_for("probably_fine")


# -- stage lifecycle ------------------------------------------------------------


def test_an_untouched_stage_is_pending() -> None:
    machine, _, _ = _machine()

    assert machine.state_of("market_worker") is StageState.pending


def test_a_stage_goes_pending_then_running_then_settled() -> None:
    machine, _, _ = _machine()

    machine.start("market_worker")
    assert machine.state_of("market_worker") is StageState.running

    machine.settle("market_worker", StageState.completed)
    assert machine.state_of("market_worker") is StageState.completed


def test_a_skipped_stage_may_settle_without_ever_running() -> None:
    machine, _, _ = _machine()

    machine.settle("arbiter", StageState.degraded, message="剩餘時間不足，略過 Arbiter。")

    assert machine.state_of("arbiter") is StageState.degraded


def test_a_settled_stage_cannot_be_restarted() -> None:
    machine, _, _ = _machine()
    machine.start("market_worker")
    machine.settle("market_worker", StageState.completed)

    with pytest.raises(ValueError, match="cannot start"):
        machine.start("market_worker")


def test_a_settled_stage_cannot_settle_twice() -> None:
    machine, _, _ = _machine()
    machine.settle("arbiter", StageState.failed)

    with pytest.raises(ValueError, match="cannot settle"):
        machine.settle("arbiter", StageState.completed)


def test_settling_into_a_non_terminal_state_is_rejected() -> None:
    machine, _, _ = _machine()
    machine.start("market_worker")

    with pytest.raises(ValueError, match="terminal stage state"):
        machine.settle("market_worker", StageState.running)


def test_settle_from_worker_maps_the_status_and_returns_it() -> None:
    machine, _, _ = _machine()
    machine.start("market_worker")

    settled = machine.settle_from_worker("market_worker", WorkerStatus.partial)

    assert settled is StageState.degraded
    assert machine.state_of("market_worker") is StageState.degraded


# -- emitted events -------------------------------------------------------------


def test_transitions_stream_stage_start_and_stage_end_events() -> None:
    machine, clock, events = _machine()

    machine.start("market_worker")
    clock.advance(2.5)
    machine.settle("market_worker", StageState.completed, output_count=7)

    assert [(e.stage, e.event_type, e.status) for e in events] == [
        ("market_worker", "stage_start", "running"),
        ("market_worker", "stage_end", "completed"),
    ]
    assert events[1].duration_ms == 2500
    assert events[1].output_count == 7
    assert {e.run_id for e in events} == {"run_20260531_000000_rs01"}
    assert {e.run_mode for e in events} == {RunMode.rehearsal}


def test_a_stage_that_never_started_reports_no_duration() -> None:
    machine, _, events = _machine()

    machine.settle("arbiter", StageState.degraded)

    assert events[0].duration_ms is None


def test_stage_durations_are_reportable_for_the_run_config_snapshot() -> None:
    machine, clock, _ = _machine()
    machine.start("market_worker")
    clock.advance(1.25)
    machine.settle("market_worker", StageState.completed)

    assert machine.stage_durations_ms() == {"market_worker": 1250}


# -- terminal derivation --------------------------------------------------------


def test_all_clean_stages_make_a_completed_run() -> None:
    machine, _, _ = _machine()
    for stage in ("market_worker", "evidence_processor"):
        machine.start(stage)
        machine.settle(stage, StageState.completed)

    assert machine.terminal_state() is TerminalState.completed


def test_one_cancelled_branch_with_a_completed_sibling_is_a_degraded_run() -> None:
    machine, _, _ = _machine()
    machine.start("market_worker")
    machine.settle("market_worker", StageState.completed)
    machine.start("research_agent")
    machine.cancel("research_agent", message="取證 deadline 到點，取消未完成的研究呼叫。")

    assert machine.state_of("research_agent") is StageState.cancelled
    assert machine.terminal_state() is TerminalState.degraded


def test_a_partial_branch_degrades_the_run_without_failing_it() -> None:
    machine, _, _ = _machine()
    machine.start("market_worker")
    machine.settle_from_worker("market_worker", WorkerStatus.partial)

    assert machine.terminal_state() is TerminalState.degraded


def test_every_stage_failing_makes_a_failed_run() -> None:
    machine, _, _ = _machine()
    for stage in ("market_worker", "research_agent"):
        machine.start(stage)
        machine.settle(stage, StageState.failed)

    assert machine.terminal_state() is TerminalState.failed


def test_cancelling_the_run_maps_to_cancelled_not_degraded() -> None:
    machine, _, events = _machine()
    machine.start("market_worker")
    machine.settle("market_worker", StageState.completed)
    machine.start("research_agent")

    machine.cancel_run(message="分析硬停到點。")

    assert machine.terminal_state() is TerminalState.cancelled
    # A running stage is settled as cancelled rather than left dangling.
    assert machine.state_of("research_agent") is StageState.cancelled
    assert any(e.stage == "run" and e.status == "cancelled" for e in events)


def test_every_stage_cancelled_is_a_cancelled_run() -> None:
    machine, _, _ = _machine()
    for stage in ("market_worker", "research_agent"):
        machine.start(stage)
        machine.cancel(stage)

    assert machine.terminal_state() is TerminalState.cancelled


def test_a_run_with_no_recorded_stage_is_completed() -> None:
    machine, _, _ = _machine()

    assert machine.terminal_state() is TerminalState.completed


def test_running_stages_do_not_yet_influence_the_terminal_state() -> None:
    machine, _, _ = _machine()
    machine.start("market_worker")

    assert machine.terminal_state() is TerminalState.completed


def test_derive_terminal_state_is_usable_without_a_machine() -> None:
    assert derive_terminal_state([]) is TerminalState.completed
    assert derive_terminal_state([StageState.completed]) is TerminalState.completed
    assert derive_terminal_state([StageState.degraded]) is TerminalState.degraded
    assert (
        derive_terminal_state([StageState.completed, StageState.cancelled])
        is TerminalState.degraded
    )
    assert derive_terminal_state([StageState.failed]) is TerminalState.failed
    assert derive_terminal_state([StageState.cancelled]) is TerminalState.cancelled
    assert (
        derive_terminal_state([StageState.completed], run_cancelled=True)
        is TerminalState.cancelled
    )
