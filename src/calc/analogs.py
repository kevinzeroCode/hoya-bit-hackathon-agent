"""Conditional base rates over an asset's own history.

Answers a bounded, retrospective question: *when this asset has been in a
similar state before, what followed?* It does not forecast, and the design
works hard to stop its output being read as a forecast.

Three constraints shape everything here:

1. **Overlapping windows are not independent samples.** A 30-day rolling
   condition evaluated daily produces ~330 observations that contain far
   fewer genuinely distinct episodes. Both counts are reported, always.
2. **No probabilities.** Results are ordinal (``strong|moderate|weak``) plus
   raw counts. A hit rate of 77% over ~16 episodes does not support "77%
   chance", and formatting it as a percentage invites exactly that reading.
3. **The condition must not be defined using future data.** Deciding what
   counts as "low volatility" from the whole sample leaks the future into
   every historical evaluation. ``mode="expanding"`` is the default;
   ``mode="full_sample"`` is available for reproducing retrospective figures
   and self-reports the contamination in its limitations.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import realized_volatility

STRONG_DEVIATION = 0.20
"""Distance from a 50/50 split required before an outcome is called strong."""

MODERATE_DEVIATION = 0.10

MIN_EPISODES = 8
"""Below this many distinct episodes, no strength level is claimed at all."""

_BOUNDARY_TOLERANCE = 1e-9
"""Guards the threshold comparisons against float representation error.

``abs(0.70 - 0.5)`` evaluates to 0.19999999999999998, which would place a rate
sitting exactly on the documented boundary in the tier below the one the
constants describe. Real data lands on these boundaries.
"""


@dataclass(frozen=True)
class EpisodeCount:
    """Three views of "how much evidence is behind this", none optional.

    ``observations`` flatters the sample; ``distinct_episodes`` and
    ``effective_n`` deflate it. Reporting only the first is how a base rate
    ends up sounding better supported than it is.
    """

    observations: int
    distinct_episodes: int
    effective_n: float

    @property
    def is_sufficient(self) -> bool:
        return self.distinct_episodes >= MIN_EPISODES


@dataclass(frozen=True)
class BaseRate:
    """One conditional outcome, expressed ordinally with its raw counts."""

    outcome: str
    hits: int
    total: int
    rate: float
    strength: str  # strong | moderate | weak | unavailable
    median_ratio: float | None = None

    def describe(self) -> str:
        """Counts and an ordinal level -- deliberately not a percentage claim."""
        if self.strength == "unavailable":
            return f"{self.outcome}: 樣本不足，不提供強度判定（{self.hits}/{self.total}）"
        return f"{self.outcome}: {self.hits}/{self.total} 次（強度 {self.strength}）"


@dataclass(frozen=True)
class AnalogStudy:
    """A complete conditional study, including why it should be doubted."""

    condition: str
    mode: str
    horizon: int
    episodes: EpisodeCount
    rates: dict[str, BaseRate]
    status: str  # ok | unavailable
    limitations: tuple[str, ...]


def count_episodes(condition: pd.Series, horizon: int) -> EpisodeCount:
    """Count observations, consecutive-run episodes, and horizon-adjusted n.

    Consecutive qualifying days are one episode: a 40-day stretch of quiet
    market is a single thing that happened, not 40 independent confirmations.
    ``effective_n`` is the cruder ``observations / horizon`` deflation, kept
    because it is the more conservative of the two.
    """
    mask = condition.fillna(False).astype(bool)
    observations = int(mask.sum())
    if observations == 0:
        return EpisodeCount(0, 0, 0.0)

    run_ids = (mask != mask.shift()).cumsum()[mask]
    return EpisodeCount(
        observations=observations,
        distinct_episodes=int(run_ids.nunique()),
        effective_n=observations / horizon,
    )


def strength_level(rate: float, episodes: EpisodeCount) -> str:
    """Map a hit rate to an ordinal level, gated on episode count.

    Strength is distance from a coin flip, not the raw rate: 20% and 80% are
    equally informative, 50% is not informative at all. Too few episodes and
    no level is claimed regardless of how lopsided the rate looks.
    """
    if not episodes.is_sufficient:
        return "unavailable"

    deviation = abs(rate - 0.5)
    if deviation >= STRONG_DEVIATION - _BOUNDARY_TOLERANCE:
        return "strong"
    if deviation >= MODERATE_DEVIATION - _BOUNDARY_TOLERANCE:
        return "moderate"
    return "weak"


def conditional_base_rate(
    outcome: pd.Series,
    episodes: EpisodeCount,
    label: str,
    median_ratio: float | None = None,
) -> BaseRate:
    """Summarise a boolean outcome series into an ordinal base rate."""
    clean = outcome.dropna().astype(bool)
    total = len(clean)
    if total == 0:
        return BaseRate(label, 0, 0, float("nan"), "unavailable", None)

    hits = int(clean.sum())
    rate = hits / total
    return BaseRate(label, hits, total, rate, strength_level(rate, episodes), median_ratio)


def low_volatility_condition(
    close: pd.Series,
    window: int = 30,
    quintile: float = 0.20,
    mode: str = "expanding",
    min_history: int = 252,
) -> pd.Series:
    """Boolean series: is realised volatility in the asset's own bottom quintile?

    ``expanding`` ranks each bar only against bars up to that point, so the
    definition of "low" is one that was actually available at the time.
    ``full_sample`` ranks against the entire series, which is measurably more
    permissive and produces stronger-looking results for the wrong reason.
    """
    if mode not in {"expanding", "full_sample"}:
        raise ValueError(f"unknown mode: {mode!r}")

    vol = realized_volatility(close, window)
    if mode == "full_sample":
        return vol <= vol.quantile(quintile)

    percentile = vol.expanding(min_periods=min_history).rank(pct=True)
    return percentile <= quintile


def volatility_compression_study(
    close: pd.Series,
    window: int = 30,
    horizon: int = 30,
    quintile: float = 0.20,
    mode: str = "expanding",
    min_history: int = 252,
) -> AnalogStudy:
    """What has followed this asset's quietest periods, in its own history.

    Two outcomes are measured at ``horizon`` bars forward: whether volatility
    was higher, and whether price was higher. They typically behave very
    differently -- magnitude carries a signal where direction does not -- and
    separating them prevents the stronger one lending credibility to the
    weaker one.
    """
    condition = low_volatility_condition(close, window, quintile, mode, min_history)
    volatility = realized_volatility(close, window)
    forward_volatility = volatility.shift(-horizon)
    forward_return = close.shift(-horizon) / close - 1.0

    valid = (
        condition.fillna(False)
        & volatility.notna()
        & forward_volatility.notna()
        & forward_return.notna()
    )
    episodes = count_episodes(valid, horizon)

    limitations: list[str] = [
        (
            f"重疊視窗：{episodes.observations} 個觀測僅對應約 {episodes.distinct_episodes} 段"
            f"獨立區間（另以視窗長度折算約 {episodes.effective_n:.0f} 個），"
            f"不得視為獨立樣本，亦不得表述為機率。"
        ),
    ]
    if mode == "full_sample":
        limitations.append(
            "條件門檻以全樣本分位數界定，使用了當時尚不可得的資料（前視偏誤）；"
            "此模式僅供回溯對照，不應作為當期判斷依據。"
        )
    else:
        limitations.append(
            f"條件門檻以擴張視窗界定（最少 {min_history} 根 K 線），"
            "僅使用各時點當下已可得的歷史。"
        )

    if episodes.observations == 0 or not episodes.is_sufficient:
        limitations.append(
            f"獨立區間數 {episodes.distinct_episodes} 低於門檻 {MIN_EPISODES}，不輸出強度判定。"
        )
        return AnalogStudy(
            condition=f"realized_vol_{window}d 位於自身歷史最低 {quintile:.0%}",
            mode=mode,
            horizon=horizon,
            episodes=episodes,
            rates={},
            status="unavailable",
            limitations=tuple(limitations),
        )

    expansion_ratio = (forward_volatility[valid] / volatility[valid]).replace(
        [np.inf, -np.inf], np.nan
    )
    rates = {
        "volatility_expansion": conditional_base_rate(
            forward_volatility[valid] > volatility[valid],
            episodes,
            f"{horizon} 日後波動較高",
            median_ratio=float(expansion_ratio.median()) if expansion_ratio.notna().any() else None,
        ),
        "direction_up": conditional_base_rate(
            forward_return[valid] > 0,
            episodes,
            f"{horizon} 日後價格較高",
        ),
    }

    return AnalogStudy(
        condition=f"realized_vol_{window}d 位於自身歷史最低 {quintile:.0%}",
        mode=mode,
        horizon=horizon,
        episodes=episodes,
        rates=rates,
        status="ok",
        limitations=tuple(limitations),
    )
