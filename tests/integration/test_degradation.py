from datetime import UTC, datetime

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import AnalysisRequest, Asset, RunMode, TerminalState
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline

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
