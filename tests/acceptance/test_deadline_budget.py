"""Gold gate for the minute-12 analysis stop and reserved finalize tail."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.fakes import FixedClock

from hoya_agent.orchestration.deadline import DeadlineManager, OptionalWork, Stage, plan_optional_work

pytestmark = pytest.mark.acceptance


def test_nonessential_work_is_surrendered_before_the_minute_12_stop() -> None:
    clock = FixedClock(datetime(2026, 5, 31, tzinfo=UTC), monotonic_value=1000.0)
    manager = DeadlineManager(clock, 900.0)
    clock.advance(719.0)

    assert manager.remaining() == pytest.approx(1.0)
    assert manager.can_start(reserve_seconds=manager.finalize_reserve_seconds) is False
    plan = plan_optional_work(
        [OptionalWork.optional_context, OptionalWork.counter_signal_second_search],
        remaining_seconds=1.0,
        default_cost_seconds=45.0,
    )
    assert plan.keep == ()
    assert plan.skipped == (
        OptionalWork.optional_context,
        OptionalWork.counter_signal_second_search,
    )
    assert manager.analysis_deadline == pytest.approx(1720.0)
    assert manager.run_deadline == pytest.approx(1900.0)
    assert manager.deadline_for(Stage.artifact) < manager.analysis_deadline
