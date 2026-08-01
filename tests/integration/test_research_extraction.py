"""One research article reaches the ledger as several traceable Evidence items.

The bounded extraction call proposes wording; the pipeline completes provenance
deterministically. This closes the S6 gap where extracted drafts were rejected at
the Evidence stage because they lacked contract fields the model must not supply.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    EvidenceLedger,
    RawSourceRecord,
    Reliability,
    RunContext,
    RunMode,
    SourceType,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, PipelineOutcome
from hoya_agent.reasoning.research_extractor import ExtractedFact

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, tzinfo=UTC)
PUBLISHED = datetime(2026, 5, 30, tzinfo=UTC)


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


class EmptyMarket:
    """No market data — the research branch alone must reach the ledger."""

    async def execute(self, context: RunContext, emit) -> PipelineOutcome:
        del emit
        return PipelineOutcome(
            ledger=EvidenceLedger(
                run_id=context.run_id,
                analysis_as_of=context.analysis_as_of,
                run_mode=context.run_mode,
                items=[],
                degradation_events=[],
            ),
            result=None,
            terminal_state=TerminalState.degraded,
            degradation_notes=["市場分支未提供證據（測試情境）。"],
        )


class Planner:
    async def run(self, *, request, deadline):
        del request, deadline
        return object(), []


RECORD = RawSourceRecord(
    record_id="coindesk-abc123",
    source_name="CoinDesk",
    source_type=SourceType.news,
    source_url="https://www.coindesk.com/markets/story",
    asset=Asset.BTC,
    published_at=PUBLISHED,
    fetched_at=NOW,
    title="ETF outflows continue",
    content="Spot ETFs recorded outflows over the week while exchange balances fell.",
    query_or_parameters="rss feed=https://www.coindesk.com/arc/outboundfeeds/rss/",
)


class MultiFactResearch:
    """Stands in for the frozen ResearchAgent's post-LLM outcome shape."""

    class Outcome:
        status = "completed"
        records = [RECORD]
        degradation_events: list[str] = []
        executed_operations = ["fetch_rss_news"]
        drafts = [
            ExtractedFact(
                record_id="coindesk-abc123",
                normalized_fact="現貨 ETF 於該週出現淨流出。",
                event_type="etf_flow",
                asset=Asset.BTC,
            ),
            ExtractedFact(
                record_id="coindesk-abc123",
                normalized_fact="同期交易所餘額下降。",
                event_type="etf_flow",
                asset=Asset.BTC,
            ),
            ExtractedFact(
                record_id="never-fetched",
                normalized_fact="捏造的事實。",
                event_type="other",
                asset=Asset.BTC,
            ),
        ]

    async def run(self, *, plan, request, deadline):
        del plan, request, deadline
        return self.Outcome()


def _context() -> RunContext:
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        requested_at=NOW,
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_rx01",
    )
    return build_run_context(request, Clock())


async def _run() -> PipelineOutcome:
    return await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=EmptyMarket(),
        planner=Planner(),
        research_agent=MultiFactResearch(),
    ).execute(_context(), lambda event: None)


async def test_one_article_produces_several_evidence_items() -> None:
    outcome = await _run()

    facts = [item.normalized_fact for item in outcome.ledger.items]
    assert "現貨 ETF 於該週出現淨流出。" in facts
    assert "同期交易所餘額下降。" in facts
    assert len([item for item in outcome.ledger.items if item.source_name == "CoinDesk"]) == 2


async def test_extracted_items_take_reliability_from_static_policy() -> None:
    outcome = await _run()

    news = [item for item in outcome.ledger.items if item.source_type is SourceType.news]
    assert news, "extracted news evidence must reach the ledger"
    # Feed item only, original page not fetched → `low`, never upgraded by the model.
    assert all(item.reliability is Reliability.low for item in news)
    assert all(item.independence_group == "coindesk.com" for item in news)


async def test_fact_citing_an_unfetched_record_is_dropped_and_disclosed() -> None:
    outcome = await _run()

    assert all("捏造" not in item.normalized_fact for item in outcome.ledger.items)
    assert any("never-fetched" in note for note in outcome.degradation_notes)


async def test_every_extracted_item_keeps_a_traceable_source_reference() -> None:
    outcome = await _run()

    for item in outcome.ledger.items:
        assert item.content_reference.strip()
        assert item.query_or_parameters.strip()
        assert item.fetched_at is not None
