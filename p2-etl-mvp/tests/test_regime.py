"""Tests for market regime classification (deterministic synthesis of indicators)."""

from __future__ import annotations

from datetime import date, timedelta

from data.market_worker import WorkerResult
from data.regime import MarketRegime, build_regime_evidence, classify_regime
from data.types import MarketBar


def bars_from_returns(rets: list[float], start: float = 100.0, start_date: date = date(2026, 1, 1)) -> list[MarketBar]:
    price = start
    bars = [MarketBar(start_date, price, price, price, price, 1000.0)]
    for i, r in enumerate(rets, 1):
        price *= 1 + r
        bars.append(MarketBar(start_date + timedelta(days=i), price, price * 1.001, price * 0.999, price, 1000.0))
    return bars


def _classify(bars):
    return classify_regime("BTC", bars, analysis_as_of=bars[-1].date)


def test_trending_up():
    # noisy history, then a steady low-vol rise (~+13% over 14d)
    bars = bars_from_returns([0.03, -0.03] * 45 + [0.009] * 40)
    r = _classify(bars)
    assert isinstance(r, MarketRegime)
    assert r.label == "trending_up"


def test_trending_down():
    bars = bars_from_returns([0.03, -0.03] * 45 + [-0.009] * 40)
    assert _classify(bars).label == "trending_down"


def test_range_bound():
    # varied high-vol history, then a flat calm stretch (return ~0, vol not top-percentile)
    bars = bars_from_returns([0.03, -0.03, 0.02, -0.02, 0.04, -0.04] * 15 + [0.001, -0.001] * 20)
    assert _classify(bars).label == "range_bound"


def test_high_volatility():
    # calm history, then a wild recent stretch -> current vol in top percentile
    bars = bars_from_returns([0.005] * 90 + [0.06, -0.06] * 20)
    assert _classify(bars).label == "high_volatility"


def test_too_few_bars_returns_none():
    assert classify_regime("BTC", bars_from_returns([0.01] * 10), analysis_as_of=date(2026, 1, 20)) is None


def test_build_regime_evidence_is_high_market_draft():
    bars = bars_from_returns([0.03, -0.03] * 45 + [0.009] * 40)
    result = build_regime_evidence("BTC", bars, analysis_as_of=bars[-1].date)
    assert isinstance(result, WorkerResult)
    assert result.status == "completed"
    d = result.drafts[0]
    assert d.source_type == "market"
    assert d.reliability == "high"
    assert d.metric_name == "market_regime"
    assert d.asset == "BTC"
    assert d.normalized_fact.strip()
