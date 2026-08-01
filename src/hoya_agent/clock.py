"""Injectable UTC and monotonic clocks for deterministic orchestration."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from hoya_agent.models import AnalysisRequest, RunContext, RunMode
from hoya_agent.ports import Clock


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


def build_run_context(request: AnalysisRequest, clock: Clock) -> RunContext:
    """Create immutable timing state, freezing the cutoff from ``clock``.

    Cutoff policy (evidence-contracts.md §2):

    - ``official`` always takes the injected clock reading and discards any
      supplied cutoff, so an official run's cutoff cannot be chosen by the
      caller;
    - ``rehearsal``/``demo`` keep an explicitly supplied cutoff so a past run can
      be reproduced;
    - any mode that omits the cutoff also takes the injected clock reading.

    The result always carries a real strict-UTC cutoff, and both the returned
    context and its embedded request are immutable thereafter.
    """

    started_at = clock.now_utc()
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("Clock.now_utc() must return a timezone-aware UTC datetime")
    if started_at.utcoffset().total_seconds() != 0:
        raise ValueError("Clock.now_utc() must return UTC")

    effective_request = request
    if request.run_mode is RunMode.official or request.analysis_as_of is None:
        effective_request = request.model_copy(update={"analysis_as_of": started_at})

    started_monotonic = clock.monotonic()
    return RunContext(
        run_id=effective_request.run_id,
        request=effective_request,
        analysis_as_of=effective_request.analysis_as_of,
        started_at=started_at,
        started_monotonic=started_monotonic,
        deadline_monotonic=started_monotonic + effective_request.deadline_seconds,
    )
