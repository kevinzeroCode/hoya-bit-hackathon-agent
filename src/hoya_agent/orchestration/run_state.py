"""In-memory stage lifecycle and terminal run-state derivation.

Orchestration decides the run's state so no other layer has to infer it — in
particular the UI reads a terminal state that was already recorded in
`execution_log.jsonl` and `run_config.json`.

Two vocabularies meet here. `WorkerStatus` (`completed|partial|failed`) is what a
worker reports about its own branch; `StageState`
(`pending|running|completed|degraded|failed|cancelled`) is what the run records
about that branch. The mapping is deterministic and one-way: a partial branch
degrades the run, it never passes as complete.

Cancellation has two levels, and the difference decides the terminal state. One
cancelled branch beside a completed sibling is a *degraded* run — the sibling's
evidence still ships. Cancelling the run itself is `cancelled`.

No network, no LLM, no file system here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType

from hoya_agent.models import (
    ExecutionEvent,
    RunContext,
    StageState,
    TerminalState,
    WorkerStatus,
)
from hoya_agent.ports import Clock

EventEmitter = Callable[[ExecutionEvent], None]

RUN_STAGE = "run"

SETTLED_STAGE_STATES: frozenset[StageState] = frozenset(
    {
        StageState.completed,
        StageState.degraded,
        StageState.failed,
        StageState.cancelled,
    }
)

STAGE_STATE_BY_WORKER_STATUS: Mapping[WorkerStatus, StageState] = MappingProxyType(
    {
        WorkerStatus.completed: StageState.completed,
        WorkerStatus.partial: StageState.degraded,
        WorkerStatus.failed: StageState.failed,
    }
)


def stage_state_for(status: WorkerStatus | str) -> StageState:
    """Map a worker's self-reported status onto the run's stage lifecycle."""
    if isinstance(status, WorkerStatus):
        return STAGE_STATE_BY_WORKER_STATUS[status]
    raw = str(getattr(status, "value", status))
    try:
        return STAGE_STATE_BY_WORKER_STATUS[WorkerStatus(raw)]
    except ValueError as exc:
        raise ValueError(f"unknown worker status {raw!r}") from exc


def derive_terminal_state(
    states: Iterable[StageState],
    *,
    run_cancelled: bool = False,
) -> TerminalState:
    """Collapse settled stage states into one terminal run state.

    A single cancelled or failed branch degrades the run rather than failing it,
    because the sibling branch's evidence still reaches the renderer.
    """
    settled = [state for state in states if state in SETTLED_STAGE_STATES]
    if run_cancelled:
        return TerminalState.cancelled
    if settled and all(state is StageState.cancelled for state in settled):
        return TerminalState.cancelled
    if settled and all(state is StageState.failed for state in settled):
        return TerminalState.failed
    if any(
        state in {StageState.failed, StageState.degraded, StageState.cancelled}
        for state in settled
    ):
        return TerminalState.degraded
    return TerminalState.completed


class RunStateMachine:
    """Tracks one run's stage lifecycle and streams the transitions.

    Stage keys are execution-log stage names (`market_worker`, `research_agent`,
    ...), which are finer grained than the budget milestones in `deadline.py`.
    """

    def __init__(
        self,
        *,
        context: RunContext,
        clock: Clock,
        emit: EventEmitter | None = None,
    ) -> None:
        self._context = context
        self._clock = clock
        self._emit = emit
        self._states: dict[str, StageState] = {}
        self._started: dict[str, float] = {}
        self._durations_ms: dict[str, int] = {}
        self._run_cancelled = False

    # -- queries ------------------------------------------------------------

    def state_of(self, stage: str) -> StageState:
        return self._states.get(stage, StageState.pending)

    @property
    def stage_states(self) -> dict[str, StageState]:
        return dict(self._states)

    @property
    def run_cancelled(self) -> bool:
        return self._run_cancelled

    def settled_states(self) -> list[StageState]:
        return [state for state in self._states.values() if state in SETTLED_STAGE_STATES]

    def stage_durations_ms(self) -> dict[str, int]:
        return dict(self._durations_ms)

    def terminal_state(self) -> TerminalState:
        return derive_terminal_state(self.settled_states(), run_cancelled=self._run_cancelled)

    # -- transitions --------------------------------------------------------

    def start(self, stage: str, *, message: str = "") -> None:
        current = self.state_of(stage)
        if current is not StageState.pending:
            raise ValueError(f"stage {stage!r} cannot start from {current.value}")
        self._states[stage] = StageState.running
        self._started[stage] = self._clock.monotonic()
        self._publish(
            stage,
            "stage_start",
            StageState.running.value,
            message=message or f"{stage} running",
        )

    def settle(
        self,
        stage: str,
        state: StageState,
        *,
        message: str = "",
        output_count: int | None = None,
        error_category: str | None = None,
    ) -> StageState:
        """Record a stage's terminal state.

        A stage may settle without ever running: optional work skipped under time
        pressure is recorded, not silently dropped.
        """
        if state not in SETTLED_STAGE_STATES:
            raise ValueError(f"{state.value!r} is not a terminal stage state")
        current = self.state_of(stage)
        if current not in {StageState.pending, StageState.running}:
            raise ValueError(f"stage {stage!r} cannot settle from {current.value}")

        self._states[stage] = state
        duration_ms: int | None = None
        started = self._started.pop(stage, None)
        if started is not None:
            duration_ms = max(0, round((self._clock.monotonic() - started) * 1000))
            self._durations_ms[stage] = duration_ms
        self._publish(
            stage,
            "stage_end",
            state.value,
            message=message or f"{stage} {state.value}",
            duration_ms=duration_ms,
            output_count=output_count,
            error_category=error_category,
        )
        return state

    def settle_from_worker(
        self,
        stage: str,
        status: WorkerStatus | str,
        *,
        message: str = "",
        output_count: int | None = None,
    ) -> StageState:
        return self.settle(
            stage,
            stage_state_for(status),
            message=message,
            output_count=output_count,
        )

    def cancel(self, stage: str, *, message: str = "") -> StageState:
        return self.settle(
            stage,
            StageState.cancelled,
            message=message or f"{stage} cancelled",
            error_category="cancelled",
        )

    def cancel_run(self, *, message: str = "") -> TerminalState:
        """Cancel the run, settling any still-running stage as cancelled."""
        self._run_cancelled = True
        for stage, state in list(self._states.items()):
            if state is StageState.running:
                self.cancel(stage, message=message)
        self._publish(
            RUN_STAGE,
            "run_cancelled",
            TerminalState.cancelled.value,
            message=message or "run cancelled",
            error_category="cancelled",
        )
        return self.terminal_state()

    # -- internals ----------------------------------------------------------

    def _publish(
        self,
        stage: str,
        event_type: str,
        status: str,
        *,
        message: str = "",
        duration_ms: int | None = None,
        output_count: int | None = None,
        error_category: str | None = None,
    ) -> None:
        if self._emit is None:
            return
        self._emit(
            ExecutionEvent(
                timestamp=self._clock.now_utc(),
                run_id=self._context.run_id,
                run_mode=self._context.run_mode,
                stage=stage,
                event_type=event_type,
                status=status,
                duration_ms=duration_ms,
                output_count=output_count,
                error_category=error_category,
                message=message,
            )
        )


__all__ = [
    "RUN_STAGE",
    "SETTLED_STAGE_STATES",
    "STAGE_STATE_BY_WORKER_STATUS",
    "EventEmitter",
    "RunStateMachine",
    "StageState",
    "TerminalState",
    "derive_terminal_state",
    "stage_state_for",
]
