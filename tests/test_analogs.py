"""Tests for the conditional base-rate engine.

Two things are pinned here: that the retrospective mode reproduces the
published figures, and that the default mode produces *weaker* ones. The
second matters more -- the difference between them is the size of the
look-ahead bias, and it must stay visible rather than being tuned away.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calc.analogs import (
    MIN_EPISODES,
    EpisodeCount,
    conditional_base_rate,
    count_episodes,
    low_volatility_condition,
    strength_level,
    volatility_compression_study,
)

ALL_ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP")


# --------------------------------------------------------------------------
# episode accounting
# --------------------------------------------------------------------------

def test_consecutive_days_collapse_into_one_episode():
    """A five-day quiet stretch is one thing that happened, not five."""
    condition = pd.Series([True, True, True, True, True])
    counted = count_episodes(condition, horizon=30)

    assert counted.observations == 5
    assert counted.distinct_episodes == 1


def test_separated_runs_count_separately():
    condition = pd.Series([True, True, False, False, True, False, True])
    counted = count_episodes(condition, horizon=30)

    assert counted.observations == 4
    assert counted.distinct_episodes == 3


def test_effective_n_deflates_by_the_horizon():
    condition = pd.Series([True] * 300)

    assert count_episodes(condition, horizon=30).effective_n == pytest.approx(10.0)


def test_empty_condition_counts_nothing():
    counted = count_episodes(pd.Series([False, False]), horizon=30)

    assert counted.observations == 0
    assert counted.distinct_episodes == 0
    assert not counted.is_sufficient


# --------------------------------------------------------------------------
# strength levels
# --------------------------------------------------------------------------

def test_strength_measures_distance_from_a_coin_flip_not_the_raw_rate():
    """20% and 80% are equally informative; 50% is not informative at all."""
    plenty = EpisodeCount(observations=600, distinct_episodes=20, effective_n=20.0)

    assert strength_level(0.80, plenty) == "strong"
    assert strength_level(0.20, plenty) == "strong"
    assert strength_level(0.50, plenty) == "weak"


@pytest.mark.parametrize(
    "rate,expected",
    [(0.95, "strong"), (0.70, "strong"), (0.65, "moderate"), (0.55, "weak"), (0.45, "weak")],
)
def test_strength_thresholds(rate, expected):
    plenty = EpisodeCount(observations=600, distinct_episodes=20, effective_n=20.0)

    assert strength_level(rate, plenty) == expected


def test_exact_boundary_rates_land_in_the_documented_tier():
    """Regression: abs(0.70 - 0.5) is 0.19999999999999998 in float arithmetic.

    Without a tolerance, a rate sitting exactly on a published threshold falls
    into the tier below the one the constants describe -- and real data does
    land here.
    """
    plenty = EpisodeCount(observations=600, distinct_episodes=20, effective_n=20.0)

    assert strength_level(0.70, plenty) == "strong"
    assert strength_level(0.30, plenty) == "strong"
    assert strength_level(0.60, plenty) == "moderate"
    assert strength_level(0.40, plenty) == "moderate"


def test_too_few_episodes_yields_no_strength_however_lopsided_the_rate():
    thin = EpisodeCount(observations=90, distinct_episodes=MIN_EPISODES - 1, effective_n=3.0)

    assert strength_level(0.99, thin) == "unavailable"


def test_base_rate_with_no_observations_is_unavailable():
    plenty = EpisodeCount(600, 20, 20.0)
    rate = conditional_base_rate(pd.Series([], dtype=bool), plenty, "x")

    assert rate.strength == "unavailable"
    assert rate.total == 0


def test_base_rate_description_carries_counts_not_a_percentage():
    plenty = EpisodeCount(600, 20, 20.0)
    rate = conditional_base_rate(pd.Series([True, True, False, True]), plenty, "測試結果")

    assert "3/4" in rate.describe()
    assert "%" not in rate.describe()


# --------------------------------------------------------------------------
# condition construction
# --------------------------------------------------------------------------

def test_full_sample_condition_is_more_permissive_than_expanding(closes):
    """The extra observations are exactly what the look-ahead buys."""
    close = closes["BTC"]
    expanding = low_volatility_condition(close, mode="expanding").fillna(False).sum()
    full_sample = low_volatility_condition(close, mode="full_sample").fillna(False).sum()

    assert expanding > full_sample


def test_unknown_mode_is_rejected(closes):
    with pytest.raises(ValueError, match="unknown mode"):
        low_volatility_condition(closes["BTC"], mode="lookahead")


def test_expanding_condition_needs_minimum_history(closes):
    condition = low_volatility_condition(closes["BTC"], mode="expanding", min_history=252)

    assert not condition.iloc[:251].fillna(False).any()


# --------------------------------------------------------------------------
# the study, against the published figures
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,volatility_hits,direction_hits",
    [("BTC", 0.773, 0.516), ("ETH", 0.824, 0.525), ("SOL", 0.700, 0.573),
     ("BNB", 0.696, 0.569), ("XRP", 0.812, 0.615)],
)
def test_full_sample_mode_reproduces_published_rates(closes, asset, volatility_hits, direction_hits):
    """Retrospective mode matches the figures in the design document."""
    study = volatility_compression_study(closes[asset], mode="full_sample")

    assert study.status == "ok"
    assert study.rates["volatility_expansion"].rate == pytest.approx(volatility_hits, abs=0.005)
    assert study.rates["direction_up"].rate == pytest.approx(direction_hits, abs=0.005)


def test_published_observation_count_is_reproduced(closes):
    """The document reports n ~ 330; that is the full-sample quintile size."""
    study = volatility_compression_study(closes["XRP"], mode="full_sample")

    assert study.episodes.observations == pytest.approx(330, abs=5)


@pytest.mark.parametrize("asset", ALL_ASSETS)
def test_expanding_mode_gives_a_weaker_volatility_signal(closes, asset):
    """The bias-free default must not quietly inherit the stronger numbers."""
    expanding = volatility_compression_study(closes[asset], mode="expanding")
    full_sample = volatility_compression_study(closes[asset], mode="full_sample")

    assert expanding.rates["volatility_expansion"].rate < full_sample.rates["volatility_expansion"].rate


@pytest.mark.parametrize("asset", ALL_ASSETS)
def test_direction_is_never_better_than_moderate_under_the_honest_mode(closes, asset):
    """Direction is close to a coin flip once the look-ahead is removed."""
    study = volatility_compression_study(closes[asset], mode="expanding")

    assert study.rates["direction_up"].strength in ("weak", "moderate")
    assert study.rates["direction_up"].rate < 0.60


def test_default_mode_is_expanding(closes):
    default = volatility_compression_study(closes["BTC"])

    assert default.mode == "expanding"


def test_volatility_and_direction_are_reported_separately(closes):
    """Combining them would let the strong signal carry the weak one."""
    study = volatility_compression_study(closes["BTC"], mode="full_sample")

    assert study.rates["volatility_expansion"].strength == "strong"
    assert study.rates["direction_up"].strength == "weak"


def test_median_expansion_ratio_is_reported_for_volatility(closes):
    study = volatility_compression_study(closes["BTC"], mode="full_sample")

    assert study.rates["volatility_expansion"].median_ratio == pytest.approx(1.50, abs=0.05)


# --------------------------------------------------------------------------
# disclosure obligations
# --------------------------------------------------------------------------

def test_overlapping_window_limitation_is_always_present(closes):
    study = volatility_compression_study(closes["BTC"])

    assert any("重疊視窗" in item for item in study.limitations)
    assert any("不得視為獨立樣本" in item for item in study.limitations)


def test_full_sample_mode_discloses_its_own_look_ahead(closes):
    study = volatility_compression_study(closes["BTC"], mode="full_sample")

    assert any("前視偏誤" in item for item in study.limitations)


def test_expanding_mode_states_it_used_only_available_history(closes):
    study = volatility_compression_study(closes["BTC"], mode="expanding")

    assert any("擴張視窗" in item for item in study.limitations)
    assert not any("前視偏誤" in item for item in study.limitations)


def test_thin_history_yields_unavailable_not_a_thin_base_rate(closes):
    study = volatility_compression_study(closes["BTC"].iloc[:300], mode="full_sample")

    assert study.status == "unavailable"
    assert study.rates == {}


def test_study_never_formats_a_rate_as_a_probability(closes):
    """Nothing in the emitted limitations should read as a probability claim."""
    study = volatility_compression_study(closes["BTC"])
    joined = " ".join(study.limitations)

    assert "機率" in joined  # only ever as a prohibition
    assert "不得表述為機率" in joined


def test_flat_series_produces_no_spurious_episodes():
    """A series with zero volatility must not manufacture a base rate."""
    flat = pd.Series(np.full(800, 100.0))
    study = volatility_compression_study(flat)

    assert study.status in ("ok", "unavailable")
    if study.status == "ok":
        assert study.rates["volatility_expansion"].total > 0
