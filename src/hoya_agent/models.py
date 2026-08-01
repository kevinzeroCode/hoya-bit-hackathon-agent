"""Canonical Pydantic v2 contracts for the HOYA Market Agent.

This module is the single source of truth for all shared domain models.
It imports no project module and performs no I/O.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

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
    trending_up = "trending_up"
    trending_down = "trending_down"
    range_bound = "range_bound"
    high_volatility = "high_volatility"
    mixed = "mixed"


class InvalidationOperator(str, Enum):
    lt = "lt"
    lte = "lte"
    gt = "gt"
    gte = "gte"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_ID_RE = re.compile(r"^run_\d{8}_\d{6}_.+$")
_EV_ID_RE = re.compile(r"^ev_\d{3,}$")
_CL_ID_RE = re.compile(r"^cl_\d{3,}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _validate_utc(v: datetime, field_name: str) -> datetime:
    """Ensure a datetime is timezone-aware UTC."""
    if v.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC, got naive datetime")
    return v


def _strip_non_empty(v: str, field_name: str) -> str:
    """Strip whitespace and reject empty strings."""
    stripped = v.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty or blank")
    return stripped


# ---------------------------------------------------------------------------
# AnalysisRequest (§2)
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    @field_validator("run_id")
    @classmethod
    def _run_id_format(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError(
                "run_id must match format run_YYYYMMDD_HHMMSS_<suffix>"
            )
        return v


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
            raise ValueError(
                "is_cached=false requires cache_time=None"
            )
        if self.is_cached and self.cache_time is None:
            raise ValueError(
                "is_cached=true requires cache_time to be set"
            )
        return self


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

    @field_validator("content_reference")
    @classmethod
    def _content_reference_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "content_reference")

    @field_validator("normalized_fact")
    @classmethod
    def _normalized_fact_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "normalized_fact")

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
# TimeRange and MarketContext
# ---------------------------------------------------------------------------


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _date_format(cls, v: str) -> str:
        stripped = v.strip()
        # Validate YYYY-MM-DD format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", stripped):
            raise ValueError("date must be YYYY-MM-DD format")
        return stripped

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

    @model_validator(mode="after")
    def _claim_layering(self) -> "Claim":
        if self.claim_type == ClaimType.fact:
            if self.based_on_claim_ids:
                raise ValueError(
                    "fact claims must have empty based_on_claim_ids"
                )
        elif self.claim_type in (ClaimType.inference, ClaimType.conclusion):
            if not self.based_on_claim_ids:
                raise ValueError(
                    f"{self.claim_type.value} claims must have non-empty based_on_claim_ids"
                )
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


class DegradationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    event_type: str
    source: str
    message: str
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _timestamp_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "timestamp")


class EvidenceLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    run_id: str
    analysis_as_of: datetime
    run_mode: RunMode
    items: list[EvidenceItem] = []
    conflict_indicators: list[ConflictIndicator] = []
    degradation_events: list[DegradationEvent] = []

    @field_validator("analysis_as_of")
    @classmethod
    def _analysis_as_of_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v, "analysis_as_of")


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


# ---------------------------------------------------------------------------
# Requirement 16 — MarketRegime (§16.3)
# ---------------------------------------------------------------------------


class MarketRegime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: Asset
    label: RegimeLabel
    as_of: str
    window_days: int
    metrics: dict[str, float]
    thresholds: dict[str, float]
    evidence_id: str


# ---------------------------------------------------------------------------
# Requirement 16 — TrustScorecard (§16.2)
# ---------------------------------------------------------------------------


class SourceIndependenceDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    distinct_groups: int


class SourceDiversityDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    distinct_source_types: int


class ReliabilityMix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high: int
    medium: int
    low: int


class ConsistencyDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    has_material_conflict: bool
    opposing_count: int


class FreshnessDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: TrustLevel
    newest_evidence_age_hours: float | None = None
    has_stale: bool


class TrustScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_independence: SourceIndependenceDimension
    source_diversity: SourceDiversityDimension
    reliability_mix: ReliabilityMix
    consistency: ConsistencyDimension
    freshness: FreshnessDimension
    rationale: str

    @field_validator("rationale")
    @classmethod
    def _rationale_non_empty(cls, v: str) -> str:
        return _strip_non_empty(v, "rationale")


# ---------------------------------------------------------------------------
# AnalysisResult (§11 + §16)
# ---------------------------------------------------------------------------


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
