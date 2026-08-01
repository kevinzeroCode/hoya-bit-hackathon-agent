"""Typed same-process boundaries shared by all HOYA owners.

These protocols reserve replaceable seams without introducing a database,
queue, broker, remote registry, service boundary, or provider-specific type.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from hoya_agent.models import (
    Asset,
    ExecutionEvent,
    RawSourceRecord,
    RunContext,
    RunSummary,
    SourceResult,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
SourceT = TypeVar("SourceT", covariant=True)
ToolOperation = Callable[..., Awaitable[object]]


@runtime_checkable
class Clock(Protocol):
    def now_utc(self) -> datetime: ...

    def monotonic(self) -> float: ...


@runtime_checkable
class LLMClient(Protocol):
    async def converse_structured(
        self,
        *,
        operation: str,
        messages: Sequence[Mapping[str, Any]],
        schema: type[ModelT],
        max_tokens: int,
        deadline: float,
        system_prompt: str = "",
    ) -> ModelT: ...


@runtime_checkable
class SourceAdapter(Protocol[SourceT]):
    """Generic external-source boundary (design.md §4.4, §8.7).

    Every adapter returns the normalized :class:`SourceResult` envelope rather
    than a bare payload, so an expected provider failure travels as data and one
    failing source degrades a branch instead of killing the run.
    """

    async def fetch(
        self, *, context: RunContext, **params: object
    ) -> SourceResult[SourceT]: ...


@runtime_checkable
class MarketDataAdapter(Protocol):
    """Deterministic market-data boundary; a ``SourceAdapter`` specialization.

    The bar/snapshot payload models belong to the market-data task, so the
    envelope payload stays open here rather than pre-empting that owner.
    """

    async def fetch_daily_bars(
        self,
        *,
        asset: Asset,
        start: date,
        end: date,
        context: RunContext,
    ) -> SourceResult[object]: ...

    async def fetch_snapshot(
        self, *, asset: Asset, context: RunContext
    ) -> SourceResult[object]: ...

    async def fetch(
        self, *, context: RunContext, **params: object
    ) -> SourceResult[object]: ...


@runtime_checkable
class ResearchSourceAdapter(Protocol):
    """Research boundary; a ``SourceAdapter`` specialization over raw records."""

    async def fetch(
        self,
        *,
        context: RunContext,
        **params: object,
    ) -> SourceResult[list[RawSourceRecord]]: ...


class ProgressSink(Protocol):
    async def publish(self, event: ExecutionEvent) -> None: ...


class ArtifactStore(Protocol):
    async def write_text(self, run_id: str, filename: str, content: str) -> str: ...

    async def write_json(self, run_id: str, filename: str, payload: object) -> str: ...

    async def append_event(self, run_id: str, event: ExecutionEvent) -> str: ...


class PersistencePort(Protocol):
    """Future-facing port only; S1 intentionally supplies no persistent backend."""

    async def save_summary(self, summary: RunSummary) -> None: ...

    async def get_summary(self, run_id: str) -> RunSummary | None: ...

    async def save_artifact_references(self, run_id: str, references: Mapping[str, str]) -> None: ...


# Descriptive alias retained for callers that prefer the domain-specific name.
RunPersistence = PersistencePort


class ToolRegistry(Protocol):
    def operations(self) -> tuple[str, ...]: ...

    def is_allowed(self, operation: str) -> bool: ...

    async def invoke(self, operation: str, **params: object) -> object: ...


class StaticToolRegistry:
    """Immutable, configuration-backed map of finite local operations."""

    def __init__(self, operations: Mapping[str, ToolOperation]) -> None:
        copied: dict[str, ToolOperation] = {}
        for name, handler in operations.items():
            normalized = name.strip()
            if not normalized:
                raise ValueError("tool operation names must not be blank")
            if normalized in copied:
                raise ValueError(f"duplicate tool operation: {normalized}")
            if not callable(handler):
                raise TypeError(f"tool operation {normalized!r} must be callable")
            copied[normalized] = handler
        self._operations = MappingProxyType(copied)
        self._operation_names = tuple(copied)

    def operations(self) -> tuple[str, ...]:
        return self._operation_names

    def is_allowed(self, operation: str) -> bool:
        return operation in self._operations

    async def invoke(self, operation: str, **params: object) -> object:
        if not self.is_allowed(operation):
            raise PermissionError(f"operation is not allowlisted: {operation}")
        return await self._operations[operation](**params)
