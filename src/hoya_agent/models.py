"""Canonical Pydantic v2 contracts for the HOYA Market Agent.

This module is the single source of truth for all shared domain models.
It imports no project module and performs no I/O.

Model-local invariants enforced here:
- extra="forbid" on every model.
- Persisted timestamps are timezone-aware and carry UTC offset zero.
- AnalysisRequest / EvidenceLedger / AnalysisResult are frozen after
  construction (setattr raises); the immutability of `analysis_as_of` follows.
- Stance is owned exclusively by ClaimEvidenceLink.
- ID and text formats/nonblankness are enforced where a single model has all
  required inputs.
- Local Claim shape, EvidenceItem cache/temporal, InvalidationCondition
  all-or-nothing, MarketRegime "unavailable" payload, EvidenceLedger ordering
  and duplicate-detection, TrustScorecard dimension-to-count mappings, and
  Evidence List projection all live here.

Aggregate invariants enforced on AnalysisResult only when this model has all
inputs (its own claims + links + trust_scorecards + scalar fields):
- Claim assets ⊆ result.assets.
- Claim time_range.end ≤ analysis_as_of (date-level).
- Claim graph acyclicity, self-dep rejection, missing-target rejection.
- Inference cannot depend on conclusion; conclusion reachability to fact
  follows from acyclicity + layering.
- Link.claim_id resolves within the result's claims.
- Fact/inference/conclusion coverage (fact needs non-neutral, inference/
  conclusion need supports unless insufficient_data=true for conclusions).
- insufficient_data=true forces confidence=low.
- TrustScorecard claim_ids resolve to conclusion claims.

Cross-artifact invariants that require BOTH the result AND the ledger
(evidence_id resolution, ledger cutoff, threshold equality) are deliberately
NOT enforced here. They belong to a later boundary that has both artifacts:
- Ledger `published_at <= analysis_as_of` cutoff → Task 5 (Evidence Processor).
- Link.evidence_id resolution + Scorecard/InvalidationCondition evidence_id
  resolution → Task 5 (Evidence Processor) / Task 8 (integration).
- Confidence caps requiring ledger/conflict inputs → Task 5 / Task 6 (Arbiter).
- Ledger enforcement of the configured fetched-vs-published clock tolerance
  → Task 5 (the tolerance value itself is frozen in Task 1b Settings).
- Official `analysis_as_of` is frozen by Task 1b `build_run_context` using the
  injected UTC clock.
- The configured maximum `question` length is enforced by Task 1b Settings at
  the application boundary.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Enums (all str-backed for direct serialization)
# ---------------------------------------------------------------------------


class Asset(str, Enum):
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    BNB = "BNB"
    XRP = "XRP"


class RunMode(str, Enum):
    official = "official"
    rehearsal = "rehearsal"
    demo = "demo"


class SourceType(str, Enum):
    official = "official"
    market = "market"
    news = "news"
    onchain = "onchain"
    social = "social"
    macro = "macro"


class Reliability(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Stance(str, Enum):
    supports = "supports"
    opposes = "opposes"
    neutral = "neutral"


class ClaimType(str, Enum):
    fact = "fact"
    inference = "inference"
    conclusion = "conclusion"


class TrustLevel(str, Enum):
    strong = "strong"
    moderate = "moderate"
    weak = "weak"
    unavailable = "unavailable"


class RegimeLabel(str, Enum):
    """Per amended evidence-contracts.md §16.3 (Requirement 16 AC8 requires
    an unavailable state when required bars are missing)."""

    trending_up = "trending_up"
    trending_down = "trending_down"
    range_bound = "range_bound"
    high_volatility = "high_volatility"
    mixed = "mixed"
    unavailable = "unavailable"


class InvalidationOperator(str, Enum):
    lt = "lt"
    lte = "lte"
    gt = "gt"
    gte = "gte"


class WorkerStatus(str, Enum):
    completed = "completed"
    partial = "partial"
    failed = "failed"


class StageState(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    degraded = "degraded"
    failed = "failed"
    cancelled = "cancelled"


class TerminalState(str, Enum):
    completed = "completed"
    degraded = "degraded"
    failed = "failed"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_ID_RE = re.compile(r"^run_\d{8}_\d{6}_[A-Za-z0-9][A-Za-z0-9_-]*$")
_EV_ID_RE = re.compile(r"^ev_\d{3,}$")
_CL_ID_RE = re.compile(r"^cl_\d{3,}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_ZERO_OFFSET = timedelta(0)
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def _validate_utc(v: datetime, field_name: str) -> datetime:
    """Ensure a datetime is timezone-aware with UTC offset zero.

    Finding 3: `tzinfo is not None` is insufficient. Some tzinfo subclasses
    return None from utcoffset(), and any non-UTC timezone will pass a bare
    tzinfo check while violating the contract's Z-terminated invariant.
    """
    if v.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC, got naive datetime")
    offset = v.utcoffset()
    if offset is None:
        raise ValueError(
            f"{field_name} must be UTC (offset 00:00), got tzinfo with no utcoffset"
        )
    if offset != _ZERO_OFFSET:
        raise ValueError(
            f"{field_name} must be UTC (offset 00:00), got offset {offset}"
        )
    return v


def _strip_non_empty(v: str, field_name: str) -> str:
    """Strip whitespace and reject empty strings."""
    stripped = v.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty or blank")
    return stripped


def _strip_optional_non_empty(v: str | None, field_name: str) -> str | None:
    """Strip an optional string, rejecting a present but blank value."""
    if v is None:
        return None
    return _strip_non_empty(v, field_name)


def _validate_optional_http_url(v: str | None, field_name: str) -> str | None:
    """Accept only a present, nonblank HTTP(S) URL with a hostname."""
    stripped = _strip_optional_non_empty(v, field_name)
    if stripped is None:
        return None
    try:
        parsed = _HTTP_URL_ADAPTER.validate_python(stripped)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid HTTP(S) URL") from exc
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must be a valid HTTP(S) URL without credentials")
    return stripped


def _validate_non_blank_list(values: list[str], field_name: str) -> list[str]:
    """Reject blank list entries and return the stripped values.

    Second-review Finding 4: earlier version returned raw values, so
    surrounding whitespace persisted contrary to evidence-contracts.md §1
    ("Text fields are stripped and must not be empty").
    """
    stripped_values: list[str] = []
    for entry in values:
        stripped = entry.strip()
        if not stripped:
            raise ValueError(f"{field_name} must not contain blank strings")
        stripped_values.append(stripped)
    return stripped_values


def _validate_real_date(v: str, field_name: str) -> str:
    """Parse YYYY-MM-DD as a real calendar date."""
    stripped = v.strip()
    try:
        date.fromisoformat(stripped)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a real YYYY-MM-DD calendar date"
        ) from exc
    return stripped


# ---------------------------------------------------------------------------
# AnalysisRequest (§2)
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str
    assets: list[Asset]
    requested_at: datetime
    analysis_as_of: datetime
    deadline_seconds: int = 900
    run_mode: RunMode
    enable_conditional_debate: bool = False
    run_id: str

    @field_validator("question")
    @classmethod
    def _question_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "question")

    @field_validator("assets")
    @classmethod
    def _assets_valid(cls, v: list[Asset]) -> list[Asset]:
        if not (1 <= len(v) <= 2):
            raise ValueError("assets must contain 1 or 2 items")
        if len(v) != len(set(v)):
            raise ValueError("assets must be unique")
        return v

    @field_validator("requested_at")
    @classmethod
    def _requested_at_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "requested_at")

    @field_validator("analysis_as_of")
    @classmethod
    def _analysis_as_of_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "analysis_as_of")

    @field_validator("deadline_seconds")
    @classmethod
    def _deadline_range(cls, v: int) -> int:
        # requirements.md AC 8.1 + competition-rules: 900s external hard deadline.
        # Clock-freeze of the cutoff itself lives in RunContext/build_run_context.
        if v <= 0 or v > 900:
            raise ValueError("deadline_seconds must be in (0, 900]")
        return v

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v


class RunContext(BaseModel):
    """Immutable run-scoped timing and request state.

    Use :func:`hoya_agent.clock.build_run_context` rather than constructing this
    model directly so official runs take their cutoff from the injected clock.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    request: AnalysisRequest
    analysis_as_of: datetime
    started_at: datetime
    started_monotonic: float
    deadline_monotonic: float

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v

    @field_validator("analysis_as_of", "started_at")
    @classmethod
    def _timestamps_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "run context timestamp")

    @model_validator(mode="after")
    def _consistent_with_request(self) -> "RunContext":
        if self.run_id != self.request.run_id:
            raise ValueError("run_id must match request.run_id")
        if self.analysis_as_of != self.request.analysis_as_of:
            raise ValueError("analysis_as_of must match request.analysis_as_of")
        if self.request.run_mode is RunMode.official and self.analysis_as_of != self.started_at:
            raise ValueError("official analysis_as_of must equal the injected clock time")
        if self.started_monotonic < 0:
            raise ValueError("started_monotonic must be non-negative")
        expected_deadline = self.started_monotonic + self.request.deadline_seconds
        if self.deadline_monotonic != expected_deadline:
            raise ValueError("deadline_monotonic must equal start plus deadline_seconds")
        return self

    @property
    def run_mode(self) -> RunMode:
        return self.request.run_mode

    @property
    def question(self) -> str:
        return self.request.question

    @property
    def assets(self) -> tuple[Asset, ...]:
        return tuple(self.request.assets)

    @property
    def deadline_seconds(self) -> int:
        return self.request.deadline_seconds


class ResearchStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    tool_operation: str
    rationale: str

    @field_validator("step_id", "tool_operation", "rationale")
    @classmethod
    def _nonblank(cls, v: str) -> str:
        return _strip_non_empty(v, "research step field")


class ResearchPlan(BaseModel):
    """Bounded Planner output; operation allowlisting is enforced at execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_version: str = "planner-v1"
    assets: list[Asset]
    question_summary: str
    lookback_days: int = 14
    required_evidence_types: list[SourceType] = Field(default_factory=list)
    planned_steps: list[ResearchStep]
    asset_question_mismatch_warning: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("plan_version", "question_summary")
    @classmethod
    def _nonblank(cls, v: str) -> str:
        return _strip_non_empty(v, "research plan field")

    @field_validator("assets")
    @classmethod
    def _assets_valid(cls, v: list[Asset]) -> list[Asset]:
        if not (1 <= len(v) <= 2):
            raise ValueError("assets must contain 1 or 2 items")
        if len(set(v)) != len(v):
            raise ValueError("assets must be unique")
        return v

    @field_validator("lookback_days")
    @classmethod
    def _lookback_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("lookback_days must be positive")
        return v

    @field_validator("planned_steps")
    @classmethod
    def _bounded_steps(cls, v: list[ResearchStep]) -> list[ResearchStep]:
        if not (1 <= len(v) <= 8):
            raise ValueError("planned_steps must contain 1 to 8 steps")
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("planned step IDs must be unique")
        return v

    @field_validator("asset_question_mismatch_warning")
    @classmethod
    def _optional_warning(cls, v: str | None) -> str | None:
        return _strip_optional_non_empty(v, "asset_question_mismatch_warning")

    @field_validator("notes")
    @classmethod
    def _notes_nonblank(cls, v: list[str]) -> list[str]:
        return _validate_non_blank_list(v, "notes")


# ---------------------------------------------------------------------------
# EvidenceItem (§3)
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    asset: Asset | None
    source_type: SourceType
    source_name: str
    source_url: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    query_or_parameters: str
    content_reference: str
    normalized_fact: str
    reliability: Reliability
    independence_group: str
    content_hash: str
    is_cached: bool = False
    cache_time: datetime | None = None
    is_stale: bool = False

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id_format(cls, v: str) -> str:
        if not _EV_ID_RE.match(v):
            raise ValueError("evidence_id must match format ev_NNN")
        return v

    @field_validator("source_name")
    @classmethod
    def _source_name_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "source_name")

    @field_validator("source_url")
    @classmethod
    def _source_url_valid(cls, v: str | None) -> str | None:
        return _validate_optional_http_url(v, "source_url")

    @field_validator("content_reference")
    @classmethod
    def _content_reference_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "content_reference")

    @field_validator("normalized_fact")
    @classmethod
    def _normalized_fact_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "normalized_fact")

    @field_validator("independence_group")
    @classmethod
    def _independence_group_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "independence_group")

    @field_validator("query_or_parameters")
    @classmethod
    def _query_or_parameters_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "query_or_parameters")

    @field_validator("fetched_at")
    @classmethod
    def _fetched_at_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "fetched_at")

    @field_validator("published_at")
    @classmethod
    def _published_at_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return _validate_utc(v, "published_at")
        return v

    @field_validator("cache_time")
    @classmethod
    def _cache_time_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return _validate_utc(v, "cache_time")
        return v

    @field_validator("content_hash")
    @classmethod
    def _content_hash_hex64(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError("content_hash must be 64 lowercase hex characters")
        return v

    @model_validator(mode="after")
    def _cache_consistency(self) -> "EvidenceItem":
        if not self.is_cached and self.cache_time is not None:
            raise ValueError("is_cached=false requires cache_time=None")
        if self.is_cached and self.cache_time is None:
            raise ValueError("is_cached=true requires cache_time to be set")
        return self

    # Note: fetched_at vs published_at ordering intentionally NOT validated
    # here. Per evidence-contracts.md §3, `fetched_at` may precede
    # `published_at` by up to the configured clock tolerance. A strict
    # zero-tolerance rule is stricter than the contract permits, not a valid
    # subset of it, so the whole comparison is deferred. Owners:
    # - Configured clock tolerance → Settings.
    # - Combined tolerance + ledger-cutoff enforcement → Task 5 (Evidence
    #   Processor), which has both the tolerance and the ledger.


# ---------------------------------------------------------------------------
# EvidenceDraft — EvidenceItem minus processor-assigned fields
# ---------------------------------------------------------------------------


class EvidenceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: Asset | None
    source_type: SourceType
    source_name: str
    source_url: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    query_or_parameters: str
    content_reference: str
    normalized_fact: str
    is_cached: bool = False
    cache_time: datetime | None = None
    is_stale: bool = False
    source_record_id: str | None = None

    @field_validator("source_name")
    @classmethod
    def _source_name_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "source_name")

    @field_validator("source_url")
    @classmethod
    def _source_url_valid(cls, v: str | None) -> str | None:
        return _validate_optional_http_url(v, "source_url")

    @field_validator("source_record_id")
    @classmethod
    def _source_record_id_non_empty(cls, v: str | None) -> str | None:
        return _strip_optional_non_empty(v, "source_record_id")

    @field_validator("content_reference")
    @classmethod
    def _content_reference_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "content_reference")

    @field_validator("normalized_fact")
    @classmethod
    def _normalized_fact_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "normalized_fact")

    @field_validator("query_or_parameters")
    @classmethod
    def _query_or_parameters_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "query_or_parameters")

    @field_validator("fetched_at")
    @classmethod
    def _fetched_at_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "fetched_at")

    @field_validator("published_at")
    @classmethod
    def _published_at_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return _validate_utc(v, "published_at")
        return v

    @field_validator("cache_time")
    @classmethod
    def _cache_time_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return _validate_utc(v, "cache_time")
        return v

    @model_validator(mode="after")
    def _cache_consistency(self) -> "EvidenceDraft":
        if not self.is_cached and self.cache_time is not None:
            raise ValueError("is_cached=false requires cache_time=None")
        if self.is_cached and self.cache_time is None:
            raise ValueError("is_cached=true requires cache_time to be set")
        return self


class RawSourceRecord(BaseModel):
    """Normalized provider record before Evidence admission."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    source_name: str
    source_type: SourceType
    source_url: str | None = None
    asset: Asset | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    title: str | None = None
    content: str
    query_or_parameters: str
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("record_id", "source_name", "content", "query_or_parameters")
    @classmethod
    def _required_text(cls, v: str) -> str:
        return _strip_non_empty(v, "raw source field")

    @field_validator("title")
    @classmethod
    def _optional_title(cls, v: str | None) -> str | None:
        return _strip_optional_non_empty(v, "title")

    @field_validator("source_url")
    @classmethod
    def _source_url_valid(cls, v: str | None) -> str | None:
        return _validate_optional_http_url(v, "source_url")

    @field_validator("published_at")
    @classmethod
    def _published_at_utc(cls, v: datetime | None) -> datetime | None:
        return _validate_utc(v, "published_at") if v is not None else None

    @field_validator("fetched_at")
    @classmethod
    def _fetched_at_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "fetched_at")

    # fetched_at vs published_at ordering deferred; see EvidenceItem note.


# ---------------------------------------------------------------------------
# ClaimEvidenceLink (§8)
# ---------------------------------------------------------------------------


class ClaimEvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    evidence_id: str
    stance: Stance
    reason: str

    @field_validator("claim_id")
    @classmethod
    def _claim_id_format(cls, v: str) -> str:
        if not _CL_ID_RE.match(v):
            raise ValueError("claim_id must match format cl_NNN")
        return v

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id_format(cls, v: str) -> str:
        if not _EV_ID_RE.match(v):
            raise ValueError("evidence_id must match format ev_NNN")
        return v

    @field_validator("reason")
    @classmethod
    def _reason_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "reason")


# ---------------------------------------------------------------------------
# Evidence List projection (Finding 5)
# ---------------------------------------------------------------------------


class EvidenceListRow(BaseModel):
    """One row of the Evidence List projection.

    Fields are exactly those required by requirements.md AC 5.7 and design.md
    §5.1: `source`, `fetched_at`, `content_reference`, `related_claim`.

    Cardinality of `related_claim` is `list[str]` because evidence-contracts.md
    §8 explicitly permits one EvidenceItem to link to multiple claims with
    different stances. The Evidence List projects one row per EvidenceItem,
    so `related_claim` for that row is the collection of claim IDs pointing
    to it. Rows with no links carry `[]` rather than being omitted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    fetched_at: datetime
    content_reference: str
    related_claim: list[str]

    @field_validator("source")
    @classmethod
    def _source_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "source")

    @field_validator("content_reference")
    @classmethod
    def _content_reference_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "content_reference")

    @field_validator("fetched_at")
    @classmethod
    def _fetched_at_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "fetched_at")

    @field_validator("related_claim")
    @classmethod
    def _related_claim_valid(cls, v: list[str]) -> list[str]:
        for cid in v:
            if not _CL_ID_RE.match(cid):
                raise ValueError(
                    f"related_claim entry must match cl_NNN: {cid!r}"
                )
        if len(set(v)) != len(v):
            raise ValueError("related_claim must be unique")
        if v != sorted(v):
            raise ValueError("related_claim must be sorted")
        return v


def project_evidence_list(
    items: list[EvidenceItem], links: list[ClaimEvidenceLink]
) -> list[EvidenceListRow]:
    """Deterministic mapping from (EvidenceItem, ClaimEvidenceLink[]) to
    Evidence List projection rows.

    - Each EvidenceItem produces one row.
    - Row order follows the input `items` order (the ledger validator sorts
      items by evidence_id, so the projection is deterministic in practice).
    - `related_claim` deduplicates claim IDs and is sorted lexicographically.
    """
    by_evidence: dict[str, set[str]] = defaultdict(set)
    for link in links:
        by_evidence[link.evidence_id].add(link.claim_id)
    return [
        EvidenceListRow(
            source=item.source_name,
            fetched_at=item.fetched_at,
            content_reference=item.content_reference,
            related_claim=sorted(by_evidence.get(item.evidence_id, set())),
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# TimeRange and MarketContext
# ---------------------------------------------------------------------------


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _real_calendar_date(cls, v: str) -> str:
        return _validate_real_date(v, "date")

    @model_validator(mode="after")
    def _start_before_end(self) -> "TimeRange":
        if self.start > self.end:
            raise ValueError("start must be <= end")
        return self


class MarketContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    time_range: TimeRange

    @field_validator("summary")
    @classmethod
    def _summary_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "summary")


# ---------------------------------------------------------------------------
# Claim (§7)
# ---------------------------------------------------------------------------


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: ClaimType
    assets: list[Asset]
    time_range: TimeRange
    text: str
    based_on_claim_ids: list[str] = []
    confidence: Reliability
    limitations: list[str] = []
    invalidation_conditions: list[str] = []

    @field_validator("claim_id")
    @classmethod
    def _claim_id_format(cls, v: str) -> str:
        if not _CL_ID_RE.match(v):
            raise ValueError("claim_id must match format cl_NNN")
        return v

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "text")

    @field_validator("assets")
    @classmethod
    def _assets_valid(cls, v: list[Asset]) -> list[Asset]:
        if not (1 <= len(v) <= 2):
            raise ValueError("claim assets must contain 1 or 2 items")
        if len(v) != len(set(v)):
            raise ValueError("claim assets must be unique")
        return v

    @field_validator("based_on_claim_ids")
    @classmethod
    def _based_on_ids(cls, v: list[str]) -> list[str]:
        for cid in v:
            if not _CL_ID_RE.match(cid):
                raise ValueError(
                    f"based_on_claim_ids entry must match cl_NNN: {cid!r}"
                )
        if len(set(v)) != len(v):
            raise ValueError("based_on_claim_ids must be unique")
        return v

    @field_validator("limitations", "invalidation_conditions")
    @classmethod
    def _nonblank_list(cls, v: list[str]) -> list[str]:
        return _validate_non_blank_list(v, "list entry")

    @model_validator(mode="after")
    def _claim_layering(self) -> "Claim":
        if self.claim_type == ClaimType.fact:
            if self.based_on_claim_ids:
                raise ValueError("fact claims must have empty based_on_claim_ids")
        elif self.claim_type in (ClaimType.inference, ClaimType.conclusion):
            if not self.based_on_claim_ids:
                raise ValueError(
                    f"{self.claim_type.value} claims must have non-empty "
                    "based_on_claim_ids"
                )
        return self

    @model_validator(mode="after")
    def _no_self_dependency(self) -> "Claim":
        # Finding 7 (local half): a claim cannot list itself in its deps.
        if self.claim_id in self.based_on_claim_ids:
            raise ValueError(f"claim {self.claim_id} depends on itself (self-dep)")
        return self


# ---------------------------------------------------------------------------
# EvidenceLedger (§12), ConflictIndicator (§9), DegradationEvent
# ---------------------------------------------------------------------------


class ConflictIndicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    supporting_evidence_ids: list[str] = []
    opposing_evidence_ids: list[str] = []
    independence_groups: list[str] = []
    rule_version: str = "1.0"

    @field_validator("claim_id")
    @classmethod
    def _claim_id_format(cls, v: str) -> str:
        if not _CL_ID_RE.match(v):
            raise ValueError("claim_id must match format cl_NNN")
        return v

    @field_validator("supporting_evidence_ids", "opposing_evidence_ids")
    @classmethod
    def _ev_id_list(cls, v: list[str]) -> list[str]:
        for eid in v:
            if not _EV_ID_RE.match(eid):
                raise ValueError(f"evidence id must match ev_NNN: {eid!r}")
        return v

    @field_validator("independence_groups")
    @classmethod
    def _independence_groups_nonblank(cls, v: list[str]) -> list[str]:
        return _validate_non_blank_list(v, "independence_groups")

    @field_validator("rule_version")
    @classmethod
    def _rule_version_nonblank(cls, v: str) -> str:
        return _strip_non_empty(v, "rule_version")


class DegradationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    event_type: str
    source: str
    message: str
    timestamp: datetime

    @field_validator("stage", "event_type", "source", "message")
    @classmethod
    def _nonblank(cls, v: str) -> str:
        return _strip_non_empty(v, "field")

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "timestamp")


class WorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: WorkerStatus
    evidence_drafts: list[EvidenceDraft] = Field(default_factory=list)
    raw_records: list[RawSourceRecord] = Field(default_factory=list)
    degradation_events: list[DegradationEvent] = Field(default_factory=list)


class ExecutionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    timestamp: datetime
    run_id: str
    run_mode: RunMode
    stage: str
    event_type: str
    status: str
    duration_ms: int | None = None
    provider_or_model: str | None = None
    parameters: dict[str, str] = Field(default_factory=dict)
    attempt: int = 1
    input_count: int | None = None
    output_count: int | None = None
    error_category: str | None = None
    message: str = ""

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v

    @field_validator("schema_version", "stage", "event_type", "status")
    @classmethod
    def _stage_nonblank(cls, v: str) -> str:
        return _strip_non_empty(v, "stage")

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "timestamp")


class RunConfigSnapshot(BaseModel):
    """Sanitized configuration persisted in ``run_config.json``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    prompt_version: str
    policy_version: str
    run_id: str
    requested_run_mode: RunMode
    effective_run_mode: RunMode
    sanitized_request: dict[str, object]
    analysis_as_of: datetime
    deadline_seconds: int
    stage_durations_ms: dict[str, int] = Field(default_factory=dict)
    configured_sources: list[str] = Field(default_factory=list)
    optional_keys_present: dict[str, bool] = Field(default_factory=dict)
    used_recorded_fallback: bool = False
    used_cached_evidence: bool = False
    has_stale_evidence: bool = False
    terminal_status: str | None = None
    artifact_checksums: dict[str, str] = Field(default_factory=dict)
    missing_artifacts: list[str] = Field(default_factory=list)
    artifact_write_failures: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v

    @field_validator("analysis_as_of")
    @classmethod
    def _analysis_as_of_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "analysis_as_of")

    @property
    def run_mode(self) -> RunMode:
        return self.effective_run_mode

    @property
    def optional_key_presence(self) -> dict[str, bool]:
        return self.optional_keys_present

class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    run_mode: RunMode
    terminal_state: TerminalState
    artifact_dir: str
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    missing_artifacts: list[str] = Field(default_factory=list)
    evidence_item_count: int = 0
    confidence: Reliability
    insufficient_data: bool
    degradation_notes: list[str] = Field(default_factory=list)
    report_markdown: str | None = None

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v

    @field_validator("artifact_paths")
    @classmethod
    def _artifact_paths_nonblank(cls, v: dict[str, str]) -> dict[str, str]:
        return {
            _strip_non_empty(name, "artifact name"): _strip_non_empty(path, "artifact path")
            for name, path in v.items()
        }

    @field_validator("degradation_notes")
    @classmethod
    def _notes_nonblank(cls, v: list[str]) -> list[str]:
        return _validate_non_blank_list(v, "degradation_notes")

    @property
    def effective_run_mode(self) -> RunMode:
        return self.run_mode


class EvidenceLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str
    analysis_as_of: datetime
    run_mode: RunMode
    items: list[EvidenceItem] = []
    conflict_indicators: list[ConflictIndicator] = []
    degradation_events: list[DegradationEvent] = []

    @field_validator("schema_version")
    @classmethod
    def _schema_version_nonblank(cls, v: str) -> str:
        return _strip_non_empty(v, "schema_version")

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v

    @field_validator("analysis_as_of")
    @classmethod
    def _analysis_as_of_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "analysis_as_of")

    @model_validator(mode="after")
    def _ledger_invariants(self) -> "EvidenceLedger":
        # Finding 11: sorted, unique, empty-requires-degradation.
        ids = [it.evidence_id for it in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate evidence_id in ledger.items")
        if ids != sorted(ids):
            raise ValueError("ledger.items must be sorted by evidence_id")
        if not self.items and not self.degradation_events:
            raise ValueError(
                "empty ledger requires at least one degradation_event explaining why"
            )
        return self


# ---------------------------------------------------------------------------
# Requirement 16 — InvalidationCondition (§16.4)
# ---------------------------------------------------------------------------


class InvalidationCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    metric: str | None = None
    operator: InvalidationOperator | None = None
    threshold: float | None = None
    basis_evidence_id: str | None = None

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "text")

    @field_validator("metric")
    @classmethod
    def _metric_non_empty(cls, v: str | None) -> str | None:
        return _strip_optional_non_empty(v, "metric")

    @field_validator("basis_evidence_id")
    @classmethod
    def _basis_id_format(cls, v: str | None) -> str | None:
        if v is not None and not _EV_ID_RE.match(v):
            raise ValueError("basis_evidence_id must match format ev_NNN")
        return v

    @model_validator(mode="after")
    def _all_or_nothing(self) -> "InvalidationCondition":
        structured = (self.metric, self.operator, self.threshold, self.basis_evidence_id)
        n_set = sum(1 for f in structured if f is not None)
        if n_set not in (0, 4):
            raise ValueError(
                "InvalidationCondition requires all of "
                "(metric, operator, threshold, basis_evidence_id) or none of them"
            )
        return self


# ---------------------------------------------------------------------------
# Requirement 16 — MarketRegime (§16.3)
# ---------------------------------------------------------------------------


class MarketRegime(BaseModel):
    """Deterministic Market Regime label per amended §16.3.

    When `label == unavailable` (Requirement 16 AC8), `metrics` and `thresholds`
    may be empty and `evidence_id` may be None: no deterministic Evidence
    exists to reference. For every other label the payload must be complete.
    """

    model_config = ConfigDict(extra="forbid")

    asset: Asset
    label: RegimeLabel
    as_of: str
    window_days: int
    metrics: dict[str, float] = {}
    thresholds: dict[str, float] = {}
    evidence_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def _as_of_real_date(cls, v: str) -> str:
        return _validate_real_date(v, "as_of")

    @field_validator("window_days")
    @classmethod
    def _window_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("window_days must be > 0")
        return v

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id_format(cls, v: str | None) -> str | None:
        if v is not None and not _EV_ID_RE.match(v):
            raise ValueError("evidence_id must match format ev_NNN")
        return v

    @model_validator(mode="after")
    def _payload_shape(self) -> "MarketRegime":
        if self.label == RegimeLabel.unavailable:
            return self
        if not self.metrics:
            raise ValueError("non-unavailable MarketRegime requires non-empty metrics")
        if not self.thresholds:
            raise ValueError(
                "non-unavailable MarketRegime requires non-empty thresholds"
            )
        if self.evidence_id is None:
            raise ValueError("non-unavailable MarketRegime requires evidence_id")
        return self


# ---------------------------------------------------------------------------
# Requirement 16 — TrustScorecard dimensions (§16.2)
# ---------------------------------------------------------------------------


class SourceIndependenceDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    distinct_groups: int

    @field_validator("distinct_groups")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("distinct_groups must be >= 0")
        return v

    @model_validator(mode="after")
    def _level_matches_count(self) -> "SourceIndependenceDimension":
        n = self.distinct_groups
        if self.level == TrustLevel.strong and n < 3:
            raise ValueError("strong independence requires distinct_groups >= 3")
        if self.level == TrustLevel.moderate and n != 2:
            raise ValueError("moderate independence requires distinct_groups == 2")
        if self.level == TrustLevel.weak and n != 1:
            raise ValueError("weak independence requires distinct_groups == 1")
        if self.level == TrustLevel.unavailable and n != 0:
            raise ValueError("unavailable independence requires distinct_groups == 0")
        return self


class SourceDiversityDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    distinct_source_types: int

    @field_validator("distinct_source_types")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("distinct_source_types must be >= 0")
        return v

    @model_validator(mode="after")
    def _level_matches_count(self) -> "SourceDiversityDimension":
        n = self.distinct_source_types
        if self.level == TrustLevel.strong and n < 3:
            raise ValueError("strong diversity requires distinct_source_types >= 3")
        if self.level == TrustLevel.moderate and n != 2:
            raise ValueError("moderate diversity requires distinct_source_types == 2")
        if self.level == TrustLevel.weak and n != 1:
            raise ValueError("weak diversity requires distinct_source_types == 1")
        if self.level == TrustLevel.unavailable and n != 0:
            raise ValueError(
                "unavailable diversity requires distinct_source_types == 0"
            )
        return self


class ReliabilityMix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high: int
    medium: int
    low: int

    @field_validator("high", "medium", "low")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("reliability counts must be >= 0")
        return v


class ConsistencyDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    has_material_conflict: bool
    opposing_count: int

    @field_validator("opposing_count")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("opposing_count must be >= 0")
        return v

    @model_validator(mode="after")
    def _level_consistent(self) -> "ConsistencyDimension":
        # §16.2 bidirectional mapping:
        #   has_material_conflict=true                -> weak (requires opposing >= 1)
        #   has_material_conflict=false, opposing==0  -> strong
        #   has_material_conflict=false, opposing>0   -> moderate
        if self.has_material_conflict:
            if self.opposing_count < 1:
                raise ValueError(
                    "has_material_conflict=true requires opposing_count >= 1"
                )
            if self.level != TrustLevel.weak:
                raise ValueError(
                    "consistency level must be weak when has_material_conflict=true"
                )
        else:
            if self.opposing_count == 0 and self.level != TrustLevel.strong:
                raise ValueError(
                    "consistency level must be strong when no conflict and "
                    "opposing_count=0"
                )
            if self.opposing_count > 0 and self.level != TrustLevel.moderate:
                raise ValueError(
                    "consistency level must be moderate when no conflict and "
                    "opposing_count>0"
                )
        return self


class FreshnessDimension(BaseModel):
    """Freshness dimension per §16.2.

    The "configured fresh window" that determines strong vs moderate for the
    presence of a usable age is Task 1b Settings; this model enforces only
    the two shape rules that hold regardless of that window:
    - has_stale=true precludes strong;
    - a missing age (None) is only compatible with unavailable.
    """

    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    newest_evidence_age_hours: float | None = None
    has_stale: bool

    @field_validator("newest_evidence_age_hours")
    @classmethod
    def _non_negative_age(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("newest_evidence_age_hours must be >= 0")
        return v

    @model_validator(mode="after")
    def _level_consistent(self) -> "FreshnessDimension":
        if self.has_stale and self.level == TrustLevel.strong:
            raise ValueError("freshness=strong is invalid when has_stale=true")
        # §16.2: unavailable applies when no supporting Evidence carries a
        # usable time. Enforce the biconditional so `unavailable` and a missing
        # age imply each other.
        if self.newest_evidence_age_hours is None and self.level != TrustLevel.unavailable:
            raise ValueError(
                "freshness with no usable age must be unavailable"
            )
        if self.level == TrustLevel.unavailable and self.newest_evidence_age_hours is not None:
            raise ValueError(
                "freshness=unavailable requires newest_evidence_age_hours=None"
            )
        return self


class TrustScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_independence: SourceIndependenceDimension
    source_diversity: SourceDiversityDimension
    reliability_mix: ReliabilityMix
    consistency: ConsistencyDimension
    freshness: FreshnessDimension
    rationale: str

    @field_validator("claim_id")
    @classmethod
    def _claim_id_format(cls, v: str) -> str:
        if not _CL_ID_RE.match(v):
            raise ValueError("claim_id must match format cl_NNN")
        return v

    @field_validator("rationale")
    @classmethod
    def _rationale_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "rationale")


# ---------------------------------------------------------------------------
# AnalysisResult (§11 + §16)
# ---------------------------------------------------------------------------


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    question: str
    assets: list[Asset]
    analysis_as_of: datetime
    direct_answer: str
    market_context: MarketContext | None = None
    claims: list[Claim] = []
    claim_evidence_links: list[ClaimEvidenceLink] = []
    confidence: Reliability
    confidence_rationale: str
    limitations: list[str] = []
    invalidation_conditions: list[InvalidationCondition] = []
    watch_items: list[str] = []
    insufficient_data: bool = False
    degradation_notes: list[str] = []
    market_regime: MarketRegime | None = None
    trust_scorecards: list[TrustScorecard] = []

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError("run_id must match format run_YYYYMMDD_HHMMSS_<suffix>")
        return v

    @field_validator("assets")
    @classmethod
    def _assets_valid(cls, v: list[Asset]) -> list[Asset]:
        # Second-review Finding 2: mirror the AnalysisRequest contract of one
        # or two unique assets. This is decidable from the result itself and
        # does not require the ledger.
        if not (1 <= len(v) <= 2):
            raise ValueError("result assets must contain 1 or 2 items")
        if len(v) != len(set(v)):
            raise ValueError("result assets must be unique")
        return v

    @field_validator("analysis_as_of")
    @classmethod
    def _analysis_as_of_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "analysis_as_of")

    @field_validator("direct_answer")
    @classmethod
    def _direct_answer_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "direct_answer")

    @field_validator("question")
    @classmethod
    def _question_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "question")

    @field_validator("confidence_rationale")
    @classmethod
    def _rationale_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "confidence_rationale")

    @field_validator("limitations", "watch_items", "degradation_notes")
    @classmethod
    def _nonblank_list(cls, v: list[str]) -> list[str]:
        return _validate_non_blank_list(v, "list entry")

    # ------------------------------------------------------------------
    # Model-aggregate invariants that require this result's own collections
    # (Findings 6, 7, 8, 9, 13). Cross-artifact ledger checks are deferred.
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _insufficient_data_caps_confidence(self) -> "AnalysisResult":
        # Finding 9 (MODEL_LOCAL half): only the insufficient_data cap is
        # decidable from AnalysisResult alone. Ledger/conflict-driven caps
        # (material conflict, independence groups, stale-only) require the
        # ledger and are deferred to Task 5 / Task 6.
        if self.insufficient_data and self.confidence != Reliability.low:
            raise ValueError(
                "insufficient_data=true requires confidence=low"
            )
        return self

    @model_validator(mode="after")
    def _validate_claim_graph_and_context(self) -> "AnalysisResult":
        # Build ID map + list-position map.
        claims_by_id: dict[str, Claim] = {}
        position: dict[str, int] = {}
        for i, claim in enumerate(self.claims):
            if claim.claim_id in claims_by_id:
                raise ValueError(
                    f"duplicate claim_id in claims: {claim.claim_id}"
                )
            claims_by_id[claim.claim_id] = claim
            position[claim.claim_id] = i

        # Finding 6 (aggregate half): asset ⊆ result.assets, end ≤ cutoff.
        result_assets = set(self.assets)
        cutoff_date = self.analysis_as_of.date().isoformat()
        for claim in self.claims:
            if not set(claim.assets).issubset(result_assets):
                raise ValueError(
                    f"claim {claim.claim_id} references assets outside result.assets"
                )
            if claim.time_range.end > cutoff_date:
                raise ValueError(
                    f"claim {claim.claim_id} time_range.end > analysis_as_of date"
                )

        # Findings 7 + second-review 1: DAG invariants — missing target,
        # inference deps must be earlier in claims and of type fact/inference,
        # conclusion deps must be of type fact/inference (never conclusion).
        for i, claim in enumerate(self.claims):
            for dep in claim.based_on_claim_ids:
                if dep not in claims_by_id:
                    raise ValueError(
                        f"claim {claim.claim_id} depends on missing claim {dep}"
                    )
                dep_type = claims_by_id[dep].claim_type
                if claim.claim_type == ClaimType.inference:
                    if dep_type == ClaimType.conclusion:
                        raise ValueError(
                            f"inference {claim.claim_id} cannot depend on "
                            f"conclusion {dep}"
                        )
                    # evidence-contracts.md §7: inference depends on an
                    # EARLIER fact or inference.
                    if position[dep] >= i:
                        raise ValueError(
                            f"inference {claim.claim_id} depends on {dep} "
                            "which is not listed earlier in claims"
                        )
                elif claim.claim_type == ClaimType.conclusion:
                    # evidence-contracts.md §7: conclusion depends on fact
                    # or inference (never another conclusion).
                    if dep_type == ClaimType.conclusion:
                        raise ValueError(
                            f"conclusion {claim.claim_id} cannot depend on "
                            f"conclusion {dep}"
                        )

        # Cycle detection via DFS coloring. Under the layering + ordering
        # rules above cycles are structurally impossible, but the defensive
        # check remains so future rule changes cannot silently regress.
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(claims_by_id, WHITE)

        def visit(cid: str) -> None:
            state = color[cid]
            if state == GRAY:
                raise ValueError(
                    f"cycle in claim dependency graph involving {cid}"
                )
            if state == BLACK:
                return
            color[cid] = GRAY
            for dep in claims_by_id[cid].based_on_claim_ids:
                visit(dep)
            color[cid] = BLACK

        for cid in list(claims_by_id):
            visit(cid)

        return self

    @model_validator(mode="after")
    def _validate_links_and_coverage(self) -> "AnalysisResult":
        claim_ids = {c.claim_id for c in self.claims}
        links_by_claim: dict[str, list[ClaimEvidenceLink]] = defaultdict(list)
        for link in self.claim_evidence_links:
            # Finding 8 (aggregate half): link.claim_id must resolve to a claim
            # in this result. evidence_id resolution against the ledger is
            # deferred to Task 5 / Task 8 which has both artifacts.
            if link.claim_id not in claim_ids:
                raise ValueError(
                    f"link references unknown claim_id: {link.claim_id}"
                )
            links_by_claim[link.claim_id].append(link)

        for claim in self.claims:
            links = links_by_claim.get(claim.claim_id, [])
            non_neutral = [
                link for link in links if link.stance != Stance.neutral
            ]
            supports = [link for link in links if link.stance == Stance.supports]
            if claim.claim_type == ClaimType.fact:
                if not non_neutral:
                    raise ValueError(
                        f"fact {claim.claim_id} must have at least one "
                        "non-neutral evidence link"
                    )
            elif claim.claim_type == ClaimType.inference:
                if not supports:
                    raise ValueError(
                        f"inference {claim.claim_id} must have at least one "
                        "supporting evidence link"
                    )
            elif claim.claim_type == ClaimType.conclusion:
                if not self.insufficient_data and not supports:
                    raise ValueError(
                        f"conclusion {claim.claim_id} must have at least one "
                        "supporting evidence link (insufficient_data=false)"
                    )
        return self

    @model_validator(mode="after")
    def _validate_trust_scorecards(self) -> "AnalysisResult":
        # Finding 13 (aggregate half): scorecards may only reference conclusion
        # claims present in this result.
        claims_by_id = {c.claim_id: c for c in self.claims}
        for sc in self.trust_scorecards:
            if sc.claim_id not in claims_by_id:
                raise ValueError(
                    f"trust_scorecard references unknown claim_id: {sc.claim_id}"
                )
            if claims_by_id[sc.claim_id].claim_type != ClaimType.conclusion:
                raise ValueError(
                    f"trust_scorecard {sc.claim_id} must reference a "
                    "conclusion claim"
                )
        return self
