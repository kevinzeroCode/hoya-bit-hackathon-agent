"""What a producer hands the Evidence Processor, and what the processor adds.

`models.EvidenceDraft` is deliberately narrower than `models.EvidenceItem`: it has
no `evidence_id`, `reliability`, `independence_group` or `content_hash`, because
all four are **assigned by the processor**, not by whoever fetched the data. The
provisional dataclass this replaces carried `reliability` and `independence_group`
on the draft itself, which inverted that rule — a producer could state its own
trustworthiness.

`PendingEvidence` restores the direction. A producer supplies the draft plus the
*provenance* the deterministic policy needs to decide reliability and grouping:

- `source_class` selects the static reliability row (evidence-contracts §4);
- `original_publisher` / `provider_id` feed the independence-group rule (§5);
- `metric_name`/`metric_value` carry a deterministic number forward, because
  `EvidenceItem` has `extra="forbid"` and cannot hold them, yet §16.4 requires a
  quantified invalidation threshold to equal a value the evidence carries.

Nothing here calls an LLM, the network, or the filesystem.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from hoya_agent.evidence.policies import SourceClass
from hoya_agent.models import Asset, EvidenceDraft, SourceType


@dataclass(frozen=True)
class MetricValue:
    """A deterministic numeric value that its Evidence Item carries.

    Kept beside the ledger rather than inside `EvidenceItem`, whose 16 fields and
    `extra="forbid"` cannot hold it. Dropping it would make a quantified
    invalidation condition unverifiable.
    """

    metric_name: str
    metric_value: float


@dataclass(frozen=True)
class PendingEvidence:
    """One canonical draft plus the provenance the processor needs."""

    draft: EvidenceDraft
    source_class: SourceClass
    original_publisher: str | None = None
    provider_id: str | None = None
    metric: MetricValue | None = None

    # Convenience passthroughs so callers can read the draft without reaching
    # inside. `reliability` and `independence_group` are deliberately absent: they
    # do not exist until the processor assigns them.
    @property
    def asset(self) -> Asset | None:
        return self.draft.asset

    @property
    def source_type(self) -> SourceType:
        return self.draft.source_type

    @property
    def source_name(self) -> str:
        return self.draft.source_name

    @property
    def source_url(self) -> str | None:
        return self.draft.source_url

    @property
    def query_or_parameters(self) -> str:
        return self.draft.query_or_parameters

    @property
    def normalized_fact(self) -> str:
        return self.draft.normalized_fact

    @property
    def content_reference(self) -> str:
        return self.draft.content_reference

    @property
    def published_at(self) -> datetime | None:
        return self.draft.published_at

    @property
    def fetched_at(self) -> datetime:
        return self.draft.fetched_at

    @property
    def is_cached(self) -> bool:
        return self.draft.is_cached

    @property
    def cache_time(self) -> datetime | None:
        return self.draft.cache_time

    @property
    def is_stale(self) -> bool:
        return self.draft.is_stale

    @property
    def metric_name(self) -> str | None:
        return self.metric.metric_name if self.metric else None

    @property
    def metric_value(self) -> float | None:
        return self.metric.metric_value if self.metric else None


def pending(
    *,
    source_class: SourceClass,
    asset: Asset | str | None,
    source_type: SourceType | str,
    source_name: str,
    fetched_at: datetime,
    query_or_parameters: str,
    content_reference: str,
    normalized_fact: str,
    source_url: str | None = None,
    published_at: datetime | None = None,
    original_publisher: str | None = None,
    provider_id: str | None = None,
    is_cached: bool = False,
    cache_time: datetime | None = None,
    is_stale: bool = False,
    source_record_id: str | None = None,
    metric_name: str | None = None,
    metric_value: float | None = None,
) -> PendingEvidence:
    """Build a validated draft plus its provenance in one call.

    Asset and source type accept plain strings; Pydantic coerces them to the
    canonical enums and rejects anything outside the allowlist at the point of
    creation rather than at ledger time.
    """
    draft = EvidenceDraft(
        asset=asset,  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        source_name=source_name,
        source_url=source_url,
        published_at=published_at,
        fetched_at=fetched_at,
        query_or_parameters=query_or_parameters,
        content_reference=content_reference,
        normalized_fact=normalized_fact,
        is_cached=is_cached,
        cache_time=cache_time,
        is_stale=is_stale,
        source_record_id=source_record_id,
    )
    metric = (
        MetricValue(metric_name=metric_name, metric_value=float(metric_value))
        if metric_name is not None and metric_value is not None
        else None
    )
    return PendingEvidence(
        draft=draft,
        source_class=source_class,
        original_publisher=original_publisher,
        provider_id=provider_id,
        metric=metric,
    )


def facts_of(items: Sequence[PendingEvidence]) -> list[str]:
    """Normalized facts in order — handy in tests and disclosure messages."""
    return [item.draft.normalized_fact for item in items]
