from datetime import UTC, datetime, timedelta

from hoya_agent.evidence.trust import build_trust_scorecards
from hoya_agent.models import (
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunMode,
    SourceType,
    Stance,
    TimeRange,
    TrustLevel,
)

CUTOFF = datetime(2026, 5, 31, tzinfo=UTC)


def _item(index: int, group: str, source_type: SourceType) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev_{index:03d}",
        asset=Asset.BTC,
        source_type=source_type,
        source_name=group,
        fetched_at=CUTOFF - timedelta(hours=index),
        published_at=CUTOFF - timedelta(hours=index),
        query_or_parameters="fixture=true",
        content_reference=f"row {index}",
        normalized_fact=f"可手算事實 {index}",
        reliability=Reliability.high,
        independence_group=group,
        content_hash=f"{index:064x}",
    )


def test_scorecard_uses_fixed_ordinal_mappings() -> None:
    items = [
        _item(1, "g1", SourceType.market),
        _item(2, "g2", SourceType.news),
        _item(3, "g3", SourceType.official),
    ]
    ledger = EvidenceLedger(
        run_id="run_20260531_000000_trust",
        analysis_as_of=CUTOFF,
        run_mode=RunMode.rehearsal,
        items=items,
    )
    conclusion = Claim(
        claim_id="cl_002",
        claim_type=ClaimType.conclusion,
        assets=[Asset.BTC],
        time_range=TimeRange(start="2026-05-01", end="2026-05-31"),
        text="測試結論",
        based_on_claim_ids=["cl_001"],
        confidence=Reliability.high,
    )
    links = [
        ClaimEvidenceLink(
            claim_id="cl_002",
            evidence_id=item.evidence_id,
            stance=Stance.supports,
            reason="fixture support",
        )
        for item in items
    ]
    card = build_trust_scorecards(ledger, links, [conclusion])[0]
    assert card.source_independence.level is TrustLevel.strong
    assert card.source_diversity.level is TrustLevel.strong
    assert card.consistency.level is TrustLevel.strong
    assert card.freshness.level is TrustLevel.strong


def test_scorecard_is_only_created_for_conclusions() -> None:
    fact = Claim(
        claim_id="cl_001",
        claim_type=ClaimType.fact,
        assets=[Asset.BTC],
        time_range=TimeRange(start="2026-05-01", end="2026-05-31"),
        text="測試事實",
        confidence=Reliability.high,
    )
    ledger = EvidenceLedger(
        run_id="run_20260531_000000_trust",
        analysis_as_of=CUTOFF,
        run_mode=RunMode.rehearsal,
        items=[_item(1, "g1", SourceType.market)],
    )
    assert build_trust_scorecards(ledger, [], [fact]) == []
