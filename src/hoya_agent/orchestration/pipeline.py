"""Stage order and the deterministic evidence pipeline.

Task 3 extends this module with `DeadlineManager` wiring and Market/Research
fork-join. What lives here today is the first increment: the seam that lets the
S2 vertical slice run on the real deterministic market evidence that landed on
`main`, instead of on committed fixtures.

One provisional coupling remains explicit and contained:

* `to_contract_ledger` bridges `evidence/types.py` (the data/evidence layer's
  frozen dataclasses) to `models.py` (the canonical Pydantic contracts). Both
  representations currently exist on `main`; when the dataclasses retire, this
  function retires with them.

No LLM and no network live here. The organizer CSV is a local file, so this whole
path runs offline.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from hoya_agent.adapters.organizer_csv import default_data_dir, load_organizer_csv
from hoya_agent.conclusion_guards import ensure_honest_insufficiency
from hoya_agent.data.market_worker import build_market_evidence
from hoya_agent.data.price_analysis import build_comparison_evidence
from hoya_agent.data.regime import build_regime_evidence, classify_market_regime
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.drafts import MetricValue, PendingEvidence
from hoya_agent.evidence.grounding import ground_drafts
from hoya_agent.evidence.ledger import build_conflict_indicators
from hoya_agent.evidence.processor import build_ledger
from hoya_agent.evidence.trust import build_trust_scorecards
from hoya_agent.models import (
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    DataMode,
    DegradationEvent,
    EvidenceItem,
    EvidenceLedger,
    ExecutionEvent,
    InvalidationCondition,
    InvalidationOperator,
    MarketContext,
    Reliability,
    RunContext,
    Stance,
    TerminalState,
    TimeRange,
)
from hoya_agent.orchestration.deadline import (
    DeadlineManager,
    OptionalWork,
    Stage,
    plan_optional_work,
    skip_note,
)
from hoya_agent.orchestration.run_state import EventEmitter, RunStateMachine, StageState
from hoya_agent.ports import Clock
from hoya_agent.reasoning.arbiter import apply_confidence_caps
from hoya_agent.reasoning.arbiter_output import (
    ArbiterOutput,
    ledger_view,
    project_to_analysis_result,
)
from hoya_agent.reasoning.research_extractor import complete_extracted_drafts


@dataclass
class PipelineOutcome:
    ledger: EvidenceLedger
    result: AnalysisResult | None
    terminal_state: TerminalState = TerminalState.completed
    degradation_notes: list[str] = field(default_factory=list)
    stage_durations_ms: dict[str, int] = field(default_factory=dict)
    effective_data_mode: DataMode | None = None


@dataclass(frozen=True)
class ReasoningRequest:
    """String-valued request view for the frozen S7 reasoning boundary."""

    run_id: str
    question: str
    assets: tuple[str, ...]
    analysis_as_of: datetime


@runtime_checkable
class AnalysisPipeline(Protocol):
    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome: ...

BarLoader = Callable[[str], Sequence[MarketBar]]

STAGE_PLANNER = "planner"
STAGE_MARKET = "market_worker"
STAGE_RESEARCH = "research_agent"
STAGE_EVIDENCE = "evidence_processor"
STAGE_ARBITER = "arbiter"

# Below this the single Arbiter call cannot finish, and skipping it protects the
# deterministic finalize window rather than burning it on a call that will die.
MIN_ARBITER_SECONDS = 5.0


class DeadlineAwarePipeline:
    """H2-Lite orchestration: plan → market/research fork-join → ledger → Arbiter.

    Dependencies are typed same-process objects. Provider failures become
    degradation notes and the market branch still yields a traceable fallback.
    """

    def __init__(
        self,
        *,
        clock: Clock,
        market_pipeline: AnalysisPipeline,
        planner: Any | None = None,
        research_agent: Any | None = None,
        arbiter: Any | None = None,
        per_stage_timeout_seconds: float = 45.0,
        optional_operations: Sequence[str] = (),
        counter_signal_operations: Sequence[str] = (),
        source_note_sink: list[str] | None = None,
    ) -> None:
        self._clock = clock
        self._market = market_pipeline
        self._planner = planner
        self._research = research_agent
        self._arbiter = arbiter
        self._stage_timeout = per_stage_timeout_seconds
        # Disclosures from inside the tool registry — a source that only succeeded on
        # its retry, for instance. The registry has no other route to the report, and
        # a recovered-but-flaky source in the judged run must still be admitted.
        self._source_notes = source_note_sink
        # Which planned operations count as optional is configuration, not a guess
        # the pipeline makes. Everything not listed here is baseline work and is
        # never surrendered to the clock.
        self._optional_operations = frozenset(optional_operations)
        self._counter_signal_operations = frozenset(counter_signal_operations)

    @property
    def last_bars_by_asset(self) -> dict[str, Sequence[MarketBar]]:
        """Forward to the wrapped market pipeline's bars, if it tracks any.

        Lets a caller holding a `DeadlineAwarePipeline` (the live/Bedrock path)
        reuse the same bars the run already loaded, same as a caller holding a
        bare `OrganizerCsvPipeline` directly (the offline path) — see Task 14 /
        G2 triangulation wiring in `ui/presenter.py`.
        """
        return getattr(self._market, "last_bars_by_asset", {})

    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome:
        deadline = DeadlineManager.for_run(context, self._clock)
        state = RunStateMachine(context=context, clock=self._clock, emit=emit)
        notes: list[str] = []
        durations: dict[str, int] = {}
        reasoning_request = _reasoning_request(context)
        # One pipeline instance serves one run; a stale note from a previous run
        # would be attributed to this one.
        if self._source_notes is not None:
            self._source_notes.clear()

        plan = None
        if self._planner is not None:
            state.start(STAGE_PLANNER)
            try:
                plan, plan_notes = await deadline.run(
                    self._planner.run(
                        request=reasoning_request,
                        deadline=deadline.deadline_for(Stage.planner),
                    ),
                    stage=Stage.planner,
                    timeout_seconds=self._stage_timeout,
                )
                notes.extend(plan_notes)
                state.settle(
                    STAGE_PLANNER,
                    StageState.degraded if plan_notes else StageState.completed,
                )
            except Exception as exc:  # noqa: BLE001 - converted to a typed degradation
                notes.append(f"Planner 失敗（{type(exc).__name__}），研究分支略過。")
                state.settle(STAGE_PLANNER, StageState.degraded, message=notes[-1])

            if plan is not None:
                # Surfaces an existing decision (Task 15 / G4): the Planner
                # already chooses per-question which allowlisted operations to
                # run (Research Agent only executes `plan.planned_steps`), but
                # that choice and its reasoning were never logged as their own
                # event — only visible by diffing the ledger afterward. Kept
                # outside the try/except above: this must never turn a
                # successful plan into a settle-twice failure, and a test
                # double's `Planner` need not implement `allowed_operations()`.
                allowed_fn = getattr(self._planner, "allowed_operations", None)
                allowed = allowed_fn() if callable(allowed_fn) else ()
                emit(
                    ExecutionEvent(
                        timestamp=self._clock.now_utc(),
                        run_id=context.run_id,
                        run_mode=context.run_mode,
                        stage=STAGE_PLANNER,
                        event_type="plan_decision",
                        status="ok",
                        output_count=len(list(getattr(plan, "planned_steps", None) or ())),
                        message=_plan_decision_message(plan, allowed),
                    )
                )

        # Optional work is surrendered in the fixed order before the branches
        # start, and enforced by trimming the plan the Research Agent receives.
        research_plan = plan
        if plan is not None:
            research_plan = self._apply_skip_order(plan, deadline, state, notes)

        # The fork-join below owns the acquisition window, so a branch clamps only
        # its own per-call timeout. Two nested clamps on the same milestone would
        # race and make which one cancelled the branch non-deterministic.
        async def run_market() -> PipelineOutcome:
            return await self._market.execute(context, emit)

        async def run_research() -> Any | None:
            if self._research is None or research_plan is None:
                return None
            return await deadline.run(
                self._research.run(
                    plan=research_plan,
                    request=reasoning_request,
                    deadline=deadline.deadline_for(Stage.gather),
                ),
                timeout_seconds=self._stage_timeout,
            )

        state.start(STAGE_MARKET)
        state.start(STAGE_RESEARCH)
        fork_started = self._clock.monotonic()
        market_result, research_result = await _fork_join(
            (run_market(), run_research()),
            timeout_seconds=deadline.remaining(Stage.gather),
        )
        durations["market_research_fork_join"] = _elapsed_ms(self._clock, fork_started)

        if isinstance(market_result, BaseException):
            cancelled = isinstance(market_result, asyncio.CancelledError)
            notes.append(
                "市場分支於取證 deadline 到點時取消。"
                if cancelled
                else f"市場分支失敗（{type(market_result).__name__}）。"
            )
            ledger = _empty_ledger(context, notes[-1], self._clock.now_utc())
            market_outcome = PipelineOutcome(
                ledger=ledger,
                result=None,
                terminal_state=TerminalState.degraded,
                degradation_notes=[notes[-1]],
            )
            state.settle(
                STAGE_MARKET,
                StageState.cancelled if cancelled else StageState.failed,
                message=notes[-1],
            )
        else:
            market_outcome = market_result
            notes.extend(market_outcome.degradation_notes)
            # TerminalState and StageState share member names by contract.
            state.settle(STAGE_MARKET, StageState(market_outcome.terminal_state.value))

        # A degraded sibling never discards the branch that did finish.
        if self._source_notes:
            notes.extend(self._source_notes)
        if isinstance(research_result, BaseException):
            cancelled = isinstance(research_result, asyncio.CancelledError)
            notes.append(
                "研究分支於取證 deadline 到點時取消，市場證據仍保留。"
                if cancelled
                else f"研究分支失敗（{type(research_result).__name__}），市場證據仍保留。"
            )
            state.settle(
                STAGE_RESEARCH,
                StageState.cancelled if cancelled else StageState.failed,
                message=notes[-1],
            )
            research_result = None
        elif research_result is None:
            state.settle(STAGE_RESEARCH, StageState.degraded, message="研究分支未執行。")
        else:
            research_notes = list(getattr(research_result, "degradation_events", ()) or ())
            notes.extend(research_notes)
            state.settle(
                STAGE_RESEARCH,
                StageState.degraded if research_notes else StageState.completed,
            )

        # Extracted facts arrive with wording only. Reliability, independence group
        # and provenance are completed deterministically, and a fact citing a record
        # that was never fetched is disclosed rather than admitted.
        state.start(STAGE_EVIDENCE)
        ledger = market_outcome.ledger
        research_drafts = list(getattr(research_result, "drafts", ()) or ())
        if research_drafts:
            research_drafts, extraction_notes = complete_extracted_drafts(
                research_drafts,
                records=list(getattr(research_result, "records", ()) or ()),
                fetched_at=self._clock.now_utc(),
            )
            notes.extend(extraction_notes)
        if research_drafts:
            ledger, rejected = _merge_research_drafts(context, ledger, research_drafts)
            if rejected:
                notes.append(f"{rejected} 筆研究 draft 未符合 Evidence 契約，已拒絕。")
        state.settle(
            STAGE_EVIDENCE,
            StageState.completed if ledger.items else StageState.degraded,
            output_count=len(ledger.items),
        )

        result = market_outcome.result
        if self._arbiter is not None and ledger.items:
            if deadline.remaining(Stage.reason) > MIN_ARBITER_SECONDS:
                result, arbiter_notes = await self._run_arbiter(
                    deadline, state, reasoning_request, ledger, notes
                )
                notes.extend(arbiter_notes)
                if result is None:
                    result = market_outcome.result
            else:
                notes.append("剩餘時間不足，略過 Arbiter 並保留 artifacts finalize 預算。")
                state.settle(STAGE_ARBITER, StageState.degraded, message=notes[-1])

        # Deterministic and post-LLM: conflicts, caps and scorecards are decided
        # here so the model can never talk its way past them.
        ledger, result, conflict_notes = finalize_analysis(ledger, result)
        notes.extend(conflict_notes)

        durations.update(state.stage_durations_ms())
        # Nothing arrived and the acquisition window cut the market branch off: the
        # run was cancelled, not merely degraded. Any evidence that did arrive keeps
        # the run degraded instead, so that evidence still ships.
        if not ledger.items and state.state_of(STAGE_MARKET) is StageState.cancelled:
            state.cancel_run(
                message="分析 deadline 到點，取證分支已取消且無證據可交付。"
            )
            notes.append("分析 deadline 到點，取證分支已取消且無證據可交付。")
        terminal = state.terminal_state()
        # Missing analysis or any recorded degradation keeps the run off `completed`.
        if terminal is TerminalState.completed and (result is None or notes):
            terminal = TerminalState.degraded
        return PipelineOutcome(
            ledger=ledger,
            result=result,
            terminal_state=terminal,
            degradation_notes=list(dict.fromkeys(notes)),
            stage_durations_ms=durations,
        )

    def _classify(self, operation: str) -> OptionalWork | None:
        """Map a planned operation onto optional work, or ``None`` for baseline.

        Counter-signal is checked first: an operation declared as both is treated
        as the more valuable category, because it is surrendered last.
        """
        if operation in self._counter_signal_operations:
            return OptionalWork.counter_signal_second_search
        if operation in self._optional_operations:
            return OptionalWork.optional_context
        return None

    def _apply_skip_order(
        self,
        plan: Any,
        deadline: DeadlineManager,
        state: RunStateMachine,
        notes: list[str],
    ) -> Any | None:
        """Surrender optional work in the fixed order and trim it out of the plan.

        Enforcement goes through the existing interface — the Research Agent simply
        receives a narrower plan — so the frozen reasoning package is untouched.
        H3 is never classified here: it is permanently disabled, so it is never
        scheduled and reporting it as *skipped* would imply the run had a debate
        stage to give up.

        Returns the plan the Research Agent should receive, or ``None`` when every
        planned step was optional and none of it fits. Starting a branch whose work
        has all been surrendered would be bookkeeping, not research.
        """
        steps = list(getattr(plan, "planned_steps", ()) or ())
        if not steps:
            return plan

        by_work: dict[OptionalWork, list[Any]] = defaultdict(list)
        for step in steps:
            work = self._classify(str(getattr(step, "tool_operation", "")))
            if work is not None:
                by_work[work].append(step)
        if not by_work:
            return plan

        decision = plan_optional_work(
            by_work.keys(),
            remaining_seconds=deadline.remaining(Stage.gather),
            default_cost_seconds=self._stage_timeout,
            # Worst case is one per-call timeout for each planned call, which is
            # the configured cap rather than an invented estimate.
            cost_seconds={
                work: self._stage_timeout * len(work_steps)
                for work, work_steps in by_work.items()
            },
        )
        if not decision.skipped:
            return plan

        for work in decision.skipped:
            note = skip_note(work)
            notes.append(note)
            state.settle(work.value, StageState.degraded, message=note)

        kept = set(decision.keep)
        kept_steps = [
            step
            for step in steps
            if self._classify(str(getattr(step, "tool_operation", ""))) in (None, *kept)
        ]
        if not kept_steps:
            return None
        copier = getattr(plan, "model_copy", None)
        if copier is None:
            notes.append("Plan 型別不支援步驟裁剪，略過的 optional 工作僅以揭露方式記錄。")
            return plan
        return copier(update={"planned_steps": kept_steps})

    async def _run_arbiter(
        self,
        deadline: DeadlineManager,
        state: RunStateMachine,
        reasoning_request: ReasoningRequest,
        ledger: EvidenceLedger,
        notes: list[str],
    ) -> tuple[AnalysisResult | None, list[str]]:
        """One bounded Arbiter call. Failure degrades the stage, never the run."""
        state.start(STAGE_ARBITER)
        extra_notes: list[str] = []
        max_evidence = int(getattr(getattr(self._arbiter, "settings", None), "max_evidence", 30))
        protected_ids = {
            evidence_id
            for indicator in ledger.conflict_indicators
            for evidence_id in (
                *indicator.supporting_evidence_ids,
                *indicator.opposing_evidence_ids,
            )
        }
        arbiter_items = select_balanced_evidence(
            ledger.items, max_evidence, protected_ids=protected_ids
        )
        # The frozen reasoning layer reads attributes through `str(...)`, so it is
        # handed a string-valued view of the ledger for the same reason it is handed
        # `ReasoningRequest` instead of `RunContext`. With enum-valued items its
        # high-reliability priority and its fallback's fact selection both fail
        # silently — see `EvidenceView`.
        arbiter_ledger = ledger_view(arbiter_items)
        if len(arbiter_items) < len(ledger.items):
            extra_notes.append(
                f"雙資產 Arbiter 輸入依資產/來源配額由 {len(ledger.items)} 筆縮為 "
                f"{len(arbiter_items)} 筆；完整 Ledger 仍保留。"
            )
        try:
            result, arbiter_notes = await deadline.run(
                self._arbiter.run(
                    request=reasoning_request,
                    ledger=arbiter_ledger,
                    indicators=ledger.conflict_indicators,
                    deadline=deadline.deadline_for(Stage.reason),
                    degradation_notes=notes + extra_notes,
                ),
                stage=Stage.reason,
                timeout_seconds=self._stage_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - converted to a typed degradation
            extra_notes.append(
                f"Arbiter 失敗（{type(exc).__name__}），使用 deterministic fallback。"
            )
            state.settle(STAGE_ARBITER, StageState.degraded, message=extra_notes[-1])
            return None, extra_notes

        # An `ArbiterOutput` carries no request context by design; deterministic code
        # stamps the frozen run identity and cutoff back on. A projection failure is
        # an Arbiter failure, not a run failure.
        if isinstance(result, ArbiterOutput):
            try:
                result, projection_notes = project_to_analysis_result(
                    result, request=reasoning_request, evidence_items=arbiter_ledger.items
                )
            except ValidationError as exc:
                extra_notes.append(
                    f"Arbiter 輸出無法投影為 AnalysisResult（{type(exc).__name__}），"
                    "使用 deterministic fallback。"
                )
                state.settle(STAGE_ARBITER, StageState.degraded, message=extra_notes[-1])
                return None, extra_notes
            extra_notes.extend(projection_notes)
        # AC 6.4 / AC 9.6: a claims-empty result may never ship as a confident
        # report, whichever arbiter implementation produced it.
        if isinstance(result, AnalysisResult):
            result = ensure_honest_insufficiency(result)
        state.settle(STAGE_ARBITER, StageState.completed)
        return result, extra_notes + list(arbiter_notes)


def select_balanced_evidence(
    items: Sequence[EvidenceItem],
    limit: int,
    *,
    protected_ids: set[str] | None = None,
) -> list[EvidenceItem]:
    """Bound an Arbiter payload without letting one asset/source fill it.

    The complete ledger is never truncated. ``asset=None`` is its own neutral
    bucket and does not consume either asset's representation.
    """
    cap = max(0, min(limit, 30))
    protected = protected_ids or set()
    ordered = sorted(
        items,
        key=lambda item: (
            0 if item.evidence_id in protected else 1,
            {Reliability.high: 0, Reliability.medium: 1, Reliability.low: 2}[item.reliability],
            item.evidence_id,
        ),
    )
    if len(ordered) <= cap:
        return ordered
    buckets: dict[tuple[str, str], deque[EvidenceItem]] = defaultdict(deque)
    for item in ordered:
        asset_key = item.asset.value if item.asset is not None else "_market"
        buckets[(asset_key, item.source_type.value)].append(item)
    selected: list[EvidenceItem] = []
    while len(selected) < cap and buckets:
        for key in sorted(buckets):
            queue = buckets[key]
            if queue:
                selected.append(queue.popleft())
            if len(selected) >= cap:
                break
        buckets = {key: queue for key, queue in buckets.items() if queue}
    return sorted(selected, key=lambda item: item.evidence_id)


@dataclass(frozen=True)
class MappedLedger:
    """The canonical ledger plus what `EvidenceItem` cannot carry.

    `unmapped` is retained for callers but is now always empty: drafts are
    canonical `EvidenceDraft` models, so an unsupported asset or source type is
    rejected where it is produced rather than silently dropped at ledger time.
    """

    ledger: EvidenceLedger
    metric_index: dict[str, MetricValue]
    unmapped: list[str]


def to_contract_ledger(
    pending_items: Sequence[PendingEvidence],
    *,
    context: RunContext,
    degradation_messages: Sequence[str] = (),
) -> MappedLedger:
    """Assign reliability, grouping, hashes and ids, then return the ledger.

    A thin seam over `evidence.processor.build_ledger` so the pipeline keeps one
    call site while the processor owns every assignment rule.
    """
    build = build_ledger(
        pending_items,
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        degradation_messages=degradation_messages,
        now=datetime.now(timezone.utc),
    )
    return MappedLedger(
        ledger=build.ledger, metric_index=dict(build.metric_index), unmapped=[]
    )


class OrganizerCsvPipeline:
    """Deterministic, offline pipeline over the organizer Daily OHLCV CSV.

    One code path serves every supported asset: the symbol is a parameter, never a
    branch. There is no Arbiter in this increment, so `result` is `None` and the
    application renders the deterministic insufficient-data report over real
    evidence rather than pretending an analysis exists.
    """

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        load_bars: BarLoader | None = None,
        analysis_date: date | None = None,
        extra_drafts: Callable[[], tuple[list[PendingEvidence], list[str]]] | None = None,
        market_source_name: str | None = None,
        market_independence_group: str | None = None,
        market_source_url: str | None = None,
        emit_no_arbiter_note: bool = True,
    ) -> None:
        self._data_dir = data_dir
        self._load_bars = load_bars
        self._analysis_date = analysis_date
        # When this pipeline is the market branch of a pipeline that DOES run an
        # Arbiter, the "no Arbiter" note is false and must be suppressed.
        self._emit_no_arbiter_note = emit_no_arbiter_note
        # Injected callable for additional deterministic sources (e.g. live Fear &
        # Greed). It owns any HTTP so this module keeps its no-httpx boundary.
        self._extra_drafts = extra_drafts
        # Provenance for the market series. Defaults (None) keep the organizer CSV
        # labels; a live loader (e.g. Binance) must pass its own so evidence is
        # never misattributed to the organizer benchmark.
        self._market_source: dict[str, str] = {}
        if market_source_name is not None:
            self._market_source["source_name"] = market_source_name
        if market_independence_group is not None:
            self._market_source["independence_group"] = market_independence_group
        if market_source_url is not None:
            self._market_source["source_url"] = market_source_url
        self.last_metric_index: dict[str, MetricValue] = {}
        # Stashed the same way as `last_metric_index`: the caller already holds this
        # pipeline instance, so re-exposing what `execute()` already loaded costs
        # nothing extra and lets the UI layer (Task 14 / G2 triangulation) reuse the
        # exact bars a run used instead of re-fetching. Never read by anything inside
        # this module — a pure post-run convenience for callers.
        self.last_bars_by_asset: dict[str, Sequence[MarketBar]] = {}

    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome:
        as_of = self._analysis_date or context.analysis_as_of.date()
        drafts: list[PendingEvidence] = []
        degradation: list[str] = []
        statuses: list[str] = []
        bars_by_asset: dict[Asset, Sequence[MarketBar]] = {}

        for asset in context.assets:
            status, asset_drafts, bars = self._market_evidence_for(asset, as_of, degradation)
            statuses.append(status)
            drafts.extend(asset_drafts)
            if bars is not None:
                bars_by_asset[asset] = bars
                regime = build_regime_evidence(
                    asset.value,
                    bars,
                    analysis_as_of=as_of,
                    **self._market_source,
                )
                drafts.extend(regime.drafts)
                degradation.extend(regime.degradation)
            emit(
                self._stage_event(
                    context,
                    stage=STAGE_MARKET,
                    status=status,
                    output_count=len(asset_drafts),
                    message=f"{asset.value} market evidence {status}",
                )
            )

        self.last_bars_by_asset = {asset.value: bars for asset, bars in bars_by_asset.items()}

        if len(context.assets) == 2:
            left, right = context.assets
            if left in bars_by_asset and right in bars_by_asset:
                comparison = build_comparison_evidence(
                    left.value,
                    right.value,
                    bars_by_asset[left],
                    bars_by_asset[right],
                    analysis_as_of=as_of,
                    **self._market_source,
                )
                drafts.extend(comparison.drafts)
                degradation.extend(comparison.degradation)
                emit(
                    self._stage_event(
                        context,
                        stage="cross_asset_comparison",
                        status=comparison.status,
                        output_count=len(comparison.drafts),
                        message=f"{left.value}/{right.value} comparison {comparison.status}",
                    )
                )
            else:
                message = (
                    f"{left.value}/{right.value}: comparison unavailable because one asset "
                    "has no aligned market series"
                )
                degradation.append(message)
                emit(
                    self._stage_event(
                        context,
                        stage="cross_asset_comparison",
                        status="degraded",
                        output_count=0,
                        message=message,
                    )
                )

        # Additional deterministic sources (e.g. live sentiment). The injected
        # callable owns its HTTP; failures degrade, never raise.
        if self._extra_drafts is not None:
            try:
                extra, extra_degradation = self._extra_drafts()
            except Exception as exc:  # noqa: BLE001 - any source failure is a degradation, not a crash
                extra, extra_degradation = [], [f"額外來源取得失敗（{type(exc).__name__}）"]
            drafts.extend(extra)
            degradation.extend(extra_degradation)
            emit(
                self._stage_event(
                    context,
                    stage=STAGE_RESEARCH,
                    status="ok" if extra else "degraded",
                    output_count=len(extra),
                    message=f"extra deterministic evidence: {len(extra)}",
                )
            )

        # Fact-grounding disclosure: surface any LLM-extracted fact whose numbers
        # or dates are absent from its source (contract-safe — notes only).
        _, grounding_notes = ground_drafts(drafts)
        degradation.extend(grounding_notes)

        mapped = to_contract_ledger(
            drafts, context=context, degradation_messages=degradation
        )
        self.last_metric_index = mapped.metric_index
        emit(
            self._stage_event(
                context,
                stage=STAGE_EVIDENCE,
                status="ok" if mapped.ledger.items else "degraded",
                output_count=len(mapped.ledger.items),
                message=f"ledger built with {len(mapped.ledger.items)} items",
            )
        )

        result = _dual_asset_result(context, mapped, bars_by_asset, as_of)
        ledger, result, conflict_notes = finalize_analysis(mapped.ledger, result)
        notes = list(conflict_notes)
        if result is None and self._emit_no_arbiter_note:
            notes.append(
                "Arbiter 尚未接線，本次僅產出 deterministic 市場證據，未產出經驗證的推論或結論。"
            )
        notes += [f"市場指標缺口：{message}" for message in degradation]
        if mapped.unmapped:
            notes.append("未能對應契約列舉的證據：" + "、".join(mapped.unmapped))

        terminal_state = (
            TerminalState.failed
            if not ledger.items and all(status == "failed" for status in statuses)
            else TerminalState.degraded
        )
        return PipelineOutcome(
            ledger=ledger,
            result=result,
            terminal_state=terminal_state,
            degradation_notes=notes,
            stage_durations_ms={},
            # Reported from what this instance actually reads, not from
            # `run_mode`: a `load_bars` loader (e.g. live Binance) makes this
            # `live`; no loader means the static organizer CSV, genuine fixture
            # data, regardless of which run_mode asked for it. Guessing from
            # `run_mode` alone let a fixture-backed instance self-report `live`
            # under `official`, silently defeating the mode-honesty gate.
            effective_data_mode=(
                DataMode.live if self._load_bars is not None else DataMode.fixture
            ),
        )

    # -- internals ----------------------------------------------------------

    def _market_evidence_for(
        self, asset: Asset, as_of: date, degradation: list[str]
    ) -> tuple[str, list[PendingEvidence], Sequence[MarketBar] | None]:
        """Load bars and build market evidence for one asset; failures degrade, never raise."""
        try:
            bars = self._bars_for(asset)
        except (OSError, ValueError) as exc:
            degradation.append(
                f"{asset.value}: 無法載入主辦方 CSV（{exc.__class__.__name__}），該資產無市場基準證據。"
            )
            return "failed", [], None

        worker = build_market_evidence(asset.value, bars, analysis_as_of=as_of, **self._market_source)
        degradation.extend(f"{asset.value}: {message}" for message in worker.degradation)
        return worker.status, list(worker.drafts), bars

    def _bars_for(self, asset: Asset) -> Sequence[MarketBar]:
        if self._load_bars is not None:
            return self._load_bars(asset.value)
        data_dir = self._data_dir or default_data_dir()
        return load_organizer_csv(data_dir / f"{asset.value}_daily_ohlcv.csv")

    def _stage_event(
        self,
        context: RunContext,
        *,
        stage: str,
        status: str,
        output_count: int,
        message: str,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            timestamp=datetime.now(timezone.utc),
            run_id=context.run_id,
            run_mode=context.run_mode,
            stage=stage,
            event_type="stage_end",
            status=status,
            provider_or_model="public_market_data",
            output_count=output_count,
            message=message,
        )


def _event(
    now: datetime, *, stage: str, event_type: str, source: str, message: str
) -> DegradationEvent:
    return DegradationEvent(
        stage=stage, event_type=event_type, source=source, message=message, timestamp=now
    )


async def _fork_join(
    coroutines: Sequence[Awaitable[Any]],
    *,
    timeout_seconds: float,
) -> list[Any]:
    """Run branches concurrently under one acquisition deadline.

    On timeout the unfinished branches are cancelled and then awaited, so no
    pending task leaks into the Evidence stage. A cancelled branch is returned as
    a `CancelledError` value rather than raised, because the sibling branch's
    completed evidence must still reach the ledger.
    """
    tasks = [asyncio.ensure_future(coroutine) for coroutine in coroutines]
    try:
        _, pending = await asyncio.wait(tasks, timeout=max(0.0, timeout_seconds))
    except asyncio.CancelledError:
        # The run itself was cancelled: tear the children down, then re-raise.
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    for task in pending:
        task.cancel()
    if pending:
        # Cancel first, then await: never advance while a child task is unwound.
        await asyncio.gather(*pending, return_exceptions=True)

    results: list[Any] = []
    for task in tasks:
        if task.cancelled():
            results.append(asyncio.CancelledError())
            continue
        error = task.exception()
        results.append(error if error is not None else task.result())
    return results


def _elapsed_ms(clock: Clock, started: float) -> int:
    return max(0, round((clock.monotonic() - started) * 1000))


def _reasoning_request(context: RunContext) -> ReasoningRequest:
    return ReasoningRequest(
        run_id=context.run_id,
        question=context.question,
        assets=tuple(asset.value for asset in context.assets),
        analysis_as_of=context.analysis_as_of,
    )


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _plan_decision_message(plan: Any, allowed_operations: Sequence[str]) -> str:
    """Human-readable summary of which operations the Planner chose, skipped,
    and (when the model gave one) why — surfaces an existing decision for the
    `plan_decision` execution-log event (Task 15 / G4). Computes nothing new:
    every value here already exists on `plan` or the tool registry.
    """
    steps = list(getattr(plan, "planned_steps", None) or ())
    chosen = [str(getattr(step, "tool_operation", "")) for step in steps]
    skipped = [op for op in allowed_operations if op not in chosen]
    parts = [
        f"Planner 選用 {len(chosen)}/{len(allowed_operations)} 個可用操作："
        f"{'、'.join(chosen) if chosen else '（無）'}"
    ]
    if skipped:
        parts.append(f"略過：{'、'.join(skipped)}")
    rationales = [
        f"{getattr(step, 'tool_operation', '')}（{rationale}）"
        for step in steps
        if (rationale := str(getattr(step, "rationale", "") or "").strip())
    ]
    if rationales:
        parts.append("理由：" + "；".join(rationales))
    return "；".join(parts)


def _empty_ledger(context: RunContext, message: str, now: datetime) -> EvidenceLedger:
    return EvidenceLedger(
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        degradation_events=[
            DegradationEvent(
                stage="market_worker",
                event_type="branch_failed",
                source="pipeline",
                message=message,
                timestamp=now,
            )
        ],
    )


def _merge_research_drafts(
    context: RunContext,
    ledger: EvidenceLedger,
    research_drafts: Sequence[Any],
    *,
    metric_index: Mapping[str, MetricValue] | None = None,
) -> tuple[EvidenceLedger, int]:
    """Fold research evidence into the market ledger, re-ranking the merged set.

    Anything that is not `PendingEvidence` is counted as rejected rather than
    coerced: a producer that cannot state its own source class cannot have its
    reliability decided for it.
    """
    admitted = [item for item in research_drafts if isinstance(item, PendingEvidence)]
    rejected = len(research_drafts) - len(admitted)

    build = build_ledger(
        admitted,
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        existing=ledger.items,
        existing_metrics=metric_index,
        now=datetime.now(timezone.utc),
    )
    merged_events = list(ledger.degradation_events) + list(build.ledger.degradation_events)
    return build.ledger.model_copy(update={"degradation_events": merged_events}), rejected


def _attach_trust(result: Any, ledger: EvidenceLedger) -> Any:
    if not isinstance(result, AnalysisResult):
        return result
    conclusions = [claim for claim in result.claims if claim.claim_type is ClaimType.conclusion]
    cards = build_trust_scorecards(
        ledger,
        result.claim_evidence_links,
        conclusions,
        analysis_as_of=result.analysis_as_of,
    )
    payload = result.model_dump()
    payload["trust_scorecards"] = [card.model_dump() for card in cards]
    return AnalysisResult.model_validate(payload)


def finalize_analysis(
    ledger: EvidenceLedger, result: Any
) -> tuple[EvidenceLedger, Any, list[str]]:
    """Deterministic post-analysis pass: conflicts → confidence caps → scorecards.

    Material conflict is claim-level, so it can only be decided once stanced links
    exist. Detecting it here rather than inside the Arbiter keeps the rule out of
    the prompt: the indicator is derived from the ledger, persisted in
    `evidence.json`, and the affected conclusion is capped at `low` even though the
    model asked for `high`. H3 never runs — the conflict survives regardless.

    Trust Scorecards are built last because their `consistency` dimension reads the
    indicators this function just attached.
    """
    if not isinstance(result, AnalysisResult):
        return ledger, result, []

    notes: list[str] = []
    indicators = build_conflict_indicators(
        claim_evidence_links=result.claim_evidence_links, ledger=ledger
    )
    if indicators:
        ledger = ledger.model_copy(
            update={
                "conflict_indicators": indicators,
                "degradation_events": [
                    *ledger.degradation_events,
                    *(
                        DegradationEvent(
                            stage=STAGE_EVIDENCE,
                            event_type="material_conflict_detected",
                            source="evidence_processor",
                            message=(
                                f"{indicator.claim_id} 同時存在 reliability 至少 medium 且來自不同"
                                f"獨立群組的支持與反對證據（支持 "
                                f"{'、'.join(indicator.supporting_evidence_ids)}；反對 "
                                f"{'、'.join(indicator.opposing_evidence_ids)}），"
                                "雙方證據均保留，信心受規則上限約束。"
                            ),
                            timestamp=ledger.analysis_as_of,
                        )
                        for indicator in indicators
                    ),
                ],
            }
        )
        # `mode="json"` because the frozen cap helper compares confidence as plain
        # strings; enum members would never match the rank table.
        payload, cap_notes = apply_confidence_caps(
            result.model_dump(mode="json"),
            indicators,
            {item.evidence_id: item for item in ledger.items},
        )
        result = AnalysisResult.model_validate(payload)
        notes.extend(cap_notes)

    return ledger, _attach_trust(result, ledger), notes


def _dual_asset_result(
    context: RunContext,
    mapped: MappedLedger,
    bars_by_asset: dict[Asset, Sequence[MarketBar]],
    as_of: date,
) -> AnalysisResult | None:
    """Build a traceable deterministic comparison when no Arbiter is configured."""
    if len(context.assets) != 2:
        return None
    left, right = context.assets
    comparison = [
        item
        for item in mapped.ledger.items
        if left.value in item.normalized_fact
        and right.value in item.normalized_fact
        and "compare " in item.query_or_parameters
    ]
    if not comparison:
        return None
    basis = comparison[0]
    period = TimeRange(
        start=(as_of - timedelta(days=14)).isoformat(),
        end=as_of.isoformat(),
    )
    fact = Claim(
        claim_id="cl_001",
        claim_type=ClaimType.fact,
        assets=[left, right],
        time_range=period,
        text=basis.normalized_fact,
        confidence=Reliability.high,
    )
    conclusion = Claim(
        claim_id="cl_002",
        claim_type=ClaimType.conclusion,
        assets=[left, right],
        time_range=period,
        text=(
            f"截至 {as_of} UTC，{left.value} 與 {right.value} 的相對表現如 Evidence "
            f"{basis.evidence_id} 所示；這是描述性比較，不構成投資建議。"
        ),
        based_on_claim_ids=[fact.claim_id],
        confidence=Reliability.low,
        limitations=["目前比較證據來自單一市場資料獨立群組，信心上限為 low。"],
    )
    links = [
        ClaimEvidenceLink(
            claim_id=fact.claim_id,
            evidence_id=basis.evidence_id,
            stance=Stance.supports,
            reason="deterministic cross-asset calculation",
        ),
        ClaimEvidenceLink(
            claim_id=conclusion.claim_id,
            evidence_id=basis.evidence_id,
            stance=Stance.supports,
            reason="comparison conclusion quotes the same ledger fact",
        ),
    ]
    invalidations: list[InvalidationCondition] = []
    metric = mapped.metric_index.get(basis.evidence_id)
    if metric is not None:
        invalidations.append(
            InvalidationCondition(
                text=f"若 {metric.metric_name} 不再高於本次基準值，需重新評估比較敘述。",
                metric=metric.metric_name,
                operator=InvalidationOperator.lte,
                threshold=metric.metric_value,
                basis_evidence_id=basis.evidence_id,
            )
        )
    regime = None
    if left in bars_by_asset:
        regime_item = next(
            (
                item
                for item in mapped.ledger.items
                if item.asset is left and item.content_reference.startswith("market regime")
            ),
            None,
        )
        regime = classify_market_regime(
            left,
            bars_by_asset[left],
            analysis_as_of=as_of,
            evidence_id=regime_item.evidence_id if regime_item else None,
        )
    cards = build_trust_scorecards(
        mapped.ledger,
        links,
        [conclusion],
        analysis_as_of=context.analysis_as_of,
    )
    return AnalysisResult(
        run_id=context.run_id,
        question=context.question,
        assets=[left, right],
        analysis_as_of=context.analysis_as_of,
        direct_answer=conclusion.text,
        market_context=MarketContext(
            summary=f"以同一 UTC cutoff 比較 {left.value} 與 {right.value}。",
            time_range=period,
        ),
        claims=[fact, conclusion],
        claim_evidence_links=links,
        confidence=Reliability.low,
        confidence_rationale="比較證據可追溯，但目前僅有一個獨立市場資料群組。",
        limitations=["未比較不同幣的 base volume；缺日不 forward-fill。"],
        invalidation_conditions=invalidations,
        watch_items=[f"追蹤 {left.value}/{right.value} 相對報酬與比值百分位。"],
        market_regime=regime,
        trust_scorecards=cards,
    )

