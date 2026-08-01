"""Evidence Processor: many drafts from many sources become one canonical ledger.

Deterministic, no LLM. This is where the processor-assigned fields are actually
assigned — `reliability` from the static policy table, `independence_group` from
the publisher/domain rule, `content_hash` from the canonicalized fact, and the
run-local `ev_NNN` identifiers. A producer supplies wording and provenance only.

Pipeline (per evidence-contracts):
1. reliability from `source_class` (§4) — never from a producer, never from an LLM.
2. independence group from original publisher, else registered domain, else the
   configured provider id (§5).
3. `content_hash` over the canonicalized fact, with source name/URL/repost time
   excluded so byte-equivalent reposts collapse; exact matching only (§6).
4. rank by reliability, then freshness.
5. exact-hash dedup, keeping the highest-ranked copy.
6. allocate stable ids `ev_001`, `ev_002`, ... in ranked order, then sort the
   ledger by id as §12 requires.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from hoya_agent.evidence.drafts import MetricValue, PendingEvidence
from hoya_agent.evidence.policies import independence_group, reliability_for
from hoya_agent.models import (
    DegradationEvent,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunMode,
)

_REL_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

STAGE_EVIDENCE = "evidence_processor"


def _content_hash(fact: str) -> str:
    """SHA-256 over the canonicalized fact only (lowercased, whitespace-collapsed)."""
    canonical = " ".join(fact.strip().lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _freshness(item: PendingEvidence) -> float:
    when: datetime = item.draft.published_at or item.draft.fetched_at
    return when.timestamp()


def _group_for(item: PendingEvidence) -> str:
    """Independence group by the §5 order, with the source name as last resort."""
    return independence_group(
        original_publisher=item.original_publisher,
        source_url=item.draft.source_url,
        provider_id=item.provider_id or item.draft.source_name,
    )


@dataclass(frozen=True)
class LedgerBuild:
    """The canonical ledger plus what cannot live inside it."""

    ledger: EvidenceLedger
    metric_index: dict[str, MetricValue] = field(default_factory=dict)
    dropped_duplicates: int = 0


def _event(now: datetime, *, event_type: str, source: str, message: str) -> DegradationEvent:
    return DegradationEvent(
        stage=STAGE_EVIDENCE,
        event_type=event_type,
        source=source,
        message=message,
        timestamp=now,
    )


def build_ledger(
    items: Sequence[PendingEvidence],
    *,
    run_id: str,
    analysis_as_of: datetime,
    run_mode: RunMode,
    existing: Sequence[EvidenceItem] = (),
    existing_metrics: Mapping[str, MetricValue] | None = None,
    degradation_messages: Sequence[str] = (),
    degradation_events: Sequence[DegradationEvent] = (),
    now: datetime | None = None,
) -> LedgerBuild:
    """Assign reliability, grouping, hashes and ids, then dedup and rank.

    `existing` admits items that were already processed in this run — the market
    branch's ledger when the research branch arrives later. Their reliability,
    group and hash are reused rather than recomputed, but ids are reassigned across
    the merged set so the ledger stays contiguous. `existing_metrics` is remapped by
    content hash, because a metric keyed to an old id would silently point at the
    wrong evidence after the merge.
    """
    stamp = now or analysis_as_of
    events: list[DegradationEvent] = list(degradation_events)

    # (reliability rank, -freshness, input order, hash, reliability, group, source)
    scored: list[tuple[int, float, int, str, str, str, Any]] = []
    metrics_by_hash: dict[str, MetricValue] = {}
    position = 0

    for item in existing:
        reliability = str(getattr(item.reliability, "value", item.reliability))
        when = item.published_at or item.fetched_at
        scored.append(
            (
                _REL_RANK[reliability],
                -when.timestamp(),
                position,
                item.content_hash,
                reliability,
                item.independence_group,
                item,
            )
        )
        metric = (existing_metrics or {}).get(item.evidence_id)
        if metric is not None:
            metrics_by_hash.setdefault(item.content_hash, metric)
        position += 1

    for item in items:
        reliability = reliability_for(item.source_class)
        try:
            group = _group_for(item)
        except ValueError:
            events.append(
                _event(
                    stamp,
                    event_type="independence_group_unavailable",
                    source=item.draft.source_name,
                    message=(
                        f"{item.draft.source_name}：無法判定 independence_group，"
                        "該筆證據未納入 Ledger。"
                    ),
                )
            )
            continue
        digest = _content_hash(item.draft.normalized_fact)
        scored.append(
            (
                _REL_RANK[reliability],
                -_freshness(item),
                position,
                digest,
                reliability,
                group,
                item,
            )
        )
        if item.metric is not None:
            metrics_by_hash.setdefault(digest, item.metric)
        position += 1

    scored.sort(key=lambda row: (row[0], row[1], row[2]))

    seen: set[str] = set()
    admitted: list[EvidenceItem] = []
    metric_index: dict[str, MetricValue] = {}
    dropped = 0

    for _rank, _fresh, _position, digest, reliability, group, source in scored:
        if digest in seen:
            dropped += 1
            continue
        evidence_id = f"ev_{len(admitted) + 1:03d}"
        draft = source.draft if isinstance(source, PendingEvidence) else source
        try:
            admitted.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    asset=draft.asset,
                    source_type=draft.source_type,
                    source_name=draft.source_name,
                    source_url=draft.source_url,
                    published_at=draft.published_at,
                    fetched_at=draft.fetched_at,
                    query_or_parameters=draft.query_or_parameters,
                    content_reference=draft.content_reference,
                    normalized_fact=draft.normalized_fact,
                    reliability=Reliability(reliability),
                    independence_group=group,
                    content_hash=digest,
                    is_cached=draft.is_cached,
                    cache_time=draft.cache_time,
                    is_stale=draft.is_stale,
                )
            )
        except ValidationError as exc:
            events.append(
                _event(
                    stamp,
                    event_type="evidence_rejected",
                    source=draft.source_name,
                    message=f"{draft.source_name}：證據未通過契約驗證（{type(exc).__name__}），已排除。",
                )
            )
            continue
        seen.add(digest)
        metric = metrics_by_hash.get(digest)
        if metric is not None:
            metric_index[evidence_id] = metric

    if dropped:
        events.append(
            _event(
                stamp,
                event_type="exact_duplicate_collapsed",
                source=STAGE_EVIDENCE,
                message=f"以 content_hash 精確去重，收合 {dropped} 筆重複證據。",
            )
        )

    for message in degradation_messages:
        events.append(
            _event(stamp, event_type="metric_unavailable", source="market_worker", message=message)
        )

    if not admitted and not events:
        # models.EvidenceLedger rejects an empty ledger with no stated reason.
        events.append(
            _event(
                stamp,
                event_type="no_evidence",
                source=STAGE_EVIDENCE,
                message="本次 run 未取得任何可用證據，且未記錄其他降級原因。",
            )
        )

    ledger = EvidenceLedger(
        run_id=run_id,
        analysis_as_of=analysis_as_of,
        run_mode=run_mode,
        items=sorted(admitted, key=lambda entry: entry.evidence_id),
        conflict_indicators=[],
        degradation_events=events,
    )
    return LedgerBuild(ledger=ledger, metric_index=metric_index, dropped_duplicates=dropped)
