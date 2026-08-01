from datetime import date

from hoya_agent.data.regime import classify_market_regime
from hoya_agent.models import Asset, RegimeLabel


def test_missing_bars_returns_unavailable() -> None:
    regime = classify_market_regime(
        Asset.BTC,
        [],
        analysis_as_of=date(2026, 5, 31),
    )
    assert regime.label is RegimeLabel.unavailable
    assert regime.metrics == {}
    assert regime.evidence_id is None
