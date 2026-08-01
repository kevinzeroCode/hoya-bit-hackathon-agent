"""Cross-source triangulation: does a market move line up with independent news?

The strongest form of trust distillation is not "many sources said X" but
"different *kinds* of source, gathered independently, point at the same event."
This module aligns deterministic market anomaly days (large standardized daily
returns) with dated research evidence (news / social) published around the same
day, and reports how many distinct source *types* and independence groups
corroborate each event.

Deterministic and dependency-free (🚫 no LLM, no network). It reads only already
-collected, already-grounded evidence, so it invents nothing and adds no field to
the `EvidenceItem` schema — a `TriangulatedEvent` is a derived view, produced
alongside the ledger for the Arbiter and the trust-funnel UI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from hoya_agent.data.price_analysis import AnomalyDay
from hoya_agent.evidence.types import EvidenceItem

# Source types that describe the whole market rather than one coin (e.g. Fear &
# Greed). They corroborate any asset's event regardless of the item's `asset`.
WHOLE_MARKET_SOURCE_TYPES: frozenset[str] = frozenset({"macro"})


@dataclass(frozen=True)
class TriangulatedEvent:
    day: date
    asset: str
    simple_return: float
    z: float
    corroborating_evidence_ids: tuple[str, ...]
    source_types: tuple[str, ...]        # distinct, always includes "market"
    independence_groups: tuple[str, ...]  # distinct, across corroborating evidence
    strength: int                         # number of distinct source types (>=1)
    note: str


def _matches(item: EvidenceItem, *, asset: str, lo: date, hi: date) -> bool:
    if item.published_at is None:
        return False
    published = item.published_at.date()
    if not (lo <= published <= hi):
        return False
    whole_market = item.source_type in WHOLE_MARKET_SOURCE_TYPES or item.asset is None
    return whole_market or item.asset == asset


def triangulate(
    anomalies: Sequence[AnomalyDay],
    evidence_items: Sequence[EvidenceItem],
    *,
    asset: str,
    window_days: int = 1,
) -> list[TriangulatedEvent]:
    """Align each market anomaly day with research evidence published nearby.

    `window_days` is the ± tolerance (in calendar days) between the anomaly day
    and an item's `published_at`. Market anomalies with no nearby research still
    appear, at `strength == 1` (market only) — an honest "unexplained move".
    Sorted by corroboration strength (desc), then most extreme move, then day.
    """
    events: list[TriangulatedEvent] = []
    for a in anomalies:
        lo, hi = a.day - timedelta(days=window_days), a.day + timedelta(days=window_days)
        matched = [it for it in evidence_items if _matches(it, asset=asset, lo=lo, hi=hi)]

        source_types = {"market"} | {it.source_type for it in matched}
        groups = {it.independence_group for it in matched}
        ids = tuple(it.evidence_id for it in matched)
        strength = len(source_types)

        if strength >= 2:
            note = (
                f"{a.day} 市場異動(日報酬 {a.simple_return:+.2%},z={a.z:+.2f})"
                f"獲 {strength} 類來源、{len(groups)} 個獨立群佐證"
            )
        else:
            note = f"{a.day} 市場異動(日報酬 {a.simple_return:+.2%},z={a.z:+.2f}),無獨立研究來源佐證"

        events.append(
            TriangulatedEvent(
                day=a.day,
                asset=asset,
                simple_return=a.simple_return,
                z=a.z,
                corroborating_evidence_ids=ids,
                source_types=tuple(sorted(source_types)),
                independence_groups=tuple(sorted(groups)),
                strength=strength,
                note=note,
            )
        )

    events.sort(key=lambda e: (-e.strength, -abs(e.z), e.day))
    return events
