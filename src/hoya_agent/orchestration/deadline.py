"""Monotonic deadline budgeting for the H2-Lite stage sequence."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from hoya_agent.ports import Clock

T = TypeVar("T")


class DeadlineExceeded(TimeoutError):
    pass


class DeadlineManager:
    def __init__(self, clock: Clock, deadline_monotonic: float) -> None:
        self._clock = clock
        self.deadline_monotonic = deadline_monotonic

    def remaining(self) -> float:
        return max(0.0, self.deadline_monotonic - self._clock.monotonic())

    def can_start(self, *, reserve_seconds: float = 0.0) -> bool:
        return self.remaining() > reserve_seconds

    async def run(
        self,
        awaitable: Awaitable[T],
        *,
        timeout_seconds: float | None = None,
    ) -> T:
        budget = self.remaining()
        if timeout_seconds is not None:
            budget = min(budget, timeout_seconds)
        if budget <= 0:
            if hasattr(awaitable, "close"):
                awaitable.close()  # type: ignore[attr-defined]
            raise DeadlineExceeded("run deadline exhausted")
        try:
            return await asyncio.wait_for(awaitable, timeout=budget)
        except TimeoutError as exc:
            raise DeadlineExceeded("stage deadline exhausted") from exc
