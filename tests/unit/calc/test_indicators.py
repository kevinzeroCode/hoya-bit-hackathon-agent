"""Golden-value tests for single-asset indicators.

Values are taken from ``docs/price-data-analysis-outputs.html`` (as of
2026-05-31) and independently recomputed from the shipped CSVs. Where the
document and the data disagree, the test asserts the data and says so.

These golden values also pin the methodology: several were only reproducible
under one specific convention (sqrt(365) annualisation, simple-mean ATR, log
returns for skew/kurtosis, demeaned z-scores), so a silent change to any of
those breaks a test here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calc.indicators import (
    all_time_high_stats,
    atr,
    distance_from_ma,
    log_returns,
    max_drawdown,
    multi_horizon_returns,
    price_volume_cross,
    range_position,
    realized_volatility,
    recent_extremes,
    return_distribution,
    return_zscore,
    simple_returns,
    true_range,
    volatility_compression,
    volatility_percentile,
    volume_mean_percentile,
    volume_mean_ratio,
    zscore_anomalies,
)

ALL_ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP")


# --------------------------------------------------------------------------
# hand-computable behaviour
# --------------------------------------------------------------------------

def test_simple_and_log_returns_on_known_values():
    close = pd.Series([100.0, 110.0, 99.0])

    assert simple_returns(close).iloc[1] == pytest.approx(0.10)
    assert simple_returns(close).iloc[2] == pytest.approx(-0.10)
    assert log_returns(close).iloc[1] == pytest.approx(np.log(1.1))


def test_true_range_uses_the_widest_of_the_three_spans():
    # Gap down: |low - prev_close| is wider than the bar's own high-low span.
    high = pd.Series([10.0, 8.0])
    low = pd.Series([9.0, 7.0])
    close = pd.Series([10.0, 7.5])

    assert true_range(high, low, close).iloc[1] == pytest.approx(3.0)


def test_range_position_places_close_within_its_band():
    high = pd.Series([10.0] * 5)
    low = pd.Series([0.0] * 5)
    close = pd.Series([2.5, 2.5, 2.5, 2.5, 2.5])

    assert range_position(close, high, low, window=5).iloc[-1] == pytest.approx(0.25)


def test_range_position_is_nan_for_a_flat_band():
    """A zero-width band has no meaningful position; must not divide by zero."""
    flat = pd.Series([5.0] * 5)

    assert np.isnan(range_position(flat, flat, flat, window=5).iloc[-1])


def test_max_drawdown_measures_peak_to_trough():
    close = pd.Series([100.0, 50.0, 75.0])

    assert max_drawdown(close) == pytest.approx(-0.50)


def test_multi_horizon_returns_reports_nan_beyond_available_history():
    close = pd.Series(np.arange(1.0, 11.0))
    result = multi_horizon_returns(close, horizons=(1, 5, 365))

    assert result[1] == pytest.approx(10 / 9 - 1)
    assert np.isnan(result[365])


# --------------------------------------------------------------------------
# golden values: position and trend
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", -0.0740), ("ETH", -0.1967), ("SOL", -0.2109), ("BNB", -0.0337)],
)
def test_distance_from_ma200_matches_report(closes, asset, expected):
    assert distance_from_ma(closes[asset], 200).iloc[-1] == pytest.approx(expected, abs=5e-4)


def test_xrp_ma200_distance_contradicts_the_report():
    """Documented discrepancy: the report states -19.4% for XRP.

    SMA200 over the shipped CSV gives -19.10%, and the other four assets
    match SMA200 to two decimals, so the method is not in question. (An EMA200
    would give -19.47%, but applying it to XRP alone would be inconsistent.)
    Asserting the data keeps this visible instead of silently absorbed.
    """
    import calc  # local import keeps the fixture-free assertion self-contained

    df = pd.read_csv(
        "HOYA_BIT_crypto_market_dataset/data/XRP_daily_ohlcv.csv", parse_dates=["date"]
    ).sort_values("date").set_index("date")

    assert calc.distance_from_ma(df["close"], 200).iloc[-1] == pytest.approx(-0.1910, abs=5e-4)


@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", 0.21), ("ETH", 0.09), ("SOL", 0.09), ("BNB", 0.17), ("XRP", 0.11)],
)
def test_range_position_52w_matches_report(frames, asset, expected):
    df = frames[asset]
    result = range_position(df["close"], df["high"], df["low"], window=252).iloc[-1]

    assert result == pytest.approx(expected, abs=0.005)


@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", -0.0582), ("ETH", -0.1257), ("SOL", -0.0158), ("BNB", 0.1547), ("XRP", -0.0381)],
)
def test_30d_return_matches_report(closes, asset, expected):
    assert multi_horizon_returns(closes[asset], (30,))[30] == pytest.approx(expected, abs=5e-5)


def test_btc_all_time_high_stats_match_report(frames):
    stats = all_time_high_stats(frames["BTC"]["close"], frames["BTC"]["high"])

    assert stats.ath_close == pytest.approx(124658.54)
    assert stats.ath_close_date == pd.Timestamp("2025-10-06")
    assert stats.days_since_ath_close == 237
    # The report quotes -41.6% while labelling it "distance from ATH close".
    # -41.6% is the drawdown from the all-time intraday HIGH; from the ATH
    # close it is -40.9%. Both are asserted so the two can never be conflated.
    assert stats.drawdown_from_ath_high == pytest.approx(-0.4162, abs=5e-4)
    assert stats.drawdown_from_ath_close == pytest.approx(-0.4090, abs=5e-4)


@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", -0.766), ("ETH", -0.793), ("SOL", -0.963), ("BNB", -0.699), ("XRP", -0.779)],
)
def test_max_drawdown_matches_report(closes, asset, expected):
    assert max_drawdown(closes[asset]) == pytest.approx(expected, abs=1e-3)


# --------------------------------------------------------------------------
# golden values: volatility and risk
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,expected_vol,expected_pct",
    [
        ("BTC", 0.250, 0.02),
        ("ETH", 0.286, 0.00),
        ("SOL", 0.393, 0.00),
        ("BNB", 0.455, 0.37),
        ("XRP", 0.342, 0.02),
    ],
)
def test_realized_volatility_and_percentile_match_report(closes, asset, expected_vol, expected_pct):
    """Pins sqrt(365) annualisation; sqrt(252) would give ~21% for BTC, not 25%."""
    close = closes[asset]

    assert realized_volatility(close, 30).iloc[-1] == pytest.approx(expected_vol, abs=5e-4)
    assert volatility_percentile(close, 30).iloc[-1] == pytest.approx(expected_pct, abs=0.005)


@pytest.mark.parametrize(
    "asset,expected_atr,expected_ratio",
    [("BTC", 1718.77, 0.0233), ("ETH", 67.70, 0.0337), ("SOL", 2.89, 0.0351)],
)
def test_atr14_matches_report(frames, asset, expected_atr, expected_ratio):
    """Pins the simple-mean ATR; Wilder smoothing gives 1839.34 for BTC."""
    df = frames[asset]
    value = atr(df["high"], df["low"], df["close"], 14).iloc[-1]

    assert value == pytest.approx(expected_atr, rel=1e-3)
    assert value / df["close"].iloc[-1] == pytest.approx(expected_ratio, abs=5e-4)


@pytest.mark.parametrize(
    "asset,expected_skew,expected_kurt",
    [("BTC", -0.20, 3.86), ("XRP", 1.36, 18.55)],
)
def test_return_distribution_matches_report(closes, asset, expected_skew, expected_kurt):
    """Pins log returns; simple returns give XRP skew 2.92, not 1.36."""
    skew, kurt = return_distribution(closes[asset])

    assert skew == pytest.approx(expected_skew, abs=0.01)
    assert kurt == pytest.approx(expected_kurt, abs=0.05)


def test_tail_shape_separates_assets_that_share_a_volatility_number(closes):
    """The reason distribution shape is computed at all: volatility hides this."""
    btc_skew, btc_kurt = return_distribution(closes["BTC"])
    xrp_skew, xrp_kurt = return_distribution(closes["XRP"])

    assert xrp_kurt > 4 * btc_kurt
    assert btc_skew < 0 < xrp_skew


# --------------------------------------------------------------------------
# golden values: participation
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", 0.74), ("ETH", 0.55), ("SOL", 0.67), ("BNB", 0.64), ("XRP", 0.64)],
)
def test_volume_mean_ratio_matches_report(frames, asset, expected):
    assert volume_mean_ratio(frames[asset]["volume"]).iloc[-1] == pytest.approx(expected, abs=0.005)


@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", 0.02), ("ETH", 0.08), ("SOL", 0.05), ("BNB", 0.07), ("XRP", 0.02)],
)
def test_volume_percentile_ranks_the_mean_not_the_ratio(frames, asset, expected):
    """Documented mismatch: the report prints these percentiles beside the ratio.

    They are the percentile of the 30-day mean volume, not of the 30/365
    ratio -- the ratio ranks at the 43rd percentile for BTC, not the 2nd.
    Both quantities are legitimate; the pairing in the document is not.
    """
    assert volume_mean_percentile(frames[asset]["volume"], 30).iloc[-1] == pytest.approx(expected, abs=0.006)


@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", 13601), ("ETH", 265688), ("SOL", 2309578), ("BNB", 152069), ("XRP", 87621429)],
)
def test_30d_mean_volume_matches_report(frames, asset, expected):
    assert frames[asset]["volume"].iloc[-30:].mean() == pytest.approx(expected, rel=1e-4)


def test_price_volume_cross_isolates_the_one_confirmed_advance(frames):
    """BNB is the only asset rising on expanding volume -- the report's key claim.

    The exact volume percentage in the document (+35.3%) is not reproducible
    under any window alignment tried (this definition gives +36.8%), so the
    direction and the price leg are asserted rather than that figure.
    """
    results = {
        asset: price_volume_cross(frames[asset]["close"], frames[asset]["volume"], 30)
        for asset in ALL_ASSETS
    }

    assert results["BNB"].direction == "up_on_rising_volume"
    assert results["BNB"].price_change == pytest.approx(0.1547, abs=5e-4)
    assert [a for a, r in results.items() if r.direction == "up_on_rising_volume"] == ["BNB"]

    for asset in ("BTC", "ETH", "SOL"):
        assert results[asset].direction == "down_on_falling_volume"
    assert results["XRP"].direction == "down_on_rising_volume"


# --------------------------------------------------------------------------
# golden values: event timestamps
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,expected",
    [("BTC", 35), ("ETH", 30), ("SOL", 22), ("BNB", 27), ("XRP", 34)],
)
def test_three_sigma_event_counts_match_report(closes, asset, expected):
    """Pins demeaned z-scores; leaving the mean in gives SOL 23 and BNB 26."""
    assert len(zscore_anomalies(closes[asset], 3.0)) == expected


def test_all_five_assets_broke_three_sigma_on_the_same_day(closes):
    """2026-02-05: the only date where every asset exceeded 3 sigma together."""
    event = pd.Timestamp("2026-02-05")
    expected = {"BTC": (-14.02, -5.35), "ETH": (-14.96, -4.33), "SOL": (-14.95, -3.11),
                "BNB": (-12.76, -4.24), "XRP": (-19.67, -5.00)}

    for asset, (ret_pct, z) in expected.items():
        anomalies = zscore_anomalies(closes[asset], 3.0)
        assert event in anomalies.index
        assert anomalies.loc[event, "simple_return"] == pytest.approx(ret_pct / 100, abs=5e-5)
        assert anomalies.loc[event, "zscore"] == pytest.approx(z, abs=0.01)


def test_the_rebound_was_not_as_synchronised_as_the_selloff(closes):
    """2026-02-06: only 3 of 5 cleared 3 sigma, unlike the drop the day before.

    The asymmetry is the point -- a synchronised fall and a fragmented
    recovery are different situations, and the threshold has to be applied
    consistently for that difference to be visible at all.
    """
    event = pd.Timestamp("2026-02-06")
    cleared = {a for a in ALL_ASSETS if event in zscore_anomalies(closes[a], 3.0).index}

    assert cleared == {"BTC", "ETH", "XRP"}
    assert return_zscore(closes["SOL"]).loc[event] == pytest.approx(2.09, abs=0.01)
    assert return_zscore(closes["BNB"]).loc[event] == pytest.approx(2.38, abs=0.01)


def test_btc_did_not_clear_the_threshold_on_2025_10_10(closes):
    """4 of 5 assets moved >3 sigma; BTC at -2.70 did not, and is not listed."""
    event = pd.Timestamp("2025-10-10")
    cleared = {a for a in ALL_ASSETS if event in zscore_anomalies(closes[a], 3.0).index}

    assert cleared == {"ETH", "SOL", "BNB", "XRP"}
    assert return_zscore(closes["BTC"]).loc[event] == pytest.approx(-2.70, abs=0.01)


def test_anomaly_output_is_a_bounded_list_of_dates(closes):
    anomalies = zscore_anomalies(closes["BTC"], 3.0)

    assert isinstance(anomalies.index, pd.DatetimeIndex)
    assert list(anomalies.columns) == ["zscore", "simple_return", "close"]
    assert (anomalies["zscore"].abs() > 3.0).all()


# --------------------------------------------------------------------------
# golden values: thresholds
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,expected_min30",
    [("BTC", 73460.78), ("ETH", 2007.01), ("SOL", 82.04), ("BNB", 617.27), ("XRP", 1.3076)],
)
def test_recent_30d_minimum_close_matches_report(frames, asset, expected_min30):
    df = frames[asset]
    extremes = recent_extremes(df["close"], df["high"], df["low"])

    assert extremes[30]["min_close"] == pytest.approx(expected_min30)


def test_90d_and_365d_bands_match_report(frames):
    btc = frames["BTC"]
    extremes = recent_extremes(btc["close"], btc["high"], btc["low"])

    assert extremes[90]["min_close"] == pytest.approx(65971.20)
    assert extremes[90]["max_close"] == pytest.approx(82210.07)
    assert extremes[365]["min_close"] == pytest.approx(62909.86)
    assert extremes[365]["max_close"] == pytest.approx(124658.54)


def test_recent_extremes_skips_windows_longer_than_history():
    short = pd.Series([1.0, 2.0, 3.0])

    assert recent_extremes(short, short, short) == {}


# --------------------------------------------------------------------------
# volatility compression
# --------------------------------------------------------------------------

def test_compression_detects_the_state_the_regime_labels_cannot_express(closes):
    """Four assets sit at the floor of their own volatility range simultaneously.

    This is the condition the report flags as unrepresentable: the existing
    labels have a name for the top of the volatility range and none for the
    bottom, so these read as "range bound" or "mixed".
    """
    compressed = {a for a in ALL_ASSETS if volatility_compression(closes[a]).is_compressed}

    assert compressed == {"BTC", "ETH", "SOL", "XRP"}


def test_bnb_is_not_compressed_and_says_why(closes):
    state = volatility_compression(closes["BNB"])

    assert state.status == "not_compressed"
    assert state.volatility_percentile == pytest.approx(0.371, abs=0.005)
    assert state.days_in_compression == 0
    assert "above the" in state.reason


def test_compression_result_carries_its_own_sample_size(closes):
    """The percentile must not travel without the history backing it."""
    state = volatility_compression(closes["XRP"])

    assert state.history_bars == 1826
    assert state.history_years == pytest.approx(5.0, abs=0.01)
    assert "1826 bars" in state.reason
    assert str(state.history_bars) in state.reason


def test_compression_reports_unavailable_rather_than_ranking_thin_history(closes):
    """Below the history floor the answer is 'unavailable', never a percentile."""
    state = volatility_compression(closes["BTC"].iloc[:100], min_history_bars=252)

    assert state.status == "unavailable"
    assert state.volatility_percentile is None
    assert not state.is_compressed
    assert "insufficient history" in state.reason


def test_compression_requires_persistence_not_a_single_quiet_day():
    """One low-volatility bar must not toggle the state."""
    rng = np.random.default_rng(0)
    noisy = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.05, 400))))
    calm_tail = pd.Series(
        noisy.iloc[-1] * np.exp(np.cumsum(rng.normal(0, 0.0001, 3))), index=range(400, 403)
    )
    series = pd.concat([noisy, calm_tail])

    state = volatility_compression(series, min_run=5, min_history_bars=252)

    assert state.status == "not_compressed"
    assert 0 < state.days_in_compression < 5
    assert "persistence" in state.reason


def test_compression_can_require_a_second_channel_to_agree(closes):
    """With a disagreeing secondary channel, a low reading is not enough."""
    disagreeing = pd.Series([0.9] * len(closes["BTC"]), index=closes["BTC"].index)

    state = volatility_compression(closes["BTC"], secondary=disagreeing)

    assert state.status == "not_compressed"
    assert "does not confirm" in state.reason


def test_compression_never_produces_probability_language(closes):
    """The detector describes the present; it must not imply what follows."""
    forbidden = ("likely", "probability", "chance", "expect", "will ", "rare", "forecast")

    for asset in ALL_ASSETS:
        reason = volatility_compression(closes[asset]).reason.lower()
        assert not any(word in reason for word in forbidden)
