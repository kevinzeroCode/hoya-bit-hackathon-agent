from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    ResearchPlan,
    ResearchStep,
    RunMode,
    SourceType,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, OrganizerCsvPipeline

pytestmark = pytest.mark.integration


class Clock:
    def now_utc(self) -> datetime:
        return datetime(2026, 5, 31, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1000.0


class FailingMarket:
    async def execute(self, context, emit):
        del context, emit
        raise TimeoutError("injected market timeout")


async def test_market_timeout_degrades_to_an_honest_empty_ledger() -> None:
    request = AnalysisRequest(
        question="BTC 市場狀態？",
        assets=[Asset.BTC],
        requested_at=Clock().now_utc(),
        analysis_as_of=Clock().now_utc(),
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_deg1",
    )
    context = build_run_context(request, Clock())
    events = []
    outcome = await DeadlineAwarePipeline(
        clock=Clock(), market_pipeline=FailingMarket()
    ).execute(context, events.append)

    assert outcome.terminal_state is TerminalState.degraded
    assert outcome.result is None
    assert outcome.ledger.items == []
    assert outcome.ledger.degradation_events
    assert any("市場分支失敗" in note for note in outcome.degradation_notes)


class OneStepPlanner:
    async def run(self, *, request, deadline):
        del deadline
        return (
            ResearchPlan(
                assets=[Asset(asset) for asset in request.assets],
                question_summary=request.question,
                required_evidence_types=[SourceType.news],
                planned_steps=[
                    ResearchStep(
                        step_id="step_01",
                        tool_operation="baseline_news",
                        rationale="baseline research",
                    )
                ],
            ),
            [],
        )


class FailingResearch:
    async def run(self, *, plan, request, deadline):
        del plan, request, deadline
        raise TimeoutError("injected research timeout")


class MalformedResearch:
    async def run(self, *, plan, request, deadline):
        del plan, request, deadline
        return SimpleNamespace(
            drafts=[SimpleNamespace(source_type=None)],
            degradation_events=[],
        )


class FailingArbiter:
    async def run(self, **kwargs):
        del kwargs
        raise ValueError("injected invalid schema after repair")


def _context() -> object:
    request = AnalysisRequest(
        question="BTC 市場狀態？",
        assets=[Asset.BTC],
        requested_at=Clock().now_utc(),
        analysis_as_of=Clock().now_utc(),
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_deg2",
    )
    return build_run_context(request, Clock())


async def test_research_timeout_keeps_market_evidence_and_degrades() -> None:
    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        planner=OneStepPlanner(),
        research_agent=FailingResearch(),
    ).execute(_context(), lambda event: None)

    assert outcome.ledger.items
    assert outcome.terminal_state is TerminalState.degraded
    assert any("研究分支失敗" in note for note in outcome.degradation_notes)


async def test_invalid_research_draft_is_rejected_before_arbiter() -> None:
    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        planner=OneStepPlanner(),
        research_agent=MalformedResearch(),
    ).execute(_context(), lambda event: None)

    assert outcome.ledger.items
    assert all(item.source_type is not SourceType.news for item in outcome.ledger.items)
    assert any("Evidence 契約" in note for note in outcome.degradation_notes)


async def test_arbiter_failure_preserves_ledger_and_deterministic_fallback() -> None:
    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        arbiter=FailingArbiter(),
    ).execute(_context(), lambda event: None)

    assert outcome.ledger.items
    assert outcome.terminal_state is TerminalState.degraded
    assert any("deterministic fallback" in note for note in outcome.degradation_notes)
