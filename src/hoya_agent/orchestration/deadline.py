"""Monotonic deadline budgeting for the H2-Lite stage sequence.

The absolute milestones for a 900-second run are fixed by `docs/Features.md` §5.6
(from `design.md` §6.1): Planner 30 s, parallel acquisition 270 s, Evidence
Processor 360 s, Arbiter + render 510 s, artifact verification target 630 s and
the analysis hard stop at 720 s (minute 12).

They are stored here as offsets into a *reference* 720-second analysis window and
re-scaled onto whatever window the request actually affords. A rehearsal run with
`deadline_seconds=300` therefore gets proportionally smaller stages instead of
silently keeping competition-sized budgets, which would let one stage eat the
whole run.

The tail of every run belongs to the deterministic, network-free finalize: 20% of
the request deadline, at least 60 seconds when the deadline can afford it, and
never more than half the run. For the competition's 900 seconds that reserve is
180 seconds, which is exactly why the analysis hard stop lands on 720.

`time.monotonic()` drives every budget in this module. UTC wall-clock time is only
ever persisted, never used for arithmetic.

This module also owns the fixed optional-work skip order, because deciding what to
surrender is a function of remaining time. Keeping the order in one place means no
caller can invent a different one.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TypeVar

from hoya_agent.models import RunContext
from hoya_agent.ports import Clock

T = TypeVar("T")

ANALYSIS_HARD_STOP_SECONDS = 720.0
FINALIZE_RESERVE_FRACTION = 0.2
FINALIZE_RESERVE_MIN_SECONDS = 60.0
_REFERENCE_ANALYSIS_WINDOW_SECONDS = 720.0


class Stage(str, Enum):
    """Budget milestones. These are *not* execution-log stage names.

    Log stages are finer grained (`market_worker`, `research_agent`, ...) and are
    owned by `run_state.py`; several of them share one budget milestone.
    """

    planner = "planner"
    gather = "gather"
    evidence = "evidence_processor"
    reason = "reason"
    artifact = "artifact"


STAGE_MILESTONE_SECONDS: Mapping[Stage, float] = MappingProxyType(
    {
        Stage.planner: 30.0,
        Stage.gather: 270.0,
        Stage.evidence: 360.0,
        Stage.reason: 510.0,
        Stage.artifact: 630.0,
    }
)


class DeadlineExceeded(TimeoutError):
    pass


class OptionalWork(str, Enum):
    """Work that may be surrendered under time pressure.

    `conditional_debate` is H3. It is permanently disabled in the MVP, so nothing
    ever schedules it and it is therefore never actually skipped at runtime. It
    stays in this vocabulary because the approved order names it first, and
    removing it would let a later reader believe the order starts with optional
    context.
    """

    conditional_debate = "conditional_debate"
    optional_context = "optional_context"
    counter_signal_second_search = "counter_signal_second_search"


# The fixed order from competition-rules.md: this is the order in which work is
# *given up*, so the counter-signal second search is the last thing surrendered.
# Finding an opposing signal matters more to report honesty than extra context.
SKIP_ORDER: tuple[OptionalWork, ...] = (
    OptionalWork.conditional_debate,
    OptionalWork.optional_context,
    OptionalWork.counter_signal_second_search,
)

_SKIP_NOTES: Mapping[OptionalWork, str] = MappingProxyType(
    {
        OptionalWork.conditional_debate: "時間不足，略過 H3 條件式辯論（MVP 本就停用，未執行）。",
        OptionalWork.optional_context: "時間不足，略過 optional context adapter，該來源缺口已揭露。",
        OptionalWork.counter_signal_second_search: (
            "時間不足，略過反方訊號二次搜尋；本次未再尋找額外反方證據，此限制已揭露。"
        ),
    }
)


def skip_note(work: OptionalWork) -> str:
    """The zh-Hant disclosure line for surrendering ``work``."""
    return _SKIP_NOTES[work]


@dataclass(frozen=True)
class OptionalWorkPlan:
    """What optional work survives this run's remaining acquisition window."""

    keep: tuple[OptionalWork, ...] = ()
    skipped: tuple[OptionalWork, ...] = ()
    reasons: tuple[str, ...] = ()


def _as_optional_work(value: OptionalWork | str) -> OptionalWork:
    if isinstance(value, OptionalWork):
        return value
    try:
        return OptionalWork(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown optional work {value!r}") from exc


def plan_optional_work(
    pending: Iterable[OptionalWork | str],
    *,
    remaining_seconds: float,
    default_cost_seconds: float,
    cost_seconds: Mapping[OptionalWork, float] | None = None,
) -> OptionalWorkPlan:
    """Decide which optional work fits, surrendering it in the fixed skip order.

    Costs are supplied by the caller — usually the configured per-call timeout
    times the number of planned calls — so no estimate is invented here. Items are
    dropped from the front of `SKIP_ORDER` until the remaining ones fit.
    """
    ordered = [work for work in SKIP_ORDER if work in {_as_optional_work(p) for p in pending}]
    costs = dict(cost_seconds or {})

    def cost_of(work: OptionalWork) -> float:
        return float(costs.get(work, default_cost_seconds))

    keep = list(ordered)
    skipped: list[OptionalWork] = []
    budget = max(0.0, float(remaining_seconds))
    while keep and sum(cost_of(work) for work in keep) > budget:
        skipped.append(keep.pop(0))

    return OptionalWorkPlan(
        keep=tuple(keep),
        skipped=tuple(skipped),
        reasons=tuple(skip_note(work) for work in skipped),
    )


def _finalize_reserve(total_seconds: float) -> float:
    """Seconds withheld at the end of the run for the deterministic finalize."""
    if total_seconds <= 0.0:
        return 0.0
    return max(
        total_seconds * FINALIZE_RESERVE_FRACTION,
        # The 60-second floor must never starve the analysis entirely.
        min(FINALIZE_RESERVE_MIN_SECONDS, total_seconds * 0.5),
    )


class DeadlineManager:
    """Owns every stage budget for one run.

    Adapters and stages receive a budget; they never extend one.
    """

    def __init__(
        self,
        clock: Clock,
        total_seconds: float,
        *,
        started_monotonic: float | None = None,
        analysis_hard_stop_seconds: float = ANALYSIS_HARD_STOP_SECONDS,
    ) -> None:
        self._clock = clock
        self.started_monotonic = (
            clock.monotonic() if started_monotonic is None else float(started_monotonic)
        )
        self.total_seconds = max(0.0, float(total_seconds))
        self.finalize_reserve_seconds = _finalize_reserve(self.total_seconds)
        self.analysis_window_seconds = max(
            0.0,
            min(
                self.total_seconds - self.finalize_reserve_seconds,
                float(analysis_hard_stop_seconds),
            ),
        )
        self.analysis_deadline = self.started_monotonic + self.analysis_window_seconds
        self.run_deadline = self.started_monotonic + self.total_seconds

    @classmethod
    def for_run(cls, context: RunContext, clock: Clock) -> DeadlineManager:
        """Build from the frozen run context so the run start is not re-sampled."""
        return cls(
            clock,
            context.deadline_monotonic - context.started_monotonic,
            started_monotonic=context.started_monotonic,
        )

    # -- budgets ------------------------------------------------------------

    def deadline_for(self, stage: Stage | None = None) -> float:
        """Absolute monotonic deadline for ``stage``, or for the whole analysis."""
        if stage is None:
            return self.analysis_deadline
        fraction = STAGE_MILESTONE_SECONDS[stage] / _REFERENCE_ANALYSIS_WINDOW_SECONDS
        scaled = self.started_monotonic + self.analysis_window_seconds * fraction
        return min(scaled, self.analysis_deadline)

    def remaining(self, stage: Stage | None = None) -> float:
        return max(0.0, self.deadline_for(stage) - self._clock.monotonic())

    def budget_for(self, stage: Stage | None = None, *, timeout_seconds: float | None = None) -> float:
        """Remaining stage time, clamped by a per-call timeout when one applies."""
        budget = self.remaining(stage)
        if timeout_seconds is not None:
            budget = min(budget, float(timeout_seconds))
        return budget

    def can_start(self, *, reserve_seconds: float = 0.0) -> bool:
        return self.remaining() > reserve_seconds

    def budget_seconds(self) -> dict[str, float]:
        """Offsets from run start, for logging and the run-config snapshot."""
        budgets = {
            stage.value: round(self.deadline_for(stage) - self.started_monotonic, 3)
            for stage in Stage
        }
        budgets["analysis_hard_stop"] = round(self.analysis_window_seconds, 3)
        budgets["finalize_reserve"] = round(self.finalize_reserve_seconds, 3)
        return budgets

    # -- execution ----------------------------------------------------------

    async def run(
        self,
        awaitable: Awaitable[T],
        *,
        stage: Stage | None = None,
        timeout_seconds: float | None = None,
    ) -> T:
        """Await under the stage budget, cancelling the call when it expires."""
        budget = self.budget_for(stage, timeout_seconds=timeout_seconds)
        if budget <= 0:
            close = getattr(awaitable, "close", None)
            if close is not None:
                # Never leave an un-awaited coroutine behind for the next stage.
                close()
            raise DeadlineExceeded(
                f"{'run' if stage is None else stage.value} deadline exhausted before start"
            )
        try:
            return await asyncio.wait_for(awaitable, timeout=budget)
        except TimeoutError as exc:
            raise DeadlineExceeded(
                f"{'run' if stage is None else stage.value} deadline exhausted"
            ) from exc


__all__ = [
    "ANALYSIS_HARD_STOP_SECONDS",
    "FINALIZE_RESERVE_FRACTION",
    "FINALIZE_RESERVE_MIN_SECONDS",
    "SKIP_ORDER",
    "STAGE_MILESTONE_SECONDS",
    "DeadlineExceeded",
    "DeadlineManager",
    "OptionalWork",
    "OptionalWorkPlan",
    "Stage",
    "plan_optional_work",
    "skip_note",
]
