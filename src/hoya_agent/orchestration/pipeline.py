"""Stage order and the deterministic evidence pipeline.

Task 3 extends this module with `DeadlineManager` wiring and Market/Research
fork-join. What lives here today is the first increment: the seam that lets the
S2 vertical slice run on the real deterministic market evidence that landed on
`main`, instead of on committed fixtures.

One provisional coupling is deliberate and temporary:

* `to_contract_ledger` bridges `evidence/types.py` (the data/evidence layer's
  frozen dataclasses) to `models.py` (the canonical Pydantic contracts). Both
  representations currently exist on `main`; when the dataclasses retire, this
  function retires with them.

No LLM and no network live here. The organizer CSV is a local file, so this whole
path runs offline.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from hoya_agent.adapters.organizer_csv import default_data_dir, load_organizer_csv
from hoya_agent.data.market_worker import build_market_evidence
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.processor import build_ledger
from hoya_agent.evidence.types import EvidenceDraft
from hoya_agent.evidence.types import EvidenceLedger as WorkerLedger
from hoya_agent.models import (
    AnalysisResult,
    Asset,
    DegradationEvent,
    EvidenceItem,
    EvidenceLedger,
    ExecutionEvent,
    Reliability,
    RunContext,
    SourceType,
    StageState,
    TerminalState,
)

BarLoader = Callable[[str], Sequence[MarketBar]]

# The application-to-pipeline seam. These were provisional while Task 1b was
# outstanding; they live here now because orchestration owns them (Task 3), and
# `application.py` depends on orchestration rather than the other way round.
EventEmitter = Callable[[ExecutionEvent], None]


@dataclass
class PipelineOutcome:
    """What the analysis pipeline returns to `ApplicationService`.

    `result=None` means no validated analysis exists, which the application turns
    into the deterministic insufficient-data report rather than a missing file.
    """

    ledger: EvidenceLedger
    result: AnalysisResult | None
    terminal_state: TerminalState = TerminalState.completed
    degradation_notes: list[str] = field(default_factory=list)
    stage_durations_ms: dict[str, int] = field(default_factory=dict)
    # `RunSummary` reports per-stage state to the UI, so the pipeline is the one
    # that has to record it; durations alone cannot distinguish done from skipped.
    stage_statuses: dict[str, StageState] = field(default_factory=dict)


@runtime_checkable
class AnalysisPipeline(Protocol):
    """The seam `ApplicationService` drives. Task 3 supplies the real implementation."""

    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome: ...


STAGE_MARKET = "market_worker"
STAGE_EVIDENCE = "evidence_processor"


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
        run_mode=context.request.run_mode,
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

        for asset in context.request.assets:
            status, asset_drafts = self._market_evidence_for(asset, as_of, degradation)
            statuses.append(status)
            drafts.extend(asset_drafts)
            emit(
                self._stage_event(
                    context,
                    stage=STAGE_MARKET,
                    status=status,
                    output_count=len(asset_drafts),
                    message=f"{asset.value} market evidence {status}",
                )
            )

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

        notes = [
            "Arbiter 尚未接線（Task 6 整合前），本次僅產出 deterministic 市場證據，未產出經驗證的推論或結論。"
        ]
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
            result=None,
            terminal_state=terminal_state,
            degradation_notes=notes,
            stage_durations_ms={},
        )

    # -- internals ----------------------------------------------------------

    def _market_evidence_for(
        self, asset: Asset, as_of: date, degradation: list[str]
    ) -> tuple[str, list[EvidenceDraft]]:
        """Load bars and build market evidence for one asset; failures degrade, never raise."""
        try:
            bars = self._bars_for(asset)
        except (OSError, ValueError) as exc:
            degradation.append(
                f"{asset.value}: 無法載入主辦方 CSV（{exc.__class__.__name__}），該資產無市場基準證據。"
            )
            return "failed", []

        worker = build_market_evidence(asset.value, bars, analysis_as_of=as_of)
        degradation.extend(f"{asset.value}: {message}" for message in worker.degradation)
        return worker.status, list(worker.drafts)

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
            run_mode=context.request.run_mode,
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
            asset = Asset(raw.asset)
        except ValueError:
            return None, None, None, f"不支援的資產 {raw.asset!r}"
    try:
        source_type = SourceType(raw.source_type)
    except ValueError:
        return None, None, None, f"不支援的 source_type {raw.source_type!r}"
    try:
        reliability = Reliability(raw.reliability)
    except ValueError:
        return None, None, None, f"不支援的 reliability {raw.reliability!r}"
    return asset, source_type, reliability, None


def _event(
    now: datetime, *, stage: str, event_type: str, source: str, message: str
) -> DegradationEvent:
    return DegradationEvent(
        stage=stage, event_type=event_type, source=source, message=message, timestamp=now
    )
