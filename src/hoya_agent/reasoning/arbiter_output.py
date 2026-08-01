"""The Arbiter's LLM-output schema, and its projection onto `AnalysisResult`.

`models.AnalysisResult` cannot serve as the Arbiter's `result_schema`. It requires
`run_id`, `question`, `assets` and `analysis_as_of` — the frozen request context,
which the model must never restate, because a model that can restate the cutoff
can widen it. The frozen `Arbiter._fallback()` reflects that: its payload omits
all four, leaves `market_context.time_range` null, and emits claims with no time
range. This module supplies the narrower schema the model actually fills, plus the
deterministic projection that stamps the frozen context back on.

Deliberate design points, each of which has a test:

- **Boundary values are plain strings, not enums.** The frozen
  `apply_confidence_caps()` compares confidence and stance with `str(...)`. A
  `str`-mixin enum member renders as `"Reliability.low"` / `"Stance.supports"`,
  which matches nothing in its rank table and nothing in its `"supports"` check.
  With enum-typed fields, every cap adjustment corrupts the payload, the Arbiter's
  own re-validation fails, and the run silently falls back — while looking like a
  successful reasoning stage. Strings at the boundary, enums after projection.
- **Deterministic fields are absent.** `trust_scorecards` and `market_regime` are
  derived by deterministic code (Requirement 16); `extra="forbid"` means a model
  that tries to emit them is rejected rather than trusted.
- **Missing time ranges are filled from the evidence window**, not invented, and
  are clamped to the frozen cutoff.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from hoya_agent.models import (
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    InvalidationCondition,
    MarketContext,
    Reliability,
    Stance,
    TimeRange,
)

ConfidenceText = Literal["high", "medium", "low"]
ClaimTypeText = Literal["fact", "inference", "conclusion"]
StanceText = Literal["supports", "opposes", "neutral"]


def _non_blank(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("text fields must not be blank")
    return text


class ArbiterTimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str


class ArbiterMarketContext(BaseModel):
    """Market context as the model states it; the range may be left unset."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    time_range: ArbiterTimeRange | None = None

    @field_validator("summary")
    @classmethod
    def _summary_non_blank(cls, v: str) -> str:
        return _non_blank(v)


class ArbiterClaim(BaseModel):
    """One claim as the model states it.

    `time_range` is optional because the frozen deterministic fallback does not
    supply one; the projection fills it from the evidence window.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: ClaimTypeText
    assets: list[str] = []
    time_range: ArbiterTimeRange | None = None
    text: str
    based_on_claim_ids: list[str] = []
    confidence: ConfidenceText
    limitations: list[str] = []
    invalidation_conditions: list[str] = []

    @field_validator("claim_id", "text")
    @classmethod
    def _required_text(cls, v: str) -> str:
        return _non_blank(v)


class ArbiterLink(BaseModel):
    """Stance lives here, never on the evidence item."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    evidence_id: str
    stance: StanceText
    reason: str

    @field_validator("claim_id", "evidence_id", "reason")
    @classmethod
    def _required_text(cls, v: str) -> str:
        return _non_blank(v)


class ArbiterInvalidationCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    metric: str | None = None
    operator: Literal["lt", "lte", "gt", "gte"] | None = None
    threshold: float | None = None
    basis_evidence_id: str | None = None

    @field_validator("text")
    @classmethod
    def _text_non_blank(cls, v: str) -> str:
        return _non_blank(v)


class ArbiterOutput(BaseModel):
    """Exactly what the Arbiter's single bounded call is allowed to produce.

    Use as `Arbiter(result_schema=ArbiterOutput)`. Everything the frozen request
    already fixed, and everything deterministic code derives, is absent by design.
    """

    model_config = ConfigDict(extra="forbid")

    direct_answer: str
    market_context: ArbiterMarketContext | None = None
    claims: list[ArbiterClaim] = []
    claim_evidence_links: list[ArbiterLink] = []
    confidence: ConfidenceText
    confidence_rationale: str
    limitations: list[str] = []
    invalidation_conditions: list[ArbiterInvalidationCondition] = []
    watch_items: list[str] = []
    insufficient_data: bool = False
    degradation_notes: list[str] = []

    @field_validator("direct_answer", "confidence_rationale")
    @classmethod
    def _required_text(cls, v: str) -> str:
        return _non_blank(v)


# ── string-valued evidence view for the frozen boundary ─────────────────────


@dataclass(frozen=True)
class EvidenceView:
    """One ledger item rendered with plain-string enums.

    Mirrors `ReasoningRequest`: the frozen reasoning layer reads attributes through
    `str(...)`, so it must be handed strings. With canonical `EvidenceItem`s three
    things fail silently, because `str(Reliability.high)` is `"Reliability.high"`:

    - `select_evidence()` loses its "keep every high-reliability item" priority and
      degrades into pure round-robin;
    - `Arbiter._fallback()` finds no high-reliability facts and emits a report with
      **no claims and no evidence links** — destroying the traceability the fallback
      exists to preserve;
    - `apply_confidence_caps()` never sees `"low"`, so the only-low-evidence cap
      never fires.

    Field names match `EvidenceItem` so the frozen code needs no change.
    """

    evidence_id: str
    asset: str | None
    source_type: str
    source_name: str
    source_url: str | None
    published_at: datetime | None
    fetched_at: datetime | None
    query_or_parameters: str
    content_reference: str
    normalized_fact: str
    reliability: str
    independence_group: str
    is_cached: bool
    cache_time: datetime | None
    is_stale: bool


@dataclass(frozen=True)
class LedgerView:
    """Minimal `.items` carrier — all the frozen Arbiter reads from a ledger."""

    items: list[EvidenceView]


def _plain(value: Any) -> Any:
    return getattr(value, "value", value)


def ledger_view(items: Sequence[Any]) -> LedgerView:
    """Project ledger items into the string-valued view the Arbiter must receive."""
    return LedgerView(
        items=[
            EvidenceView(
                evidence_id=str(item.evidence_id),
                asset=None if getattr(item, "asset", None) is None else str(_plain(item.asset)),
                source_type=str(_plain(getattr(item, "source_type", ""))),
                source_name=str(getattr(item, "source_name", "")),
                source_url=getattr(item, "source_url", None),
                published_at=getattr(item, "published_at", None),
                fetched_at=getattr(item, "fetched_at", None),
                query_or_parameters=str(getattr(item, "query_or_parameters", "")),
                content_reference=str(getattr(item, "content_reference", "")),
                normalized_fact=str(getattr(item, "normalized_fact", "")),
                reliability=str(_plain(getattr(item, "reliability", "low"))),
                independence_group=str(getattr(item, "independence_group", "")),
                is_cached=bool(getattr(item, "is_cached", False)),
                cache_time=getattr(item, "cache_time", None),
                is_stale=bool(getattr(item, "is_stale", False)),
            )
            for item in items
        ]
    )


# ── projection ──────────────────────────────────────────────────────────────


def _coerce_asset(raw: str) -> Asset | None:
    """Accept `BTC`, `btc`, or the frozen fallback's `str(Asset.BTC)` form."""
    text = str(raw).strip()
    if text.startswith("Asset."):
        text = text.split(".", 1)[1]
    try:
        return Asset(text.upper())
    except ValueError:
        return None


def _evidence_window(items: Sequence[Any], cutoff: date) -> TimeRange:
    """Earliest evidence date through the frozen cutoff.

    Derived from the ledger rather than from a default lookback, so the rendered
    window is traceable to evidence that actually exists. With no evidence the
    range collapses to the cutoff itself, which is honest rather than invented.
    """
    dates: list[date] = []
    for item in items:
        stamp = getattr(item, "published_at", None) or getattr(item, "fetched_at", None)
        if isinstance(stamp, datetime):
            dates.append(min(stamp.date(), cutoff))
    start = min(dates) if dates else cutoff
    return TimeRange(start=start.isoformat(), end=cutoff.isoformat())


def _clamped_range(
    raw: ArbiterTimeRange | None, *, window: TimeRange, cutoff: date, label: str
) -> tuple[TimeRange, list[str]]:
    """The stated range, clamped to the cutoff; the evidence window when unset."""
    if raw is None:
        return window, []
    notes: list[str] = []
    start, end = raw.start, raw.end
    if end > cutoff.isoformat():
        notes.append(
            f"{label} 的時間範圍結束於 {end}，超出凍結 cutoff {cutoff.isoformat()}，已收斂至 cutoff。"
        )
        end = cutoff.isoformat()
    if start > end:
        notes.append(f"{label} 的時間範圍起點晚於結束點，已改用證據窗口。")
        return window, notes
    try:
        return TimeRange(start=start, end=end), notes
    except ValueError:
        notes.append(f"{label} 的時間範圍無效，已改用證據窗口。")
        return window, notes


def project_to_analysis_result(
    output: ArbiterOutput,
    *,
    request: Any,
    evidence_items: Sequence[Any] = (),
) -> tuple[AnalysisResult, list[str]]:
    """Stamp the frozen request context onto a validated `ArbiterOutput`.

    Returns `(result, notes)`. Notes record every place deterministic code had to
    correct the model — a clamped window, an unrecognized asset — so the report can
    disclose it. Raises `pydantic.ValidationError` if the projected result still
    violates the `AnalysisResult` contract, which the caller treats as an Arbiter
    failure and answers with the deterministic fallback.
    """
    notes: list[str] = []
    cutoff: datetime = request.analysis_as_of
    cutoff_date = cutoff.date()
    request_assets = [asset for asset in (_coerce_asset(a) for a in request.assets) if asset]
    window = _evidence_window(evidence_items, cutoff_date)

    claims: list[Claim] = []
    for raw_claim in output.claims:
        assets = [asset for asset in (_coerce_asset(a) for a in raw_claim.assets) if asset]
        if len(assets) != len(raw_claim.assets):
            unknown = [
                str(a) for a in raw_claim.assets if _coerce_asset(a) is None
            ]
            notes.append(
                f"claim {raw_claim.claim_id} 指涉無法辨識的資產 {'、'.join(unknown)}，"
                "已改用本次 run 的資產清單。"
            )
        if not assets:
            assets = list(request_assets)
        claim_range, range_notes = _clamped_range(
            raw_claim.time_range,
            window=window,
            cutoff=cutoff_date,
            label=f"claim {raw_claim.claim_id}",
        )
        notes.extend(range_notes)
        claims.append(
            Claim(
                claim_id=raw_claim.claim_id,
                claim_type=ClaimType(raw_claim.claim_type),
                assets=assets,
                time_range=claim_range,
                text=raw_claim.text,
                based_on_claim_ids=list(raw_claim.based_on_claim_ids),
                confidence=Reliability(raw_claim.confidence),
                limitations=list(raw_claim.limitations),
                invalidation_conditions=list(raw_claim.invalidation_conditions),
            )
        )

    market_context: MarketContext | None = None
    if output.market_context is not None:
        context_range, range_notes = _clamped_range(
            output.market_context.time_range,
            window=window,
            cutoff=cutoff_date,
            label="market_context",
        )
        notes.extend(range_notes)
        market_context = MarketContext(
            summary=output.market_context.summary, time_range=context_range
        )

    result = AnalysisResult(
        run_id=request.run_id,
        question=request.question,
        assets=request_assets,
        analysis_as_of=cutoff,
        direct_answer=output.direct_answer,
        market_context=market_context,
        claims=claims,
        claim_evidence_links=[
            ClaimEvidenceLink(
                claim_id=link.claim_id,
                evidence_id=link.evidence_id,
                stance=Stance(link.stance),
                reason=link.reason,
            )
            for link in output.claim_evidence_links
        ],
        confidence=Reliability(output.confidence),
        confidence_rationale=output.confidence_rationale,
        limitations=list(output.limitations),
        invalidation_conditions=[
            InvalidationCondition(
                text=condition.text,
                metric=condition.metric,
                operator=condition.operator,
                threshold=condition.threshold,
                basis_evidence_id=condition.basis_evidence_id,
            )
            for condition in output.invalidation_conditions
        ],
        watch_items=list(output.watch_items),
        insufficient_data=output.insufficient_data,
        degradation_notes=list(dict.fromkeys([*output.degradation_notes, *notes])),
    )
    return result, notes
