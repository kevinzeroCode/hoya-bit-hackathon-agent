"""Single use-case entry point: one request in, four artifacts and a `RunSummary` out.

The service owns run identity, the immutable cutoff, the run directory, and the
artifact write order. It contains no adapter, provider, or UI logic, and it does
not decide stage order — that is the pipeline's job (Task 3).

Write order is the resilience design: `run_config.json` exists before any analysis
work starts, execution events stream while the run is in flight, `evidence.json`
lands as soon as the ledger exists so a reasoning failure cannot erase
traceability, and `final_report.md` is written last. When analysis is missing the
report becomes the deterministic insufficient-data report rather than a missing
file.

The application consumes the canonical runtime seams from ``models`` and
``ports``; there is no parallel provisional contract.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

from hoya_agent.clock import build_run_context
from hoya_agent.models import AnalysisRequest, Asset, RunMode
from hoya_agent.models import ExecutionEvent, RunConfigSnapshot, RunContext, RunSummary, TerminalState
from hoya_agent.orchestration.pipeline import AnalysisPipeline
from hoya_agent.ports import Clock, ProgressSink
from hoya_agent.reporting.artifacts import (
    EVIDENCE_LEDGER,
    FINAL_REPORT,
    RUN_CONFIG,
    LocalArtifactStore,
)
from hoya_agent.reporting.renderer import build_insufficient_data_result, render

SCHEMA_VERSION = "1.0"
POLICY_VERSION = "1.0"
PROMPT_VERSION = "v1"

_RUN_ID_TIMESTAMP = "%Y%m%d_%H%M%S"
_SUFFIX_RE = re.compile(r"^[a-z0-9]{2,8}$")


def make_run_id(now: datetime, suffix: str) -> str:
    """Build the `run_YYYYMMDD_HHMMSS_<suffix>` identifier from injected time."""
    if not _SUFFIX_RE.match(suffix):
        raise ValueError("run id suffix must be 2-8 lowercase alphanumeric characters")
    return f"run_{now.strftime(_RUN_ID_TIMESTAMP)}_{suffix}"


def build_request(
    *,
    question: str,
    assets: list[Asset],
    run_mode: RunMode,
    now: datetime,
    run_id_suffix: str,
    analysis_as_of: datetime | None = None,
    deadline_seconds: int = 900,
    enable_conditional_debate: bool = False,
) -> AnalysisRequest:
    """Mint the run identity and freeze the cutoff according to run mode.

    `official` freezes the cutoff to the injected clock and refuses a
    caller-supplied value; rehearsal and demo may replay a fixed cutoff.
    """
    if run_mode is RunMode.official and analysis_as_of is not None:
        raise ValueError("official mode freezes analysis_as_of to the run start and cannot accept one")
    return AnalysisRequest(
        question=question,
        assets=assets,
        requested_at=now,
        analysis_as_of=analysis_as_of if analysis_as_of is not None else now,
        deadline_seconds=deadline_seconds,
        run_mode=run_mode,
        enable_conditional_debate=enable_conditional_debate,
        run_id=make_run_id(now, run_id_suffix),
    )


class ApplicationService:
    def __init__(
        self,
        *,
        artifact_root: Path,
        clock: Clock,
        pipeline: AnalysisPipeline,
        prompt_version: str = PROMPT_VERSION,
        policy_version: str = POLICY_VERSION,
        configured_sources: Sequence[str] = (),
        optional_keys_present: Mapping[str, bool] | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._artifact_root = Path(artifact_root)
        self._clock = clock
        self._pipeline = pipeline
        self._prompt_version = prompt_version
        self._policy_version = policy_version
        self._configured_sources = list(configured_sources)
        self._optional_keys_present = dict(optional_keys_present or {})
        self._stdout = stdout

    async def run(
        self,
        request: AnalysisRequest,
        progress: ProgressSink | None = None,
    ) -> RunSummary:
        context = self._build_context(request)
        store = LocalArtifactStore(self._artifact_root / context.run_id, stdout=self._stdout)
        snapshot = self._initial_snapshot(request, context)

        # run_config.json first: it must exist before any analysis work starts.
        store.write_json(RUN_CONFIG, snapshot.model_dump(mode="json"))

        progress_tasks: list[asyncio.Task[None]] = []

        def emit(event: ExecutionEvent) -> None:
            store.append_event(event)
            if progress is not None:
                sync_emit = getattr(progress, "emit", None)
                if sync_emit is not None:
                    sync_emit(event)
                else:
                    published = progress.publish(event)
                    if inspect.isawaitable(published):
                        progress_tasks.append(asyncio.create_task(published))

        emit(self._event(context, "run", "run_start", "ok", message="run started"))
        if request.run_mode is RunMode.official and request.analysis_as_of != context.analysis_as_of:
            emit(
                self._event(
                    context,
                    "run",
                    "cutoff_frozen",
                    "warning",
                    message="official mode froze analysis_as_of to the injected clock",
                )
            )
        for warning in _asset_mismatch_warnings(request):
            emit(self._event(context, "run", "request_asset_mismatch", "warning", message=warning))

        outcome = await self._pipeline.execute(context, emit)

        # evidence.json as soon as the ledger exists, so a reasoning failure
        # cannot remove traceability.
        ledger = outcome.ledger
        if store.write_json(EVIDENCE_LEDGER, ledger.model_dump(mode="json")):
            emit(
                self._event(
                    context,
                    "artifact",
                    "artifact_write",
                    "ok",
                    output_count=len(ledger.items),
                    message=f"wrote {EVIDENCE_LEDGER}",
                )
            )

        result = outcome.result
        if result is None:
            result = build_insufficient_data_result(
                run_id=context.run_id,
                question=context.question,
                assets=list(context.assets),
                analysis_as_of=context.analysis_as_of,
                reason=_fallback_reason(outcome.degradation_notes),
            )
        report = render(result, ledger)
        if store.write_text(FINAL_REPORT, report):
            emit(
                self._event(
                    context,
                    "artifact",
                    "artifact_write",
                    "ok",
                    message=f"wrote {FINAL_REPORT}",
                )
            )

        terminal_state = _terminal_state(outcome.terminal_state, store)
        # run_config.json cannot carry a checksum of itself: the digest would be
        # taken before this final rewrite and would never match the file on disk.
        checksums = {
            name: digest for name, digest in store.checksums().items() if name != RUN_CONFIG
        }
        final_snapshot = snapshot.model_copy(
            update={
                "stage_durations_ms": dict(outcome.stage_durations_ms),
                "used_cached_evidence": any(item.is_cached for item in ledger.items),
                "has_stale_evidence": any(item.is_stale for item in ledger.items),
                "terminal_status": terminal_state.value,
                "artifact_checksums": checksums,
                "missing_artifacts": store.missing_artifacts(),
                "artifact_write_failures": [f.as_dict() for f in store.failures],
            }
        )
        store.write_json(RUN_CONFIG, final_snapshot.model_dump(mode="json"))
        emit(
            self._event(
                context,
                "run",
                "run_end",
                terminal_state.value,
                message=f"run finished as {terminal_state.value}",
            )
        )
        store.disclose_missing(terminal_state)

        if progress_tasks:
            await asyncio.gather(*progress_tasks)

        return RunSummary(
            run_id=context.run_id,
            run_mode=context.run_mode,
            terminal_state=terminal_state,
            artifact_dir=str(store.run_dir),
            artifact_paths=store.artifact_paths(),
            missing_artifacts=store.missing_artifacts(),
            evidence_item_count=len(ledger.items),
            confidence=result.confidence,
            insufficient_data=result.insufficient_data,
            degradation_notes=list(outcome.degradation_notes) + list(result.degradation_notes),
            report_markdown=report,
        )

    # -- internals ----------------------------------------------------------

    def _build_context(self, request: AnalysisRequest) -> RunContext:
        return build_run_context(request, self._clock)

    def _initial_snapshot(
        self, request: AnalysisRequest, context: RunContext
    ) -> RunConfigSnapshot:
        return RunConfigSnapshot(
            schema_version=SCHEMA_VERSION,
            prompt_version=self._prompt_version,
            policy_version=self._policy_version,
            run_id=context.run_id,
            requested_run_mode=request.run_mode,
            effective_run_mode=context.run_mode,
            sanitized_request={
                "question": request.question,
                "assets": [asset.value for asset in request.assets],
                "requested_at": request.requested_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "requested_analysis_as_of": request.analysis_as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "deadline_seconds": request.deadline_seconds,
                # MVP records conditional debate as accepted but disabled.
                "enable_conditional_debate_requested": request.enable_conditional_debate,
                "conditional_debate_effective": False,
            },
            analysis_as_of=context.analysis_as_of,
            deadline_seconds=request.deadline_seconds,
            configured_sources=self._configured_sources,
            optional_keys_present=self._optional_keys_present,
        )

    def _event(
        self,
        context: RunContext,
        stage: str,
        event_type: str,
        status: str,
        *,
        message: str = "",
        output_count: int | None = None,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            schema_version=SCHEMA_VERSION,
            timestamp=self._clock.now_utc(),
            run_id=context.run_id,
            run_mode=context.run_mode,
            stage=stage,
            event_type=event_type,
            status=status,
            output_count=output_count,
            message=message,
        )


def _asset_mismatch_warnings(request: AnalysisRequest) -> list[str]:
    """`assets` always wins over the question text; the disagreement is logged."""
    requested = {asset.value for asset in request.assets}
    mentioned = {asset.value for asset in Asset if asset.value in request.question.upper()}
    extra = sorted(mentioned - requested)
    if not extra:
        return []
    return [
        "question text mentions "
        + ", ".join(extra)
        + " which is not in the requested assets "
        + ", ".join(sorted(requested))
        + "; requested assets take precedence"
    ]


def _fallback_reason(degradation_notes: Sequence[str]) -> str:
    return degradation_notes[0] if degradation_notes else "分析階段未產出可驗證結果"


def _terminal_state(pipeline_state: TerminalState, store: LocalArtifactStore) -> TerminalState:
    """Artifact delivery is part of run honesty, so missing files degrade the state."""
    missing = store.missing_artifacts()
    if len(missing) == 4:
        return TerminalState.failed
    if missing and pipeline_state is TerminalState.completed:
        return TerminalState.degraded
    return pipeline_state


__all__ = [
    "ApplicationService",
    "build_request",
    "make_run_id",
]
