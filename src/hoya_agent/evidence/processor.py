"""Evidence Processor: merge drafts from every source into one clean ledger.

Deterministic, no LLM. This is the "先處理" step: many scattered EvidenceDrafts
(market, news, LLM-extracted, sentiment) become a single ranked, deduplicated
ledger with stable IDs — one uniform shape ready for the Arbiter.

Pipeline (per evidence-contracts):
1. content_hash over the canonicalized fact (source name/URL excluded, so
   byte-equivalent reposts collapse; no fuzzy/semantic matching).
2. rank by reliability, then freshness.
3. exact-hash dedup, keeping the highest-ranked copy.
4. allocate stable run-local IDs ev_001, ev_002, ... in ranked order.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

from hoya_agent.evidence.policies import Reliability
from hoya_agent.evidence.types import EvidenceDraft, EvidenceItem, EvidenceLedger

_REL_RANK: dict[Reliability, int] = {"high": 0, "medium": 1, "low": 2}


def _content_hash(fact: str) -> str:
    """SHA-256 over the canonicalized fact only (lowercased, whitespace-collapsed)."""
    canonical = " ".join(fact.strip().lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _freshness(draft: EvidenceDraft) -> float:
    when: datetime = draft.published_at or draft.fetched_at
    return when.timestamp()


def build_ledger(
    drafts: Sequence[EvidenceDraft], *, max_for_arbiter: int = 30
) -> EvidenceLedger:
    # Rank first: highest reliability, then most recent. Ties keep input order (stable sort).
    ranked = sorted(
        drafts, key=lambda d: (_REL_RANK[d.reliability], -_freshness(d))
    )

    # Exact-hash dedup, keeping the first (best-ranked) copy of each fact.
    seen: set[str] = set()
    items: list[EvidenceItem] = []
    dropped = 0
    for draft in ranked:
        h = _content_hash(draft.normalized_fact)
        if h in seen:
            dropped += 1
            continue
        seen.add(h)
        items.append(
            EvidenceItem(
                evidence_id=f"ev_{len(items) + 1:03d}",
                content_hash=h,
                asset=draft.asset,
                source_type=draft.source_type,
                source_name=draft.source_name,
                source_url=draft.source_url,
                published_at=draft.published_at,
                fetched_at=draft.fetched_at,
                query_or_parameters=draft.query_or_parameters,
                content_reference=draft.content_reference,
                normalized_fact=draft.normalized_fact,
                reliability=draft.reliability,
                independence_group=draft.independence_group,
                is_cached=draft.is_cached,
                cache_time=draft.cache_time,
                is_stale=draft.is_stale,
                metric_name=draft.metric_name,
                metric_value=draft.metric_value,
            )
        )

    return EvidenceLedger(items=items, dropped_duplicates=dropped)
