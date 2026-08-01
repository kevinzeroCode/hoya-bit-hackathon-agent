"""Deterministic market indicators for the HOYA market-analysis agent.

Pure functions over a sequence of daily closes/volumes. No LLM, no network,
no state. All windows are explicit and every result is reproducible from the
inputs, so each value can back a high-reliability EvidenceItem.

Conventions (must match the organizer EDA so golden values line up):
- A "window" of N looks back N steps; return needs N+1 points.
- Daily return r_i = close_i / close_{i-1} - 1.
- Realized volatility is the sample standard deviation (ddof=1) of the last
  `window` daily returns.
- Max drawdown is the most negative (close / running-max - 1) over the window.
Callers must pass only completed UTC daily bars at or before analysis_as_of and
must not forward-fill missing bars.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean, stdev


def _check(closes: Sequence[float], needed: int) -> None:
    if len(closes) < needed:
        raise ValueError(f"need at least {needed} points, got {len(closes)}")


def daily_returns(closes: Sequence[float]) -> list[float]:
    """Simple daily returns; len(result) == len(closes) - 1."""
    _check(closes, 2)
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def simple_return(closes: Sequence[float], window: int) -> float:
    """close[T] / close[T-window] - 1."""
    if window <= 0:
        raise ValueError("window must be positive")
    _check(closes, window + 1)
    return closes[-1] / closes[-1 - window] - 1.0


def relative_change(a: float, b: float) -> float:
    """a relative to b: a / b - 1. Used for like-for-like comparable scales."""
    if b == 0:
        raise ValueError("base value must be non-zero")
    return a / b - 1.0


def realized_volatility(closes: Sequence[float], window: int) -> float:
    """Sample std (ddof=1) of the last `window` daily returns (uses window+1 closes)."""
    if window < 2:
        raise ValueError("window must be >= 2")
    _check(closes, window + 1)
    return stdev(daily_returns(closes[-(window + 1):]))


def max_drawdown(closes: Sequence[float], window: int) -> float:
    """Most negative close / running-max - 1 over the last `window` closes.

    Returns 0.0 for a monotonically non-decreasing window.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    _check(closes, window)
    peak = closes[-window]
    worst = 0.0
    for c in closes[-window:]:
        if c > peak:
            peak = c
        drawdown = c / peak - 1.0
        if drawdown < worst:
            worst = drawdown
    return worst


def rolling_volume_zscore(volumes: Sequence[float], window: int) -> float:
    """z-score of the latest volume vs the last `window` values of its OWN history.

    Cross-asset volume comparison is forbidden; this stays within one asset.
    """
    if window < 2:
        raise ValueError("window must be >= 2")
    _check(volumes, window)
    win = volumes[-window:]
    spread = stdev(win)
    if spread == 0:
        raise ValueError("zero volume variance; z-score undefined")
    return (win[-1] - fmean(win)) / spread
