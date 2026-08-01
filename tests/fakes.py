"""Reusable deterministic same-process fakes for owner-level tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from hoya_agent.models import (
    ExecutionEvent,
    RawSourceRecord,
    RunSummary,
    SourceResult,
    SourceStatus,
)
from hoya_agent.ports import StaticToolRegistry


class FixedClock:
    def __init__(self, now: datetime, monotonic_value: float = 0.0) -> None:
        if now.tzinfo is None or now.utcoffset() is None or now.utcoffset().total_seconds() != 0:
            raise ValueError("FixedClock requires a timezone-aware UTC datetime")
        self._now = now
        self._monotonic = monotonic_value

    def now_utc(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> None:
        """Move both readings forward without sleeping.

        Rejects a negative step so the monotonic reading can never go backwards,
        which would let a deadline test pass against impossible behaviour.
        """
        if seconds < 0:
            raise ValueError("FixedClock.advance() requires a non-negative step")
        self._now += timedelta(seconds=seconds)
        self._monotonic += seconds


class FakeLLM:
    def __init__(self, responses: list[BaseModel | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def converse_structured(self, **kwargs: Any) -> BaseModel:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("FakeLLM has no response configured")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _envelope(
    source_name: str,
    status: SourceStatus,
    data: object,
    fetched_at: datetime,
) -> SourceResult[Any]:
    """Build a normalized envelope, carrying failure as status rather than data."""
    failed = status is not SourceStatus.ok
    return SourceResult[Any](
        source_name=source_name,
        status=status,
        fetched_at=fetched_at,
        data=None if failed else data,
        error_category=status.value if failed else None,
    )


class FakeSourceAdapter:
    """Generic adapter fake returning a configurable SourceResult envelope."""

    def __init__(
        self,
        result: object = None,
        status: SourceStatus = SourceStatus.ok,
        fetched_at: datetime | None = None,
        source_name: str = "fake-source",
    ) -> None:
        self.result = result
        self.status = status
        self.source_name = source_name
        self.fetched_at = fetched_at or datetime(2026, 8, 1, tzinfo=UTC)
        self.calls: list[dict[str, object]] = []

    async def fetch(self, **params: object) -> SourceResult[Any]:
        self.calls.append(params)
        return _envelope(self.source_name, self.status, self.result, self.fetched_at)


class FakeResearchSourceAdapter(FakeSourceAdapter):
    """Research adapter fake yielding raw records inside the envelope."""

    def __init__(
        self,
        records: list[RawSourceRecord] | None = None,
        status: SourceStatus = SourceStatus.ok,
        fetched_at: datetime | None = None,
    ) -> None:
        super().__init__(
            result=list(records or []),
            status=status,
            fetched_at=fetched_at,
            source_name="fake-research",
        )

    async def fetch(self, **params: object) -> SourceResult[list[RawSourceRecord]]:
        self.calls.append(params)
        return _envelope(
            self.source_name, self.status, list(self.result or []), self.fetched_at
        )


class FakeMarketDataAdapter:
    """Market adapter fake exposing both named operations and the generic seam."""

    def __init__(
        self,
        bars: object = None,
        snapshot: object = None,
        status: SourceStatus = SourceStatus.ok,
        fetched_at: datetime | None = None,
    ) -> None:
        self.bars = bars if bars is not None else []
        self.snapshot = snapshot
        self.status = status
        self.fetched_at = fetched_at or datetime(2026, 8, 1, tzinfo=UTC)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def fetch_daily_bars(self, **params: object) -> SourceResult[Any]:
        self.calls.append(("fetch_daily_bars", params))
        return _envelope("fake-market", self.status, self.bars, self.fetched_at)

    async def fetch_snapshot(self, **params: object) -> SourceResult[Any]:
        self.calls.append(("fetch_snapshot", params))
        return _envelope("fake-market", self.status, self.snapshot, self.fetched_at)

    async def fetch(self, **params: object) -> SourceResult[Any]:
        return await self.fetch_daily_bars(**params)


class InMemoryProgressSink:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self.files: dict[tuple[str, str], object] = {}
        self.events: dict[str, list[ExecutionEvent]] = {}

    async def write_text(self, run_id: str, filename: str, content: str) -> str:
        self.files[(run_id, filename)] = content
        return f"memory://{run_id}/{filename}"

    async def write_json(self, run_id: str, filename: str, payload: object) -> str:
        self.files[(run_id, filename)] = payload
        return f"memory://{run_id}/{filename}"

    async def append_event(self, run_id: str, event: ExecutionEvent) -> str:
        self.events.setdefault(run_id, []).append(event)
        return f"memory://{run_id}/execution_log.jsonl"


class InMemoryRunPersistence:
    def __init__(self) -> None:
        self.summaries: dict[str, RunSummary] = {}
        self.artifact_references: dict[str, dict[str, str]] = {}

    async def save_summary(self, summary: RunSummary) -> None:
        self.summaries[summary.run_id] = summary

    async def get_summary(self, run_id: str) -> RunSummary | None:
        return self.summaries.get(run_id)

    async def save_artifact_references(self, run_id: str, references: Mapping[str, str]) -> None:
        self.artifact_references[run_id] = dict(references)


def fake_tool_registry(**operations: Any) -> StaticToolRegistry:
    return StaticToolRegistry(operations)


UTC_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
