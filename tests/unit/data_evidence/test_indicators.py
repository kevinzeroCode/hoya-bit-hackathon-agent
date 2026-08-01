"""Golden tests for deterministic market indicators.

Two layers:
1. Hand-computable mini fixtures — exact values verifiable by hand.
2. Real-data golden values (from the organizer CSVs, all five coins) — proves
   the functions reproduce the EDA and that the pipeline is coin-agnostic.
   Skipped automatically if the organizer dataset is not reachable.
"""

from __future__ import annotations

import csv

import pytest

from hoya_agent.adapters.organizer_csv import default_data_dir
from hoya_agent.data.indicators import (
    max_drawdown,
    realized_volatility,
    relative_change,
    rolling_volume_zscore,
    simple_return,
)

# --- Layer 1: hand-computable mini fixtures -------------------------------


def test_simple_return_window_1():
    assert simple_return([100.0, 102.0, 101.0, 105.0], 1) == pytest.approx(105 / 101 - 1)


def test_simple_return_window_3():
    assert simple_return([100.0, 102.0, 101.0, 105.0], 3) == pytest.approx(0.05)


def test_realized_volatility_symmetric_returns():
    # returns = [+0.1, -0.1] -> mean 0, sample std = sqrt(0.02)
    assert realized_volatility([100.0, 110.0, 99.0], 2) == pytest.approx(0.02**0.5)


def test_max_drawdown_clear_drop():
    # running max 100,120,120,120 -> ratios 0, .2, -.25, -.083 -> min -0.25
    assert max_drawdown([100.0, 120.0, 90.0, 110.0], 4) == pytest.approx(-0.25)


def test_max_drawdown_monotonic_is_zero():
    assert max_drawdown([100.0, 101.0, 102.0], 3) == pytest.approx(0.0)


def test_rolling_volume_zscore():
    # last=30, mean=20, sample std=10 -> z = 1.0
    assert rolling_volume_zscore([10.0, 20.0, 30.0], 3) == pytest.approx(1.0)


def test_relative_change():
    assert relative_change(0.05, 0.02) == pytest.approx(1.5)


def test_not_enough_data_raises():
    with pytest.raises(ValueError):
        simple_return([100.0], 5)


# --- Layer 2: real-data golden values (all five coins) --------------------

_DATA_DIR = default_data_dir()

# EDA golden values through 2026-05-31 (see CLAUDE.md).
GOLDEN = {
    "BTC": {"return_14d": -0.048843, "vol_30d": 0.013045, "mdd_90d": -0.118499},
    "ETH": {"return_14d": -0.058184, "vol_30d": 0.014900, "mdd_90d": -0.170314},
    "SOL": {"return_14d": -0.032848, "vol_30d": 0.020598, "mdd_90d": -0.179418},
    "BNB": {"return_14d": 0.094029, "vol_30d": 0.024817, "mdd_90d": -0.141516},
    "XRP": {"return_14d": -0.048944, "vol_30d": 0.017913, "mdd_90d": -0.152560},
}


def _load_closes(asset: str) -> list[float]:
    path = _DATA_DIR / f"{asset}_daily_ohlcv.csv"
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [float(r["close"]) for r in rows]


@pytest.mark.skipif(not _DATA_DIR.exists(), reason="organizer dataset not reachable")
@pytest.mark.parametrize("asset", ["BTC", "ETH", "SOL", "BNB", "XRP"])
def test_real_data_golden(asset: str):
    closes = _load_closes(asset)
    g = GOLDEN[asset]
    assert simple_return(closes, 14) == pytest.approx(g["return_14d"], abs=1e-6)
    assert realized_volatility(closes, 30) == pytest.approx(g["vol_30d"], abs=1e-6)
    assert max_drawdown(closes, 90) == pytest.approx(g["mdd_90d"], abs=1e-6)
