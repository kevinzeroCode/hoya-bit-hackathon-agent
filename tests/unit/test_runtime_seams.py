from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    RawSourceRecord,
    ResearchPlan,
    ResearchStep,
    RunMode,
    SourceType,
    WorkerResult,
    WorkerStatus,
)
from hoya_agent.ports import StaticToolRegistry


class FixedClock:
    def __init__(self, now: datetime, monotonic: float = 100.0) -> None:
        self._now = now
        self._monotonic = monotonic

    def now_utc(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic


def make_request(mode: RunMode, analysis_as_of: datetime) -> AnalysisRequest:
    return AnalysisRequest(
        question="分析 BTC 市場",
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 0, tzinfo=UTC),
        analysis_as_of=analysis_as_of,
        deadline_seconds=900,
        run_mode=mode,
        run_id="run_20260801_120000_test",
    )


def test_official_context_freezes_cutoff_from_injected_clock() -> None:
    clock_now = datetime(2026, 8, 1, 4, 5, tzinfo=UTC)
    supplied = datetime(2020, 1, 1, tzinfo=UTC)

    context = build_run_context(make_request(RunMode.official, supplied), FixedClock(clock_now))

    assert context.analysis_as_of == clock_now
    assert context.request.analysis_as_of == clock_now
    assert context.deadline_monotonic == 1000.0
    with pytest.raises(ValidationError):
        context.analysis_as_of = supplied


def test_rehearsal_context_preserves_requested_cutoff() -> None:
    cutoff = datetime(2026, 7, 1, tzinfo=UTC)
    context = build_run_context(
        make_request(RunMode.rehearsal, cutoff),
        FixedClock(datetime(2026, 8, 1, tzinfo=UTC)),
    )
    assert context.analysis_as_of == cutoff


def test_raw_source_record_requires_utc_and_nonblank_content() -> None:
    with pytest.raises(ValidationError):
        RawSourceRecord(
            record_id="rec_001",
            source_name="Example",
            source_type=SourceType.news,
            source_url="https://example.com/story",
            published_at=None,
            fetched_at=datetime(2026, 8, 1),
            title="title",
            content="content",
            query_or_parameters="BTC",
        )


def test_research_plan_matches_reasoning_contract() -> None:
    plan = ResearchPlan(
        plan_version="planner-v1",
        assets=[Asset.BTC],
        question_summary="BTC 市場",
        lookback_days=14,
        required_evidence_types=[SourceType.market, SourceType.news],
        planned_steps=[
            ResearchStep(step_id="s1", tool_operation="market.daily", rationale="價格證據")
        ],
    )
    assert plan.planned_steps[0].tool_operation == "market.daily"


def test_worker_result_has_only_terminal_worker_statuses() -> None:
    result = WorkerResult(status=WorkerStatus.completed)
    assert result.status is WorkerStatus.completed
    with pytest.raises(ValidationError):
        WorkerResult(status="cancelled")


@pytest.mark.asyncio
async def test_static_tool_registry_rejects_unallowlisted_operation_before_invocation() -> None:
    calls: list[dict[str, object]] = []

    async def fetch(**params: object) -> object:
        calls.append(params)
        return ["ok"]

    registry = StaticToolRegistry({"market.daily": fetch})

    with pytest.raises(PermissionError):
        await registry.invoke("evil.dynamic", payload="external content")
    assert calls == []
    assert registry.operations() == ("market.daily",)


@pytest.mark.asyncio
async def test_static_tool_registry_cannot_be_mutated_by_retrieved_content() -> None:
    async def fetch(**params: object) -> object:
        params["register"] = "evil.dynamic"
        return params

    source_mapping = {"market.daily": fetch}
    registry = StaticToolRegistry(source_mapping)
    source_mapping["evil.dynamic"] = fetch

    await registry.invoke("market.daily", register="ignored")
    assert registry.operations() == ("market.daily",)
    assert not registry.is_allowed("evil.dynamic")

