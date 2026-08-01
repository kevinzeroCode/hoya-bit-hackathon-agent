"""Canonical LLM I/O schemas for the bounded reasoning stages.

These are the *provider output* shapes the Planner / Research Agent / Arbiter ask
Claude to return (via `converse_structured(schema=...)`). They are deliberately
lax — no `run_id`, no strict claim-graph invariants — because a model must be
free to produce a shape we then validate and map onto the strict, frozen
`models.AnalysisResult` (see `reasoning/mapping.py`). Promoted from the proven
reasoning test stubs; all fields mirror `.kiro/steering/evidence-contracts.md`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

# --- Arbiter output ---------------------------------------------------------


class GenClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: str
    assets: list[str] = []
    time_range: dict[str, str] | None = None  # {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    text: str = ""
    based_on_claim_ids: list[str] = []
    confidence: str = "medium"
    limitations: list[str] = []
    invalidation_conditions: list[str] = []


class GenLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    evidence_id: str
    stance: str
    reason: str = "reason"


class GenInvalidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    metric: str | None = None
    operator: str | None = None
    threshold: float | None = None
    basis_evidence_id: str | None = None


class ArbiterGeneration(BaseModel):
    """The Arbiter's provider output; mapped onto `models.AnalysisResult`."""

    model_config = ConfigDict(extra="forbid")

    direct_answer: str
    market_context: dict[str, Any] | None = None
    claims: list[GenClaim] = []
    claim_evidence_links: list[GenLink] = []
    confidence: str = "medium"
    confidence_rationale: str = ""
    limitations: list[str] = []
    invalidation_conditions: list[GenInvalidation] = []
    watch_items: list[str] = []
    insufficient_data: bool = False
    degradation_notes: list[str] = []


# --- Planner output ---------------------------------------------------------


class GenStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    tool_operation: str
    rationale: str = ""


class PlanGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version: str = "planner-v1"
    assets: list[str] = []
    question_summary: str = ""
    lookback_days: int = 14
    required_evidence_types: list[str] = []
    planned_steps: list[GenStep] = []
    asset_question_mismatch_warning: str | None = None
    notes: list[str] = []


# --- Research Agent output --------------------------------------------------


class GenDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    asset: str | None = None
    normalized_fact: str = ""
    content_reference: str = ""
    extraction_notes: list[str] = []


class GenSkipped(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    reason: str = ""


class DraftBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drafts: list[GenDraft] = []
    skipped: list[GenSkipped] = []
