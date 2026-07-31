"""Deterministic price calculations over daily OHLCV data.

Pure functions over pandas Series/DataFrames. No I/O, no network, no model
calls: given the same bars, these always return the same numbers.

Layout:

* ``percentile``   -- the look-ahead-safe ranking primitive everything reuses
* ``indicators``   -- single-asset calculations (returns, risk, position,
                      participation, event timestamps, thresholds)
* ``cross_asset``  -- two-asset relationships (correlation, beta, relative
                      strength, dispersion)
* ``data_quality`` -- OHLCV integrity validation

Series are expected to carry a ``DatetimeIndex`` of UTC days. Ratios and
percentiles are returned as fractions, never pre-multiplied percentages.
"""

from .cross_asset import (
    align,
    dispersion,
    relative_return,
    relative_strength_percentile,
    relative_strength_ratio,
    rolling_beta,
    rolling_correlation,
)
from .data_quality import IntegrityReport, check_ohlc_integrity
from .indicators import (
    AllTimeHighStats,
    CompressionState,
    PriceVolumeCross,
    all_time_high_stats,
    atr,
    distance_from_ma,
    drawdown_series,
    log_returns,
    max_drawdown,
    moving_average,
    multi_horizon_returns,
    price_volume_cross,
    range_position,
    realized_volatility,
    recent_extremes,
    return_distribution,
    return_zscore,
    rolling_range,
    simple_returns,
    true_range,
    volatility_compression,
    volatility_percentile,
    volume_mean_percentile,
    volume_mean_ratio,
    zscore_anomalies,
)
from .percentile import expanding_percentile

__all__ = [
    "AllTimeHighStats",
    "CompressionState",
    "IntegrityReport",
    "PriceVolumeCross",
    "align",
    "all_time_high_stats",
    "atr",
    "check_ohlc_integrity",
    "dispersion",
    "distance_from_ma",
    "drawdown_series",
    "expanding_percentile",
    "log_returns",
    "max_drawdown",
    "moving_average",
    "multi_horizon_returns",
    "price_volume_cross",
    "range_position",
    "realized_volatility",
    "recent_extremes",
    "relative_return",
    "relative_strength_percentile",
    "relative_strength_ratio",
    "return_distribution",
    "return_zscore",
    "rolling_beta",
    "rolling_correlation",
    "rolling_range",
    "simple_returns",
    "true_range",
    "volatility_compression",
    "volatility_percentile",
    "volume_mean_percentile",
    "volume_mean_ratio",
    "zscore_anomalies",
]
