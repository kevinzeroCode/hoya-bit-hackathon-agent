"""PROVISIONAL stand-in for the Task 1b (S1) runtime seams. Delete on swap.

Why this file exists
--------------------
S2 (Task 2, fixture vertical slice) needs four things that Task 1b owns and that
do not exist on `main` yet:

* the plumbing models `ExecutionEvent`, `RunConfigSnapshot`, `RunSummary`,
  `RunContext` — Task 1b adds them to `models.py`;
* the `Clock` and `ProgressSink` Protocols — Task 1b adds them to `ports.py`;
* the pipeline seam that Task 3 will implement as `DeadlineAwarePipeline`;
* the terminal run states that Task 3 owns in `orchestration/run_state.py`.

Rather than editing another owner's in-flight files, S2 declares the shapes here,
with field names copied verbatim from `.kiro/steering/evidence-contracts.md`
§13/§14 so the later swap is mechanical: repoint the imports at
`hoya_agent.models` / `hoya_agent.ports` and delete this module. The precedent is
`evidence/types.py`, which plays the same role for `EvidenceDraft`.

`tests/integration/test_s1_seam_bridge.py` skips while the real seams are absent
and starts enforcing shape parity the moment Task 1b lands, so drift cannot go
unnoticed. `docs/ai/S2_CONTRACT_EXPECTATIONS.md` records the same expectations in
prose.

🚫 Do not add S2-only convenience fields here. Anything added must be something
Task 1b is expected to provide.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from hoya_agent.models import AnalysisResult, Asset, EvidenceLedger, Reliability, RunMode

# ---------------------------------------------------------------------------
# Terminal run state — owner on landing: orchestration/run_state.py (Task 3)
# ---------------------------------------------------------------------------


class TerminalState(str, Enum):
    completed = "completed"
    degraded = "degraded"
    failed = "failed"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# Plumbing models — owner on landing: models.py (Task 1b)
# ---------------------------------------------------------------------------


class ExecutionEvent(BaseModel):
    """One line of `execution_log.jsonl` (evidence-contracts.md §13).

    Never carries prompt text, chain-of-thought, credentials or tokens.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    timestamp: datetime
    run_id: str
    run_mode: RunMode
    stage: str
    event_type: str
    status: str
    duration_ms: int | None = None
    provider_or_model: str | None = None
    parameters: dict[str, str] = {}
    attempt: int = 1
    input_count: int | None = None
    output_count: int | None = None
    error_category: str | None = None
    message: str = ""


class RunConfigSnapshot(BaseModel):
    """`run_config.json` (evidence-contracts.md §14).

    Optional credentials appear as presence booleans only, never as values.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    prompt_version: str
    policy_version: str
    run_id: str
    requested_run_mode: RunMode
    effective_run_mode: RunMode
    sanitized_request: dict[str, object]
    analysis_as_of: datetime
    deadline_seconds: int
    stage_durations_ms: dict[str, int] = {}
    configured_sources: list[str] = []
    optional_keys_present: dict[str, bool] = {}
    used_recorded_fallback: bool = False
    used_cached_evidence: bool = False
    has_stale_evidence: bool = False
    terminal_status: str | None = None
    artifact_checksums: dict[str, str] = {}
    missing_artifacts: list[str] = []
    artifact_write_failures: list[dict[str, str]] = []


class RunSummary(BaseModel):
    """What `ApplicationService.run()` hands back to the UI."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_mode: RunMode
    terminal_state: TerminalState
    artifact_dir: str
    artifact_paths: dict[str, str] = {}
    missing_artifacts: list[str] = []
    evidence_item_count: int = 0
    confidence: Reliability
    insufficient_data: bool
    degradation_notes: list[str] = []
    report_markdown: str | None = None


@dataclass(frozen=True)
class RunContext:
    """Immutable per-run facts. `analysis_as_of` never changes after creation."""

    run_id: str
    run_mode: RunMode
    question: str
    assets: tuple[Asset, ...]
    analysis_as_of: datetime
    deadline_seconds: int


# ---------------------------------------------------------------------------
# Protocols — owner on landing: ports.py (Task 1b), pipeline: Task 3
# ---------------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    def now_utc(self) -> datetime: ...

    def monotonic(self) -> float: ...


@runtime_checkable
class ProgressSink(Protocol):
    def emit(self, event: ExecutionEvent) -> None: ...


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


@runtime_checkable
class AnalysisPipeline(Protocol):
    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome: ...
