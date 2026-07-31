"""Tests for A5/A6/A7 price-analysis outputs (ported from the `price` design doc).

Two layers: hand-computable unit tests, and real-data golden values that must
reproduce the design doc's published figures (proves spec alignment).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from adapters.organizer_csv import default_data_dir, load_organizer_csv
from data.market_series import closes
from data.price_analysis import (
    analog_base_rates,
    anomaly_days,
    attribution,
    daily_log_returns,
    rolling_beta,
    rolling_correlation,
    _quantile,
)
from data.types import MarketBar

_DATA_DIR = default_data_dir()


def _bars(prices: list[float]) -> list[MarketBar]:
    start = date(2024, 1, 1)
    return [
        MarketBar(date=start + timedelta(days=i), open=p, high=p, low=p, close=p, volume=100.0)
        for i, p in enumerate(prices)
    ]


# ── unit ────────────────────────────────────────────────────────────────────

def test_quantile_linear():
    assert _quantile([10, 20, 30, 40, 50], 0.0) == 10
    assert _quantile([10, 20, 30, 40, 50], 0.5) == 30
    assert _quantile([10, 20, 30, 40], 0.2) == pytest.approx(16.0)


def test_log_returns_length():
    assert len(daily_log_returns([1.0, 2.0, 4.0])) == 2


def test_correlation_and_beta_of_series_with_itself():
    cl = [100.0, 102.0, 101.0, 105.0, 108.0, 104.0, 110.0]
    assert rolling_correlation(cl, cl, window=5) == pytest.approx(1.0)
    assert rolling_beta(cl, cl, window=5) == pytest.approx(1.0)


def test_anomaly_flags_a_single_spike():
    prices = [100.0] * 20 + [100.0 * 1.5] + [150.0] * 5  # one +50% jump
    events = anomaly_days(_bars(prices), sigma=2.0, min_history=10)
    assert len(events) == 1
    assert events[0].simple_return == pytest.approx(0.5)
    assert events[0].z > 2.0


def test_anomaly_needs_min_history():
    with pytest.raises(ValueError):
        anomaly_days(_bars([100.0] * 5), min_history=365)


# ── real-data golden (must reproduce the design doc) ────────────────────────

_HAVE_DATA = (_DATA_DIR / "BTC_daily_ohlcv.csv").exists()

# doc A6: full-period ±3σ day counts
_ANOMALY_GOLDEN = {"BTC": 35, "ETH": 30, "SOL": 22, "BNB": 27, "XRP": 34}


@pytest.mark.skipif(not _HAVE_DATA, reason="organizer dataset not reachable")
@pytest.mark.parametrize("asset,count", list(_ANOMALY_GOLDEN.items()))
def test_anomaly_counts_match_doc(asset: str, count: int):
    bars = load_organizer_csv(_DATA_DIR / f"{asset}_daily_ohlcv.csv")
    assert len(anomaly_days(bars)) == count


@pytest.mark.skipif(not _HAVE_DATA, reason="organizer dataset not reachable")
def test_2026_02_05_is_a_synchronized_crash_day():
    # doc: 2026-02-05 all five coins fell > 3σ.
    for asset in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
        bars = load_organizer_csv(_DATA_DIR / f"{asset}_daily_ohlcv.csv")
        hits = {e.day: e for e in anomaly_days(bars)}
        assert date(2026, 2, 5) in hits
        assert hits[date(2026, 2, 5)].simple_return < 0


@pytest.mark.skipif(not _HAVE_DATA, reason="organizer dataset not reachable")
def test_attribution_eth_vs_btc_matches_doc():
    eth = closes(load_organizer_csv(_DATA_DIR / "ETH_daily_ohlcv.csv"))
    btc = closes(load_organizer_csv(_DATA_DIR / "BTC_daily_ohlcv.csv"))
    attr = attribution(eth, btc, corr_window=90)
    assert attr.correlation == pytest.approx(0.93, abs=0.02)   # doc 0.93
    assert attr.beta == pytest.approx(1.23, abs=0.05)          # doc 1.23


@pytest.mark.skipif(not _HAVE_DATA, reason="organizer dataset not reachable")
def test_base_rates_magnitude_matches_doc():
    btc = load_organizer_csv(_DATA_DIR / "BTC_daily_ohlcv.csv")
    br = analog_base_rates(btc)
    assert br.vol_higher_frac == pytest.approx(0.775, abs=0.02)  # doc 77.5%
    assert 0.4 < br.up_frac < 0.65  # doc: direction ≈ coin-flip
