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

Task 1b has landed, so the runtime seams come from `models.py`/`ports.py` and the
pipeline seam from `orchestration.pipeline`. The provisional stand-in is gone.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

from hoya_agent.clock import build_run_context
from hoya_agent.config import Settings
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    DataMode,
    ExecutionEvent,
    RunConfigSnapshot,
    RunContext,
    RunMode,
    RunSummary,
    TerminalState,
)
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
        settings: Settings,
        clock: Clock,
        pipeline: AnalysisPipeline,
        prompt_versions: Mapping[str, str] | None = None,
        configured_sources: Sequence[str] = (),
        data_mode: DataMode = DataMode.live,
        stdout: TextIO | None = None,
    ) -> None:
        # `Settings` carries every configuration field `run_config.json` records,
        # including which optional keys are present as booleans rather than values,
        # so the service no longer takes them apart.
        self._settings = settings
        self._artifact_root = Path(settings.artifact_root)
        self._clock = clock
        self._pipeline = pipeline
        self._prompt_versions = dict(prompt_versions or {"analysis": PROMPT_VERSION})
        self._configured_sources = list(configured_sources)
        # Data mode is separate from run mode (evidence-contracts.md §14.1): a
        # rehearsal run on fixtures and a demo run replaying a recorded bundle are
        # different facts about the evidence, not about the run's honesty label.
        self._data_mode = data_mode
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

        def emit(event: ExecutionEvent) -> None:
            store.append_event(event)
            if progress is not None:
                progress.publish(event)

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
                question=context.request.question,
                assets=list(context.request.assets),
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
        # Missing artifacts and write failures are not snapshot fields: the
        # contract records `artifact_checksums`, and what is absent from it is
        # exactly what failed to land. The failures themselves are execution
        # events, which is where the log already carries them.
        final_snapshot = snapshot.model_copy(
            update={
                "stage_durations_ms": dict(outcome.stage_durations_ms),
                "used_cache": any(item.is_cached for item in ledger.items),
                "has_stale_evidence": any(item.is_stale for item in ledger.items),
                "terminal_status": terminal_state,
                "artifact_checksums": checksums,
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

        # `design.md` §104: the application returns artifact paths, effective data
        # mode, stage statuses and degradation notes. The UI reads report text from
        # `artifact_paths`, and confidence and insufficient-data live on
        # `AnalysisResult`, so the summary does not duplicate either.
        return RunSummary(
            run_id=context.run_id,
            terminal_state=terminal_state,
            effective_run_mode=request.run_mode,
            effective_data_mode=self._data_mode,
            artifact_paths=store.artifact_paths(),
            stage_statuses=dict(outcome.stage_statuses),
            degradation_notes=list(outcome.degradation_notes) + list(result.degradation_notes),
            completed_at=self._clock.now_utc(),
        )

    # -- internals ----------------------------------------------------------

    def _build_context(self, request: AnalysisRequest) -> RunContext:
        # `clock.build_run_context` owns the cutoff-freezing policy so official
        # runs cannot take a caller-supplied cutoff.
        return build_run_context(request, self._clock)

    def _initial_snapshot(
        self, request: AnalysisRequest, context: RunContext
    ) -> RunConfigSnapshot:
        # Settings is a superset of the snapshot's configuration fields, so it
        # builds the payload itself; the service only supplies run-scoped values.
        return self._settings.sanitized_snapshot(
            context.request,
            requested_data_mode=self._data_mode,
            effective_data_mode=self._data_mode,
            effective_run_mode=request.run_mode,
            prompt_versions=self._prompt_versions,
            source_identifiers=self._configured_sources,
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
            run_mode=context.request.run_mode,
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
