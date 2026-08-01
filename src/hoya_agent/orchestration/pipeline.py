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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from hoya_agent.adapters.organizer_csv import default_data_dir, load_organizer_csv
from hoya_agent.data.market_worker import build_market_evidence
from hoya_agent.data.price_analysis import build_comparison_evidence
from hoya_agent.data.regime import build_regime_evidence, classify_market_regime
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.grounding import ground_drafts
from hoya_agent.evidence.processor import build_ledger
from hoya_agent.evidence.trust import build_trust_scorecards
from hoya_agent.evidence.types import EvidenceDraft
from hoya_agent.evidence.types import EvidenceLedger as WorkerLedger
from hoya_agent.models import (
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    DegradationEvent,
    EvidenceItem,
    EvidenceLedger,
    ExecutionEvent,
    InvalidationCondition,
    InvalidationOperator,
    MarketContext,
    Reliability,
    RunContext,
    SourceType,
    Stance,
    TerminalState,
    TimeRange,
)
from hoya_agent.orchestration.deadline import DeadlineExceeded, DeadlineManager
from hoya_agent.ports import Clock

EventEmitter = Callable[[ExecutionEvent], None]


@dataclass
class PipelineOutcome:
    ledger: EvidenceLedger
    result: AnalysisResult | None
    terminal_state: TerminalState = TerminalState.completed
    degradation_notes: list[str] = field(default_factory=list)
    stage_durations_ms: dict[str, int] = field(default_factory=dict)


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

STAGE_MARKET = "market_worker"
STAGE_EVIDENCE = "evidence_processor"
ANALYSIS_HARD_STOP_SECONDS = 720.0


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
    ) -> None:
        self._clock = clock
        self._market = market_pipeline
        self._planner = planner
        self._research = research_agent
        self._arbiter = arbiter
        self._stage_timeout = per_stage_timeout_seconds

    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome:
        analysis_deadline = min(
            context.deadline_monotonic,
            context.started_monotonic + ANALYSIS_HARD_STOP_SECONDS,
        )
        deadline = DeadlineManager(self._clock, analysis_deadline)
        notes: list[str] = []
        durations: dict[str, int] = {}
        reasoning_request = _reasoning_request(context)

        plan = None
        if self._planner is not None:
            started = self._clock.monotonic()
            try:
                plan, plan_notes = await deadline.run(
                    self._planner.run(
                        request=reasoning_request,
                        deadline=analysis_deadline,
                    ),
                    timeout_seconds=self._stage_timeout,
                )
                notes.extend(plan_notes)
                status = "degraded" if plan_notes else "ok"
            except (DeadlineExceeded, Exception) as exc:  # noqa: BLE001
                notes.append(f"Planner 失敗（{type(exc).__name__}），研究分支略過。")
                status = "degraded"
            durations["planner"] = _elapsed_ms(self._clock, started)
            emit(_pipeline_event(context, "planner", status, self._clock.now_utc()))

        async def run_market() -> PipelineOutcome:
            return await deadline.run(self._market.execute(context, emit))

        async def run_research() -> Any | None:
            if self._research is None or plan is None:
                return None
            return await deadline.run(
                self._research.run(
                    plan=plan,
                    request=reasoning_request,
                    deadline=analysis_deadline,
                ),
                timeout_seconds=self._stage_timeout,
            )

        fork_started = self._clock.monotonic()
        market_result, research_result = await asyncio.gather(
            run_market(), run_research(), return_exceptions=True
        )
        durations["market_research_fork_join"] = _elapsed_ms(self._clock, fork_started)

        if isinstance(market_result, BaseException):
            notes.append(f"市場分支失敗（{type(market_result).__name__}）。")
            ledger = _empty_ledger(context, notes[-1], self._clock.now_utc())
            market_outcome = PipelineOutcome(
                ledger=ledger,
                result=None,
                terminal_state=TerminalState.degraded,
                degradation_notes=[notes[-1]],
            )
        else:
            market_outcome = market_result
            notes.extend(market_outcome.degradation_notes)

        if isinstance(research_result, BaseException):
            notes.append(f"研究分支失敗（{type(research_result).__name__}），市場證據仍保留。")
            research_result = None
        if research_result is not None:
            notes.extend(list(getattr(research_result, "degradation_events", ()) or ()))
        emit(
            _pipeline_event(
                context,
                "research_agent",
                "ok" if research_result is not None else "degraded",
                self._clock.now_utc(),
            )
        )

        # Current research extraction schemas are owner-specific. Only admit a
        # draft when it already has the full evidence contract; malformed data
        # is disclosed and never smuggled into the Arbiter payload.
        ledger = market_outcome.ledger
        research_drafts = list(getattr(research_result, "drafts", ()) or ())
        if research_drafts:
            ledger, rejected = _merge_research_drafts(context, ledger, research_drafts)
            if rejected:
                notes.append(f"{rejected} 筆研究 draft 未符合 Evidence 契約，已拒絕。")
        emit(
            _pipeline_event(
                context,
                STAGE_EVIDENCE,
                "ok" if ledger.items else "degraded",
                self._clock.now_utc(),
                output_count=len(ledger.items),
            )
        )

        result = market_outcome.result
        if self._arbiter is not None and ledger.items and deadline.can_start(reserve_seconds=1.0):
            started = self._clock.monotonic()
            try:
                max_evidence = int(
                    getattr(getattr(self._arbiter, "settings", None), "max_evidence", 30)
                )
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
                arbiter_ledger = ledger.model_copy(update={"items": arbiter_items})
                if len(arbiter_items) < len(ledger.items):
                    notes.append(
                        f"雙資產 Arbiter 輸入依資產/來源配額由 {len(ledger.items)} 筆縮為 "
                        f"{len(arbiter_items)} 筆；完整 Ledger 仍保留。"
                    )
                result, arbiter_notes = await deadline.run(
                    self._arbiter.run(
                        request=reasoning_request,
                        ledger=arbiter_ledger,
                        indicators=ledger.conflict_indicators,
                        deadline=analysis_deadline,
                        degradation_notes=notes,
                    ),
                    timeout_seconds=self._stage_timeout,
                )
                notes.extend(arbiter_notes)
                result = _attach_trust(result, ledger)
                status = "ok"
            except (DeadlineExceeded, Exception) as exc:  # noqa: BLE001
                notes.append(f"Arbiter 失敗（{type(exc).__name__}），使用 deterministic fallback。")
                status = "degraded"
            durations["arbiter"] = _elapsed_ms(self._clock, started)
            emit(_pipeline_event(context, "arbiter", status, self._clock.now_utc()))
        elif self._arbiter is not None:
            notes.append("剩餘時間不足，略過 Arbiter 並保留 artifacts finalize 預算。")
            emit(_pipeline_event(context, "arbiter", "skipped", self._clock.now_utc()))

        terminal = TerminalState.completed
        if notes or result is None:
            terminal = TerminalState.degraded
        return PipelineOutcome(
            ledger=ledger,
            result=result,
            terminal_state=terminal,
            degradation_notes=list(dict.fromkeys(notes)),
            stage_durations_ms=durations,
        )


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
class MetricValue:
    """A deterministic numeric value that its Evidence Item carries.

    `models.EvidenceItem` has 16 fields and `extra="forbid"`, so it cannot hold
    `metric_name`/`metric_value`. Dropping them would make
    `evidence-contracts.md` §16.4 unsatisfiable, because a quantified
    invalidation threshold must equal a value carried by the referenced evidence.
    They are therefore preserved here, keyed by `evidence_id`.
    """

    metric_name: str
    metric_value: float


@dataclass(frozen=True)
class MappedLedger:
    ledger: EvidenceLedger
    metric_index: dict[str, MetricValue]
    unmapped: list[str]


def to_contract_ledger(
    worker_ledger: WorkerLedger,
    *,
    context: RunContext,
    degradation_messages: Sequence[str] = (),
) -> MappedLedger:
    """Convert a worker ledger into the canonical contract ledger, losing nothing silently."""
    now = datetime.now(timezone.utc)
    items: list[EvidenceItem] = []
    metric_index: dict[str, MetricValue] = {}
    unmapped: list[str] = []
    events: list[DegradationEvent] = []

    for raw in worker_ledger.items:
        asset, source_type, reliability, reason = _map_enums(raw)
        if reason is not None:
            unmapped.append(raw.evidence_id)
            events.append(
                _event(
                    now,
                    stage=STAGE_EVIDENCE,
                    event_type="evidence_unmappable",
                    source=raw.source_name,
                    message=f"{raw.evidence_id} 未納入 Ledger：{reason}",
                )
            )
            continue

        items.append(
            EvidenceItem(
                evidence_id=raw.evidence_id,
                asset=asset,
                source_type=source_type,
                source_name=raw.source_name,
                source_url=raw.source_url,
                published_at=raw.published_at,
                fetched_at=raw.fetched_at,
                query_or_parameters=raw.query_or_parameters,
                content_reference=raw.content_reference,
                normalized_fact=raw.normalized_fact,
                reliability=reliability,
                independence_group=raw.independence_group,
                content_hash=raw.content_hash,
                is_cached=raw.is_cached,
                cache_time=raw.cache_time,
                is_stale=raw.is_stale,
            )
        )
        if raw.metric_name is not None and raw.metric_value is not None:
            metric_index[raw.evidence_id] = MetricValue(
                metric_name=raw.metric_name, metric_value=float(raw.metric_value)
            )

    if worker_ledger.dropped_duplicates:
        events.append(
            _event(
                now,
                stage=STAGE_EVIDENCE,
                event_type="exact_duplicate_collapsed",
                source="evidence_processor",
                message=f"以 content_hash 精確去重，收合 {worker_ledger.dropped_duplicates} 筆重複證據。",
            )
        )

    for message in degradation_messages:
        events.append(
            _event(
                now,
                stage=STAGE_MARKET,
                event_type="metric_unavailable",
                source="public_market_data",
                message=message,
            )
        )

    if not items and not events:
        # models.EvidenceLedger rejects an empty ledger with no stated reason.
        events.append(
            _event(
                now,
                stage=STAGE_EVIDENCE,
                event_type="no_evidence",
                source="pipeline",
                message="本次 run 未取得任何可用證據，且未記錄其他降級原因。",
            )
        )

    ledger = EvidenceLedger(
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        items=sorted(items, key=lambda item: item.evidence_id),
        conflict_indicators=[],
        degradation_events=events,
    )
    return MappedLedger(ledger=ledger, metric_index=metric_index, unmapped=unmapped)


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
    ) -> None:
        self._data_dir = data_dir
        self._load_bars = load_bars
        self._analysis_date = analysis_date
        self.last_metric_index: dict[str, MetricValue] = {}

    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome:
        as_of = self._analysis_date or context.analysis_as_of.date()
        drafts: list[EvidenceDraft] = []
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

        if len(context.assets) == 2:
            left, right = context.assets
            if left in bars_by_asset and right in bars_by_asset:
                comparison = build_comparison_evidence(
                    left.value,
                    right.value,
                    bars_by_asset[left],
                    bars_by_asset[right],
                    analysis_as_of=as_of,
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

        # Fact-grounding disclosure: surface any LLM-extracted fact whose numbers
        # or dates are absent from its source (contract-safe — notes only).
        _, grounding_notes = ground_drafts(drafts)
        degradation.extend(grounding_notes)

        mapped = to_contract_ledger(
            build_ledger(drafts), context=context, degradation_messages=degradation
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
        notes = []
        if result is None:
            notes.append(
                "Arbiter 尚未接線，本次僅產出 deterministic 市場證據，未產出經驗證的推論或結論。"
            )
        notes += [f"市場指標缺口：{message}" for message in degradation]
        if mapped.unmapped:
            notes.append("未能對應契約列舉的證據：" + "、".join(mapped.unmapped))

        terminal_state = (
            TerminalState.failed
            if not mapped.ledger.items and all(status == "failed" for status in statuses)
            else TerminalState.degraded
        )
        return PipelineOutcome(
            ledger=mapped.ledger,
            result=result,
            terminal_state=terminal_state,
            degradation_notes=notes,
            stage_durations_ms={},
        )

    # -- internals ----------------------------------------------------------

    def _market_evidence_for(
        self, asset: Asset, as_of: date, degradation: list[str]
    ) -> tuple[str, list[EvidenceDraft], Sequence[MarketBar] | None]:
        """Load bars and build market evidence for one asset; failures degrade, never raise."""
        try:
            bars = self._bars_for(asset)
        except (OSError, ValueError) as exc:
            degradation.append(
                f"{asset.value}: 無法載入主辦方 CSV（{exc.__class__.__name__}），該資產無市場基準證據。"
            )
            return "failed", [], None

        worker = build_market_evidence(asset.value, bars, analysis_as_of=as_of)
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


def _map_enums(
    raw,  # noqa: ANN001 - the worker dataclass is provisional and untyped here on purpose
) -> tuple[Asset | None, SourceType | None, Reliability | None, str | None]:
    """Map the dataclass string fields onto the contract enums."""
    asset: Asset | None = None
    if raw.asset is not None:
        try:
            asset = Asset(_enum_value(raw.asset))
        except ValueError:
            return None, None, None, f"不支援的資產 {raw.asset!r}"
    try:
        source_type = SourceType(_enum_value(raw.source_type))
    except ValueError:
        return None, None, None, f"不支援的 source_type {raw.source_type!r}"
    try:
        reliability = Reliability(_enum_value(raw.reliability))
    except ValueError:
        return None, None, None, f"不支援的 reliability {raw.reliability!r}"
    return asset, source_type, reliability, None


def _event(
    now: datetime, *, stage: str, event_type: str, source: str, message: str
) -> DegradationEvent:
    return DegradationEvent(
        stage=stage, event_type=event_type, source=source, message=message, timestamp=now
    )


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


def _pipeline_event(
    context: RunContext,
    stage: str,
    status: str,
    timestamp: datetime,
    *,
    output_count: int | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        timestamp=timestamp,
        run_id=context.run_id,
        run_mode=context.run_mode,
        stage=stage,
        event_type="stage_end",
        status=status,
        output_count=output_count,
        message=f"{stage} {status}",
    )


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
) -> tuple[EvidenceLedger, int]:
    drafts: list[EvidenceDraft] = []
    for item in ledger.items:
        drafts.append(
            EvidenceDraft(
                asset=item.asset.value if item.asset else None,
                source_type=item.source_type.value,
                source_name=item.source_name,
                source_url=item.source_url,
                published_at=item.published_at,
                fetched_at=item.fetched_at,
                query_or_parameters=item.query_or_parameters,
                content_reference=item.content_reference,
                normalized_fact=item.normalized_fact,
                reliability=item.reliability.value,
                independence_group=item.independence_group,
                is_cached=item.is_cached,
                cache_time=item.cache_time,
                is_stale=item.is_stale,
            )
        )
    rejected = 0
    required = (
        "asset",
        "source_type",
        "source_name",
        "fetched_at",
        "query_or_parameters",
        "content_reference",
        "normalized_fact",
        "reliability",
        "independence_group",
    )
    for raw in research_drafts:
        if any(getattr(raw, name, None) is None for name in required[1:]):
            rejected += 1
            continue
        try:
            drafts.append(
                EvidenceDraft(
                    asset=(
                        _enum_value(getattr(raw, "asset"))
                        if getattr(raw, "asset", None) is not None
                        else None
                    ),
                    source_type=_enum_value(getattr(raw, "source_type")),
                    source_name=str(getattr(raw, "source_name")),
                    source_url=getattr(raw, "source_url", None),
                    published_at=getattr(raw, "published_at", None),
                    fetched_at=getattr(raw, "fetched_at"),
                    query_or_parameters=str(getattr(raw, "query_or_parameters")),
                    content_reference=str(getattr(raw, "content_reference")),
                    normalized_fact=str(getattr(raw, "normalized_fact")),
                    reliability=_enum_value(getattr(raw, "reliability")),
                    independence_group=str(getattr(raw, "independence_group")),
                    is_cached=bool(getattr(raw, "is_cached", False)),
                    cache_time=getattr(raw, "cache_time", None),
                    is_stale=bool(getattr(raw, "is_stale", False)),
                    metric_name=getattr(raw, "metric_name", None),
                    metric_value=getattr(raw, "metric_value", None),
                )
            )
        except (TypeError, ValueError):
            rejected += 1
    mapped = to_contract_ledger(build_ledger(drafts), context=context)
    merged_events = list(ledger.degradation_events) + list(mapped.ledger.degradation_events)
    return mapped.ledger.model_copy(update={"degradation_events": merged_events}), rejected


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

