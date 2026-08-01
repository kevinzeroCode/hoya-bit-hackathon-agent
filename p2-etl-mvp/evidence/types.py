"""Provisional evidence types for the P2 ETL prototype.

`EvidenceDraft` is the pre-ledger form: everything an EvidenceItem needs except
the ledger-assigned `evidence_id` and `content_hash` (the Evidence Processor
adds those). Swap for P1's canonical `models.py` when it lands; keep field names
identical so the swap is mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from evidence.policies import Reliability


@dataclass(frozen=True)
class EvidenceDraft:
    asset: str | None
    source_type: str  # "market" | "news" | "social" | "official"
    source_name: str
    source_url: str | None
    published_at: datetime | None
    fetched_at: datetime  # timezone-aware UTC
    query_or_parameters: str  # reproducibility params; never secrets
    content_reference: str
    normalized_fact: str
    reliability: Reliability
    independence_group: str
    is_cached: bool = False
    cache_time: datetime | None = None
    is_stale: bool = False
    metric_name: str | None = None
    metric_value: float | None = None


@dataclass(frozen=True)
class EvidenceItem:
    """A ledger-admitted EvidenceDraft: same fields plus a stable id and hash."""

    evidence_id: str
    content_hash: str
    asset: str | None
    source_type: str
    source_name: str
    source_url: str | None
    published_at: datetime | None
    fetched_at: datetime
    query_or_parameters: str
    content_reference: str
    normalized_fact: str
    reliability: Reliability
    independence_group: str
    is_cached: bool = False
    cache_time: datetime | None = None
    is_stale: bool = False
    metric_name: str | None = None
    metric_value: float | None = None


@dataclass(frozen=True)
class EvidenceLedger:
    """The unified, deduped, ranked evidence set — one shape for all sources."""

    items: list[EvidenceItem]
    dropped_duplicates: int

    @property
    def source_type_count(self) -> int:
        return len({i.source_type for i in self.items})

    @property
    def independence_group_count(self) -> int:
        return len({i.independence_group for i in self.items})

    def top(self, n: int) -> list[EvidenceItem]:
        """The top-ranked n items — what gets passed to the Arbiter."""
        return self.items[:n]
