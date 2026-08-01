"""Map the Arbiter's provider output onto the strict, frozen `AnalysisResult`.

The reasoning stages emit a lax `ArbiterGeneration` (no run identity, no strict
claim-graph invariants). This module injects the run identity from the request
and converts the lax shape into `models.AnalysisResult`, whose own validators
then enforce the contract (claim graph, link coverage, confidence caps).

Fail-safe by design: any conversion or validation error returns ``None`` so the
caller falls back to the deterministic insufficient-data report. A malformed
model answer can therefore never crash a run or ship an invalid report — the
worst case is the same honest "資料不足" output the offline path already produces.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from hoya_agent.models import (
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    InvalidationCondition,
    InvalidationOperator,
    Reliability,
    Stance,
    TimeRange,
)
from hoya_agent.reasoning.schemas import ArbiterGeneration, GenClaim

_DEFAULT_LOOKBACK_DAYS = 14


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _time_range(claim: GenClaim, analysis_as_of: datetime) -> TimeRange:
    """Use the model's time_range when given, else a default lookback window."""
    if claim.time_range and claim.time_range.get("start") and claim.time_range.get("end"):
        return TimeRange(start=claim.time_range["start"], end=claim.time_range["end"])
    end = analysis_as_of.date()
    start = end - timedelta(days=_DEFAULT_LOOKBACK_DAYS)
    return TimeRange(start=start.isoformat(), end=end.isoformat())


def to_analysis_result(
    generation: ArbiterGeneration, *, request: Any, ledger: Any
) -> AnalysisResult | None:
    """Convert a validated Arbiter generation into a strict AnalysisResult, or None."""
    analysis_as_of = _attr(request, "analysis_as_of")
    try:
        claims = [
            Claim(
                claim_id=c.claim_id,
                claim_type=ClaimType(c.claim_type),
                assets=[Asset(a) for a in c.assets],
                time_range=_time_range(c, analysis_as_of),
                text=c.text,
                based_on_claim_ids=list(c.based_on_claim_ids),
                confidence=Reliability(c.confidence),
                limitations=list(c.limitations),
                invalidation_conditions=list(c.invalidation_conditions),
            )
            for c in generation.claims
        ]
        links = [
            ClaimEvidenceLink(
                claim_id=link.claim_id,
                evidence_id=link.evidence_id,
                stance=Stance(link.stance),
                reason=link.reason,
            )
            for link in generation.claim_evidence_links
        ]
        invalidations = [
            InvalidationCondition(
                text=inv.text,
                metric=inv.metric,
                operator=InvalidationOperator(inv.operator) if inv.operator else None,
                threshold=inv.threshold,
                basis_evidence_id=inv.basis_evidence_id,
            )
            for inv in generation.invalidation_conditions
        ]
        return AnalysisResult(
            run_id=_attr(request, "run_id"),
            question=_attr(request, "question"),
            assets=[Asset(a) for a in (_attr(request, "assets") or ())],
            analysis_as_of=analysis_as_of,
            direct_answer=generation.direct_answer,
            market_context=None,
            claims=claims,
            claim_evidence_links=links,
            confidence=Reliability(generation.confidence),
            confidence_rationale=generation.confidence_rationale or "由 Arbiter 依證據產生。",
            limitations=list(generation.limitations),
            invalidation_conditions=invalidations,
            watch_items=list(generation.watch_items),
            insufficient_data=generation.insufficient_data,
            degradation_notes=list(generation.degradation_notes),
        )
    except (ValidationError, ValueError, TypeError):
        # Any malformed model output degrades to the deterministic fallback.
        return None
