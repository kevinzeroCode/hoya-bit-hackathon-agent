"""Deterministic Requirement 16 trust scorecards.

The scorecard exposes ledger properties; it never creates a confidence
percentage and never calls an LLM or an external source.
"""

from __future__ import annotations

from datetime import datetime

from hoya_agent.models import (
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    ConsistencyDimension,
    EvidenceLedger,
    FreshnessDimension,
    Reliability,
    ReliabilityMix,
    SourceDiversityDimension,
    SourceIndependenceDimension,
    Stance,
    TrustLevel,
    TrustScorecard,
)


def _count_level(count: int) -> TrustLevel:
    if count >= 3:
        return TrustLevel.strong
    if count == 2:
        return TrustLevel.moderate
    if count == 1:
        return TrustLevel.weak
    return TrustLevel.unavailable


def build_trust_scorecards(
    ledger: EvidenceLedger,
    links: list[ClaimEvidenceLink],
    conclusions: list[Claim],
    *,
    analysis_as_of: datetime | None = None,
    fresh_window_hours: float = 48.0,
) -> list[TrustScorecard]:
    """Build one scorecard for each conclusion, preserving input order."""
    cutoff = analysis_as_of or ledger.analysis_as_of
    by_id = {item.evidence_id: item for item in ledger.items}
    conflict_claims = {indicator.claim_id for indicator in ledger.conflict_indicators}
    cards: list[TrustScorecard] = []

    for claim in conclusions:
        if claim.claim_type is not ClaimType.conclusion:
            continue
        claim_links = [link for link in links if link.claim_id == claim.claim_id]
        linked = [by_id[link.evidence_id] for link in claim_links if link.evidence_id in by_id]
        supporting = [
            by_id[link.evidence_id]
            for link in claim_links
            if link.stance is Stance.supports and link.evidence_id in by_id
        ]
        groups = {item.independence_group for item in linked}
        source_types = {item.source_type for item in linked}
        opposing_count = sum(link.stance is Stance.opposes for link in claim_links)
        material_conflict = claim.claim_id in conflict_claims
        consistency_level = (
            TrustLevel.weak
            if material_conflict
            else TrustLevel.strong if opposing_count == 0 else TrustLevel.moderate
        )

        usable_times = [item.published_at or item.fetched_at for item in supporting]
        newest_age: float | None = None
        if usable_times:
            newest_age = max(0.0, (cutoff - max(usable_times)).total_seconds() / 3600)
        has_stale = any(item.is_stale for item in supporting)
        freshness_level = TrustLevel.unavailable
        if newest_age is not None:
            if has_stale:
                freshness_level = TrustLevel.weak
            elif newest_age <= fresh_window_hours:
                freshness_level = TrustLevel.strong
            else:
                freshness_level = TrustLevel.moderate

        mix = {level: 0 for level in Reliability}
        for item in linked:
            mix[item.reliability] += 1
        cards.append(
            TrustScorecard(
                claim_id=claim.claim_id,
                source_independence=SourceIndependenceDimension(
                    level=_count_level(len(groups)), distinct_groups=len(groups)
                ),
                source_diversity=SourceDiversityDimension(
                    level=_count_level(len(source_types)),
                    distinct_source_types=len(source_types),
                ),
                reliability_mix=ReliabilityMix(
                    high=mix[Reliability.high],
                    medium=mix[Reliability.medium],
                    low=mix[Reliability.low],
                ),
                consistency=ConsistencyDimension(
                    level=consistency_level,
                    has_material_conflict=material_conflict,
                    opposing_count=opposing_count,
                ),
                freshness=FreshnessDimension(
                    level=freshness_level,
                    newest_evidence_age_hours=newest_age,
                    has_stale=has_stale,
                ),
                rationale=(
                    f"{len(groups)} 個獨立來源群組、{len(source_types)} 種來源；"
                    f"反向證據 {opposing_count} 筆，material conflict="
                    f"{'是' if material_conflict else '否'}。"
                ),
            )
        )
    return cards


__all__ = ["build_trust_scorecards"]
