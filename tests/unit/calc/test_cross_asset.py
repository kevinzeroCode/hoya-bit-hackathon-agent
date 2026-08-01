"""Golden-value tests for two-asset relationships, benchmarked against BTC."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calc.cross_asset import (
    align,
    dispersion,
    relative_return,
    relative_strength_percentile,
    relative_strength_ratio,
    rolling_beta,
    rolling_correlation,
)


def test_align_keeps_only_shared_dates():
    """Assets list at different times; an unaligned join compares wrong days."""
    idx_a = pd.date_range("2024-01-01", periods=5)
    idx_b = pd.date_range("2024-01-03", periods=5)
    a, b = align(pd.Series(range(5), index=idx_a), pd.Series(range(5), index=idx_b))

    assert len(a) == len(b) == 3
    assert a.index.equals(b.index)


def test_perfectly_correlated_series_give_correlation_one_and_beta_of_the_scale():
    idx = pd.date_range("2024-01-01", periods=200)
    rng = np.random.default_rng(7)
    benchmark = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 200))), index=idx)
    # Same log returns, doubled -> correlation 1, beta 2.
    doubled = pd.Series(100 * np.exp(2 * np.log(benchmark / benchmark.iloc[0])), index=idx)

    assert rolling_correlation(doubled, benchmark, 90).iloc[-1] == pytest.approx(1.0)
    assert rolling_beta(doubled, benchmark, 90).iloc[-1] == pytest.approx(2.0)


@pytest.mark.parametrize(
    "asset,expected_corr,expected_beta",
    [("ETH", 0.93, 1.23), ("SOL", 0.86, 1.12), ("XRP", 0.86, 0.89), ("BNB", 0.71, 0.72)],
)
def test_correlation_and_beta_vs_btc_match_report(closes, asset, expected_corr, expected_beta):
    btc = closes["BTC"]

    assert rolling_correlation(closes[asset], btc, 90).iloc[-1] == pytest.approx(expected_corr, abs=0.005)
    assert rolling_beta(closes[asset], btc, 90).iloc[-1] == pytest.approx(expected_beta, abs=0.005)


@pytest.mark.parametrize(
    "asset,expected",
    [("BNB", 0.71), ("ETH", 0.13), ("SOL", 0.08), ("XRP", 0.08)],
)
def test_relative_strength_percentile_matches_report(closes, asset, expected):
    """Pins the trailing window at 365 bars.

    The report calls this a "1 year percentile". A 252-bar window (the equity
    convention) gives materially different answers -- ETH ranks 0.8th rather
    than 13th -- so the two are not interchangeable here.
    """
    result = relative_strength_percentile(closes[asset], closes["BTC"], window=365)

    assert result == pytest.approx(expected, abs=0.006)


def test_bnb_decoupled_while_the_others_moved_together(closes):
    """The triage signal: one asset needs its own explanation, three do not."""
    btc = closes["BTC"]

    assert relative_return(closes["BNB"], btc, 30) == pytest.approx(0.226, abs=0.002)
    assert relative_strength_percentile(closes["BNB"], btc) > 0.5

    for asset in ("ETH", "SOL", "XRP"):
        assert relative_strength_percentile(closes[asset], btc) < 0.2
        assert rolling_correlation(closes[asset], btc, 90).iloc[-1] > 0.85

    assert rolling_correlation(closes["BNB"], btc, 90).iloc[-1] < 0.75


def test_relative_strength_percentile_is_nan_without_a_full_window(closes):
    """A partial window yields no rank rather than a rank over less data."""
    short = closes["ETH"].iloc[:100]

    assert np.isnan(relative_strength_percentile(short, closes["BTC"].iloc[:100], window=365))


def test_relative_strength_ratio_moves_with_outperformance():
    idx = pd.date_range("2024-01-01", periods=3)
    asset = pd.Series([100.0, 110.0, 120.0], index=idx)
    benchmark = pd.Series([100.0, 100.0, 100.0], index=idx)

    ratio = relative_strength_ratio(asset, benchmark)

    assert ratio.is_monotonic_increasing
    assert ratio.iloc[-1] == pytest.approx(1.2)


def test_relative_return_composes_growth_factors():
    idx = pd.date_range("2024-01-01", periods=3)
    asset = pd.Series([100.0, 100.0, 120.0], index=idx)
    benchmark = pd.Series([100.0, 100.0, 110.0], index=idx)

    # 1.20 / 1.10 - 1, not 20% - 10%.
    assert relative_return(asset, benchmark, 2) == pytest.approx(1.2 / 1.1 - 1)


def test_dispersion_is_near_zero_when_a_group_moves_as_one_block():
    idx = pd.date_range("2024-01-01", periods=40)
    lockstep = {
        name: pd.Series(np.linspace(100, 120, 40), index=idx) for name in ("A", "B", "C")
    }

    assert dispersion(lockstep, 30) == pytest.approx(0.0, abs=1e-12)


def test_dispersion_requires_at_least_two_assets():
    idx = pd.date_range("2024-01-01", periods=40)

    assert np.isnan(dispersion({"A": pd.Series(np.linspace(1, 2, 40), index=idx)}, 30))
