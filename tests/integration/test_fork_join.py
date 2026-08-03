"""S4 fork-join: real overlap, one acquisition deadline, cancel-then-await.

Covers the wiring that `DeadlineManager` stage budgets and `RunStateMachine`
introduced: the Market and Research branches genuinely overlap in time, the
acquisition milestone bounds them both, and a branch cancelled at that milestone
never discards the sibling's evidence.

The cancellation case uses a deliberately tiny request deadline so the fake-free
part of the wait is milliseconds, not the competition's 270-second window.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunContext,
    RunMode,
    SourceType,
    StageState,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import (
    STAGE_MARKET,
    STAGE_RESEARCH,
    DeadlineAwarePipeline,
    PipelineOutcome,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, tzinfo=UTC)


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


def _context(*, deadline_seconds: int = 900) -> RunContext:
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        requested_at=NOW,
        analysis_as_of=NOW,
        deadline_seconds=deadline_seconds,
        run_mode=RunMode.rehearsal,
        run_id="run_20260531_000000_fj01",
    )
    return build_run_context(request, Clock())


def _ledger(context: RunContext) -> EvidenceLedger:
    return EvidenceLedger(
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        items=[
            EvidenceItem(
                evidence_id="ev_001",
                asset=Asset.BTC,
                source_type=SourceType.market,
                source_name="public_market_data",
                source_url="https://example.test/public_market_data",
                published_at=NOW,
                fetched_at=NOW,
                query_or_parameters="asset=BTC; window=14d",
                content_reference="2026-05-31 UTC close",
                normalized_fact="BTC 的 14 日報酬為 -4.88%（截至 2026-05-31 UTC）。",
                reliability=Reliability.high,
                independence_group="organizer-public-market-data",
                content_hash="a" * 64,
                is_cached=False,
                cache_time=None,
                is_stale=False,
            )
        ],
    )


class GatedMarket:
    """Signals its own start, then refuses to finish before Research has begun."""

    def __init__(self, mine: asyncio.Event, theirs: asyncio.Event) -> None:
        self._mine = mine
        self._theirs = theirs

    async def execute(self, context: RunContext, emit) -> PipelineOutcome:
        del emit
        self._mine.set()
        # Serial execution would leave this waiting forever.
        await asyncio.wait_for(self._theirs.wait(), timeout=2.0)
        return PipelineOutcome(
            ledger=_ledger(context),
            result=None,
            terminal_state=TerminalState.completed,
        )


class ImmediateMarket:
    async def execute(self, context: RunContext, emit) -> PipelineOutcome:
        del emit
        return PipelineOutcome(
            ledger=_ledger(context),
            result=None,
            terminal_state=TerminalState.completed,
        )


class FastPlanner:
    async def run(self, *, request, deadline):
        del request, deadline
        return object(), []


class RecordingPlanner:
    """A minimal but complete Planner double: real `planned_steps` shape plus
    `allowed_operations()`, so the Task 15 / G4 `plan_decision` event has real
    chosen/skipped operations to report (unlike `FastPlanner`'s bare object())."""

    def __init__(self, *, chosen: tuple[str, ...], allowed: tuple[str, ...]) -> None:
        self._chosen = chosen
        self._allowed = allowed

    def allowed_operations(self) -> tuple[str, ...]:
        return self._allowed

    async def run(self, *, request, deadline):
        del request, deadline
        steps = [
            type("Step", (), {"tool_operation": op, "rationale": f"question needs {op}"})()
            for op in self._chosen
        ]
        plan = type("Plan", (), {"planned_steps": steps})()
        return plan, []


class GatedResearch:
    def __init__(self, mine: asyncio.Event, theirs: asyncio.Event) -> None:
        self._mine = mine
        self._theirs = theirs

    async def run(self, *, plan, request, deadline):
        del plan, request, deadline
        self._mine.set()
        await asyncio.wait_for(self._theirs.wait(), timeout=2.0)
        return type("Outcome", (), {"drafts": [], "degradation_events": []})()


class NeverFinishingResearch:
    def __init__(self) -> None:
        self.cancelled = False

    async def run(self, *, plan, request, deadline):
        del plan, request, deadline
        try:
            await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            self.cancelled = True
            raise  # never suppress cancellation
        return None


async def test_market_and_research_overlap_in_time() -> None:
    market_started = asyncio.Event()
    research_started = asyncio.Event()
    context = _context()

    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=GatedMarket(market_started, research_started),
        planner=FastPlanner(),
        research_agent=GatedResearch(research_started, market_started),
    ).execute(context, lambda event: None)

    assert market_started.is_set() and research_started.is_set()
    # Either branch waiting for the other would have failed had they run serially.
    assert not [note for note in outcome.degradation_notes if "分支" in note]
    assert outcome.ledger.items, "the market branch completed inside the gather window"


async def test_a_branch_cancelled_at_the_gather_deadline_keeps_the_sibling_evidence() -> None:
    # 1-second request: 0.5 s analysis window, so the gather milestone is ~188 ms.
    context = _context(deadline_seconds=1)
    research = NeverFinishingResearch()
    events = []

    outcome = await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=ImmediateMarket(),
        planner=FastPlanner(),
        research_agent=research,
    ).execute(context, events.append)

    assert research.cancelled, "the unfinished branch must be cancelled, not abandoned"
    assert [item.evidence_id for item in outcome.ledger.items] == ["ev_001"]
    assert outcome.terminal_state is TerminalState.degraded
    assert any("研究分支" in note for note in outcome.degradation_notes)

    settled = {
        event.stage: event.status for event in events if event.event_type == "stage_end"
    }
    assert settled[STAGE_MARKET] == StageState.completed.value
    assert settled[STAGE_RESEARCH] == StageState.cancelled.value


async def test_no_child_task_survives_the_gather_stage() -> None:
    context = _context(deadline_seconds=1)

    await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=ImmediateMarket(),
        planner=FastPlanner(),
        research_agent=NeverFinishingResearch(),
    ).execute(context, lambda event: None)

    leaked = [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and not task.done()
    ]
    assert leaked == [], f"pending tasks leaked into the next stage: {leaked}"


async def test_plan_decision_event_names_chosen_and_skipped_operations() -> None:
    """Task 15 / G4: the Planner's per-question operation choice must be a
    judge-legible execution_log.jsonl event, not something only visible by
    diffing the ledger afterward."""
    context = _context()
    events = []

    await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=ImmediateMarket(),
        planner=RecordingPlanner(
            chosen=("binance.klines",),
            allowed=("binance.klines", "cryptopanic.posts", "official_announcements"),
        ),
    ).execute(context, events.append)

    decisions = [e for e in events if e.event_type == "plan_decision"]
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.stage == "planner"
    assert decision.output_count == 1
    assert "binance.klines" in decision.message
    assert "cryptopanic.posts" in decision.message  # named as skipped, not silently omitted
    assert "official_announcements" in decision.message
    assert "question needs binance.klines" in decision.message  # the model's own rationale


async def test_plan_decision_event_reflects_a_different_question_choosing_differently() -> None:
    """Proves the visualization reflects genuine variation, not a static label:
    two different chosen sets produce two different `plan_decision` messages."""
    context = _context()
    allowed = ("binance.klines", "cryptopanic.posts", "official_announcements")

    async def _run(chosen: tuple[str, ...]) -> str:
        events = []
        await DeadlineAwarePipeline(
            clock=Clock(),
            market_pipeline=ImmediateMarket(),
            planner=RecordingPlanner(chosen=chosen, allowed=allowed),
        ).execute(context, events.append)
        return next(e.message for e in events if e.event_type == "plan_decision")

    sentiment_question = await _run(("cryptopanic.posts",))
    official_question = await _run(("binance.klines", "official_announcements"))

    assert sentiment_question != official_question
    assert "cryptopanic.posts" in sentiment_question
    assert "official_announcements" not in sentiment_question.split("略過")[0]
    assert "official_announcements" in official_question
