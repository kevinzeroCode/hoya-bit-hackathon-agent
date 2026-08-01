from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    RawSourceRecord,
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


class ContractShapedResearch:
    async def run(self, *, plan, request, deadline):
        del plan, request, deadline
        record = RawSourceRecord(
            record_id="rss-001",
            source_name="CoinDesk",
            source_type=SourceType.news,
            source_url="https://www.coindesk.com/markets/example",
            asset=Asset.BTC,
            published_at=Clock().now_utc(),
            fetched_at=Clock().now_utc(),
            title="Bitcoin market update",
            content="Bitcoin market activity increased during the session.",
            query_or_parameters="feed=coindesk;lookback_days=14",
            metadata={
                "source_reference": "CoinDesk RSS item rss-001",
                "reliability": "medium",
                "independence_group": "coindesk.com",
            },
        )
        return SimpleNamespace(
            # This is the frozen Research Extraction contract: the LLM extracts
            # facts but does not assign source trust or provenance policy.
            drafts=[
                SimpleNamespace(
                    record_id="rss-001",
                    asset=Asset.BTC,
                    normalized_fact="Bitcoin market activity increased during the session.",
                    content_reference="CoinDesk RSS item rss-001",
                    # Even a richer model payload cannot upgrade source policy.
                    reliability="high",
                    independence_group="model-invented-group",
                )
            ],
            records=[record],
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


async def test_contract_shaped_research_draft_inherits_deterministic_source_policy() -> None:
    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        planner=OneStepPlanner(),
        research_agent=ContractShapedResearch(),
    ).execute(_context(), lambda event: None)

    news = [item for item in outcome.ledger.items if item.source_type is SourceType.news]
    assert len(news) == 1
    assert news[0].source_name == "CoinDesk"
    assert news[0].reliability.value == "medium"
    assert news[0].independence_group == "coindesk.com"


async def test_arbiter_failure_preserves_ledger_and_deterministic_fallback() -> None:
    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        arbiter=FailingArbiter(),
    ).execute(_context(), lambda event: None)

    assert outcome.ledger.items
    assert outcome.terminal_state is TerminalState.degraded
    assert any("deterministic fallback" in note for note in outcome.degradation_notes)

