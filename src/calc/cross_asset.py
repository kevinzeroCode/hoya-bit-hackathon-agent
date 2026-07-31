"""Two-asset calculations: is this asset moving with the market or on its own?

The practical use is triage. An asset moving in lockstep with its benchmark
is unlikely to be explained by anything specific to itself, while one that
has decoupled probably is -- which is exactly the question worth spending
further investigation on.

Only ``close`` is used here. Volume is deliberately excluded: base-unit
volume is not comparable across assets, and there is no correct way to put
two such series in one ratio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import log_returns


def align(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Restrict both series to the dates they share, in order.

    Assets list at different times, so an unaligned join silently compares
    mismatched days. Everything below aligns first.
    """
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").sort_index()
    return joined["a"], joined["b"]


def rolling_correlation(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    window: int = 90,
) -> pd.Series:
    """Rolling correlation of log returns against a benchmark.

    High correlation means the asset carries little information the benchmark
    does not already carry. It says nothing about causation in either
    direction.
    """
    a, b = align(asset_close, benchmark_close)
    return log_returns(a).rolling(window).corr(log_returns(b))


def rolling_beta(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    window: int = 90,
) -> pd.Series:
    """Rolling beta: covariance with the benchmark over benchmark variance.

    Amplitude relative to the benchmark, where correlation gives only
    direction agreement. Beta above 1 with low correlation is a real and
    easily misread combination, so both are reported separately.
    """
    a, b = align(asset_close, benchmark_close)
    asset_returns, benchmark_returns = log_returns(a), log_returns(b)
    covariance = asset_returns.rolling(window).cov(benchmark_returns)
    variance = benchmark_returns.rolling(window).var()
    return covariance / variance.where(variance > 0)


def relative_strength_ratio(asset_close: pd.Series, benchmark_close: pd.Series) -> pd.Series:
    """Price ratio of asset to benchmark.

    The level is arbitrary; only its movement and its rank within its own
    history carry meaning.
    """
    a, b = align(asset_close, benchmark_close)
    return a / b


def relative_strength_percentile(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    window: int = 365,
) -> float:
    """Rank of the latest asset/benchmark ratio within its trailing window.

    ``NaN`` when the window is not fully covered, rather than a rank computed
    against a partial window.
    """
    ratio = relative_strength_ratio(asset_close, benchmark_close).dropna()
    if len(ratio) < window:
        return float("nan")
    return float(ratio.iloc[-window:].rank(pct=True).iloc[-1])


def relative_return(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    horizon: int = 30,
) -> float:
    """How much the asset out- or under-performed the benchmark over ``horizon``.

    Computed as a ratio of growth factors, so it composes correctly rather
    than subtracting two percentages.
    """
    a, b = align(asset_close, benchmark_close)
    if len(a) <= horizon:
        return float("nan")
    asset_growth = a.iloc[-1] / a.iloc[-1 - horizon]
    benchmark_growth = b.iloc[-1] / b.iloc[-1 - horizon]
    return float(asset_growth / benchmark_growth - 1.0)


def dispersion(closes: dict[str, pd.Series], horizon: int = 30) -> float:
    """Spread of returns across a group of assets over ``horizon``.

    Near-zero dispersion means the group is moving as one block, so a
    single-asset explanation is unlikely to be the operative one.
    """
    returns = []
    for series in closes.values():
        clean = series.dropna()
        if len(clean) > horizon:
            returns.append(float(clean.iloc[-1] / clean.iloc[-1 - horizon] - 1.0))
    if len(returns) < 2:
        return float("nan")
    return float(np.std(returns, ddof=1))
