from datetime import UTC, datetime

from hoya_agent.models import Asset, EvidenceItem, Reliability, SourceType
from hoya_agent.orchestration.pipeline import select_balanced_evidence


def _item(index: int, asset: Asset, source_type: SourceType) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev_{index:03d}", asset=asset, source_type=source_type,
        source_name="fixture", fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
        query_or_parameters="fixture=true", content_reference=f"row {index}",
        normalized_fact=f"fact {index}", reliability=Reliability.high,
        independence_group=f"g-{asset.value}-{source_type.value}",
        content_hash=f"{index:064x}",
    )


def test_dual_asset_budget_keeps_both_assets_and_source_diversity() -> None:
    items = [
        *[_item(i, Asset.BTC, SourceType.market) for i in range(1, 20)],
        _item(20, Asset.ETH, SourceType.market),
        _item(21, Asset.ETH, SourceType.news),
    ]
    selected = select_balanced_evidence(items, 6)
    assert {item.asset for item in selected} == {Asset.BTC, Asset.ETH}
    assert {item.source_type for item in selected} == {SourceType.market, SourceType.news}
