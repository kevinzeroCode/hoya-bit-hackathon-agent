"""Single-asset price calculations over daily OHLCV.

Conventions used throughout this package:

* Inputs are ``pandas.Series`` aligned to a ``DatetimeIndex`` (one bar per
  UTC day). Functions that report dates read them from the index.
* Every ratio/percentage is returned as a **fraction** (``-0.074`` means
  -7.4%), and every percentile as a fraction in ``0..1``.
* Nothing here predicts. Each function states a property of the history it
  was given, and returns ``NaN``/``None`` rather than guessing when there
  are not enough bars to support the statement.

Methodology choices are pinned to what reproduces the worked numbers in
``docs/price-data-analysis-outputs.html`` (verified against the real CSVs):
volatility is annualised by ``sqrt(365)``, ATR uses a simple rolling mean
rather than Wilder smoothing, and skew/kurtosis are taken over log returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .percentile import expanding_percentile

TRADING_DAYS_PER_YEAR = 365
"""Crypto trades every calendar day, so annualisation uses 365, not 252."""


# --------------------------------------------------------------------------
# returns
# --------------------------------------------------------------------------

def simple_returns(close: pd.Series, horizon: int = 1) -> pd.Series:
    """Simple return over ``horizon`` bars: ``close_t / close_{t-h} - 1``."""
    return close / close.shift(horizon) - 1.0


def log_returns(close: pd.Series, horizon: int = 1) -> pd.Series:
    """Log return over ``horizon`` bars. Preferred for anything additive."""
    return np.log(close / close.shift(horizon))


def multi_horizon_returns(
    close: pd.Series,
    horizons: tuple[int, ...] = (1, 7, 30, 90, 365),
) -> dict[int, float]:
    """Latest simple return at several horizons at once.

    Reporting one horizon in isolation is the most common way price data
    misleads; this returns the whole set so a caller cannot cherry-pick by
    accident. Horizons with insufficient history yield ``nan``.
    """
    out: dict[int, float] = {}
    for h in horizons:
        out[h] = float(close.iloc[-1] / close.iloc[-1 - h] - 1.0) if len(close) > h else float("nan")
    return out


# --------------------------------------------------------------------------
# volatility / risk
# --------------------------------------------------------------------------

def realized_volatility(
    close: pd.Series,
    window: int = 30,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.Series:
    """Annualised rolling standard deviation of log returns."""
    return log_returns(close).rolling(window).std() * np.sqrt(periods_per_year)


def volatility_percentile(
    close: pd.Series,
    window: int = 30,
    min_periods: int | None = None,
) -> pd.Series:
    """Realised volatility ranked against the asset's *own* prior history.

    Absolute volatility is not comparable across assets; its rank within the
    asset's own history is. Uses an expanding window so no future bar can
    influence a past ranking.
    """
    vol = realized_volatility(close, window)
    return expanding_percentile(vol, min_periods=min_periods or window + 1)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Wilder's true range: greatest of today's span and the two gap spans."""
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average true range, simple rolling mean (not Wilder smoothing)."""
    return true_range(high, low, close).rolling(window).mean()


def drawdown_series(close: pd.Series) -> pd.Series:
    """Fractional drawdown from the running peak close, at every bar."""
    running_peak = close.cummax()
    return close / running_peak - 1.0


def max_drawdown(close: pd.Series) -> float:
    """Worst peak-to-trough close-to-close drawdown over the whole series."""
    return float(drawdown_series(close).min())


def return_distribution(close: pd.Series) -> tuple[float, float]:
    """``(skew, excess_kurtosis)`` of log returns over the full series.

    Distinguishes tail structure that volatility alone hides: two assets can
    share a volatility number and have entirely different crash profiles.
    """
    lr = log_returns(close).dropna()
    return float(lr.skew()), float(lr.kurt())


# --------------------------------------------------------------------------
# position within own history
# --------------------------------------------------------------------------

def moving_average(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    return close.rolling(window).mean()


def distance_from_ma(close: pd.Series, window: int) -> pd.Series:
    """Fractional distance of close above/below its own moving average."""
    ma = moving_average(close, window)
    return close / ma - 1.0


def rolling_range(high: pd.Series, low: pd.Series, window: int = 252) -> tuple[pd.Series, pd.Series]:
    """``(rolling_high, rolling_low)`` over ``window`` bars."""
    return high.rolling(window).max(), low.rolling(window).min()


def range_position(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    window: int = 252,
) -> pd.Series:
    """Where close sits inside its rolling high/low band, ``0..1``.

    ``0`` is the bottom of the band, ``1`` the top. Returns ``NaN`` for a
    degenerate (zero-width) band rather than dividing by zero.
    """
    hi, lo = rolling_range(high, low, window)
    span = hi - lo
    return (close - lo).where(span > 0) / span.where(span > 0)


@dataclass(frozen=True)
class AllTimeHighStats:
    """All-time-high context.

    Two drawdowns are reported deliberately. The intraday high and the
    highest close are different reference points and differ materially
    (for BTC in the shipped dataset: -41.6% vs -40.9%). Naming both prevents
    quoting one while labelling it the other.
    """

    ath_close: float
    ath_close_date: pd.Timestamp | None
    ath_high: float
    days_since_ath_close: int | None
    drawdown_from_ath_close: float
    drawdown_from_ath_high: float


def all_time_high_stats(close: pd.Series, high: pd.Series) -> AllTimeHighStats:
    """ATH levels, the date of the highest close, and both drawdown measures.

    "All-time" means *within the supplied history* -- with a five-year file
    that is not the asset's true all-time high. Callers reporting this should
    carry the window length alongside it.
    """
    ath_close = float(close.max())
    ath_high = float(high.max())
    idx = close.idxmax()
    last_index = close.index[-1]

    date = idx if isinstance(idx, pd.Timestamp) else None
    days = (last_index - idx).days if isinstance(last_index, pd.Timestamp) and isinstance(idx, pd.Timestamp) else None

    return AllTimeHighStats(
        ath_close=ath_close,
        ath_close_date=date,
        ath_high=ath_high,
        days_since_ath_close=days,
        drawdown_from_ath_close=float(close.iloc[-1]) / ath_close - 1.0,
        drawdown_from_ath_high=float(close.iloc[-1]) / ath_high - 1.0,
    )


# --------------------------------------------------------------------------
# participation (volume) -- same-asset comparisons only
# --------------------------------------------------------------------------

def volume_mean_ratio(volume: pd.Series, short: int = 30, long: int = 365) -> pd.Series:
    """Short-window mean volume divided by long-window mean volume.

    A ratio against the asset's own baseline, so it is meaningful for a
    single asset. Base-unit volume must never be compared *across* assets:
    one BTC and one XRP are not comparable units.
    """
    return volume.rolling(short).mean() / volume.rolling(long).mean()


def volume_mean_percentile(volume: pd.Series, window: int = 30) -> pd.Series:
    """Rank of the rolling mean volume within the asset's own prior history."""
    return expanding_percentile(volume.rolling(window).mean(), min_periods=window + 1)


@dataclass(frozen=True)
class PriceVolumeCross:
    """Whether a price move over a window came with participation."""

    price_change: float
    volume_change: float
    direction: str  # up_on_rising_volume | up_on_falling_volume | down_on_rising_volume | down_on_falling_volume


def price_volume_cross(close: pd.Series, volume: pd.Series, window: int = 30) -> PriceVolumeCross:
    """Compare the latest ``window`` bars against the ``window`` before it.

    Price direction crossed with volume direction. A rise on shrinking volume
    and a rise on expanding volume are different situations; this states which
    occurred without claiming what follows from it.
    """
    price_change = float(close.iloc[-1] / close.iloc[-1 - window] - 1.0)
    recent_volume = float(volume.iloc[-window:].mean())
    prior_volume = float(volume.iloc[-2 * window : -window].mean())
    volume_change = recent_volume / prior_volume - 1.0

    price_word = "up" if price_change >= 0 else "down"
    volume_word = "rising" if volume_change >= 0 else "falling"
    return PriceVolumeCross(price_change, volume_change, f"{price_word}_on_{volume_word}_volume")


# --------------------------------------------------------------------------
# event timestamps
# --------------------------------------------------------------------------

def return_zscore(close: pd.Series) -> pd.Series:
    """Log returns standardised by their own full-sample mean and stdev."""
    lr = log_returns(close)
    return (lr - lr.mean()) / lr.std()


def zscore_anomalies(close: pd.Series, threshold: float = 3.0) -> pd.DataFrame:
    """Days whose move exceeded ``threshold`` standard deviations.

    Price data cannot say *what* happened, only *when* something did. The
    output is a bounded list of dates to investigate elsewhere -- it turns an
    open-ended question into a finite one, and asserts no cause.
    """
    z = return_zscore(close)
    simple = simple_returns(close)
    mask = z.abs() > threshold
    return pd.DataFrame(
        {"zscore": z[mask], "simple_return": simple[mask], "close": close[mask]}
    )


# --------------------------------------------------------------------------
# volatility compression
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CompressionState:
    """Result of the volatility-compression check.

    ``history_bars`` and ``history_years`` are part of the result, not
    optional metadata: "0th percentile of volatility" means something very
    different over five years than over twenty, and the caller should not be
    able to report the percentile without the sample size attached.
    """

    status: str  # "compressed" | "not_compressed" | "unavailable"
    volatility_percentile: float | None
    days_in_compression: int
    history_bars: int
    history_years: float
    reason: str

    @property
    def is_compressed(self) -> bool:
        return self.status == "compressed"


def volatility_compression(
    close: pd.Series,
    window: int = 30,
    low_threshold: float = 0.10,
    min_run: int = 5,
    min_history_bars: int = 252,
    secondary: pd.Series | None = None,
) -> CompressionState:
    """Detect a sustained low-volatility state relative to the asset's own past.

    Mirrors the high end (a "high volatility" label typically means the top
    decile) at the low end, which otherwise has no name: an asset can sit at
    the bottom of its own volatility range and be describable only as
    "range bound", discarding the most distinctive fact available about it.

    Guards against overclaiming:

    * below ``min_history_bars`` the result is ``unavailable`` rather than a
      percentile computed against a window too thin to support it;
    * ``min_run`` consecutive qualifying bars are required, so a single quiet
      day cannot toggle the state;
    * ``secondary`` optionally requires a second, independent contraction
      channel (an ATR percentile, say) to agree, so the call is not one noisy
      series agreeing with itself;
    * the sample size travels with the answer, and no probability or
      rarity language is produced.

    This describes the present state only. It says nothing about what follows.
    """
    history_bars = int(close.notna().sum())
    history_years = history_bars / TRADING_DAYS_PER_YEAR

    if history_bars < min_history_bars:
        return CompressionState(
            status="unavailable",
            volatility_percentile=None,
            days_in_compression=0,
            history_bars=history_bars,
            history_years=history_years,
            reason=(
                f"insufficient history: {history_bars} bars < required {min_history_bars}"
            ),
        )

    pct = volatility_percentile(close, window=window).dropna()
    if pct.empty:
        return CompressionState(
            status="unavailable",
            volatility_percentile=None,
            days_in_compression=0,
            history_bars=history_bars,
            history_years=history_years,
            reason="volatility percentile could not be computed",
        )

    latest = float(pct.iloc[-1])

    run = 0
    for value in reversed(pct.tolist()):
        if value <= low_threshold:
            run += 1
        else:
            break

    if latest > low_threshold:
        return CompressionState(
            status="not_compressed",
            volatility_percentile=latest,
            days_in_compression=0,
            history_bars=history_bars,
            history_years=history_years,
            reason=(
                f"volatility at {latest:.1%} of own {history_years:.1f}y history, "
                f"above the {low_threshold:.0%} threshold"
            ),
        )

    if run < min_run:
        return CompressionState(
            status="not_compressed",
            volatility_percentile=latest,
            days_in_compression=run,
            history_bars=history_bars,
            history_years=history_years,
            reason=(
                f"volatility low ({latest:.1%}) for {run} bar(s), "
                f"short of the {min_run}-bar persistence requirement"
            ),
        )

    if secondary is not None:
        secondary_clean = secondary.dropna()
        if secondary_clean.empty:
            return CompressionState(
                status="unavailable",
                volatility_percentile=latest,
                days_in_compression=run,
                history_bars=history_bars,
                history_years=history_years,
                reason="secondary confirmation series unavailable",
            )
        secondary_latest = float(secondary_clean.iloc[-1])
        if secondary_latest > low_threshold:
            return CompressionState(
                status="not_compressed",
                volatility_percentile=latest,
                days_in_compression=run,
                history_bars=history_bars,
                history_years=history_years,
                reason=(
                    f"volatility low ({latest:.1%}) but secondary channel at "
                    f"{secondary_latest:.1%} does not confirm"
                ),
            )

    return CompressionState(
        status="compressed",
        volatility_percentile=latest,
        days_in_compression=run,
        history_bars=history_bars,
        history_years=history_years,
        reason=(
            f"volatility at {latest:.1%} of own history for {run} consecutive bars; "
            f"ranked against {history_bars} bars (~{history_years:.1f}y)"
        ),
    )


# --------------------------------------------------------------------------
# thresholds
# --------------------------------------------------------------------------

def recent_extremes(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    windows: tuple[int, ...] = (30, 90, 365),
) -> dict[int, dict[str, float]]:
    """Recent extreme closes and high/low band edges per window.

    These are the concrete numbers a falsifiable condition is built from
    ("below X", "outside the Y-day band"), computed rather than invented.
    """
    out: dict[int, dict[str, float]] = {}
    for w in windows:
        if len(close) < w:
            continue
        out[w] = {
            "min_close": float(close.iloc[-w:].min()),
            "max_close": float(close.iloc[-w:].max()),
            "lowest_low": float(low.iloc[-w:].min()),
            "highest_high": float(high.iloc[-w:].max()),
        }
    return out
