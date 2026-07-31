"""Tests for the expanding-percentile primitive.

This is the one place a look-ahead bug could enter every other percentile in
the package, so it is tested directly rather than only through its callers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calc.percentile import expanding_percentile


def test_ranks_only_against_prior_values():
    # Each point ranks within itself and everything before it, never after.
    s = pd.Series([10.0, 20.0, 5.0])
    result = expanding_percentile(s)

    assert result.iloc[0] == pytest.approx(1.0)  # alone -> top of a 1-point history
    assert result.iloc[1] == pytest.approx(1.0)  # 20 is the highest of (10, 20)
    assert result.iloc[2] == pytest.approx(1 / 3)  # 5 is lowest of (10, 20, 5)


def test_ties_take_average_rank():
    s = pd.Series([1.0, 1.0])
    result = expanding_percentile(s)
    # Two equal values share ranks 1 and 2 -> average 1.5 of 2 -> 0.75.
    assert result.iloc[1] == pytest.approx(0.75)


def test_min_periods_blocks_thin_samples():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    result = expanding_percentile(s, min_periods=3)

    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(1.0)


def test_future_bars_cannot_change_a_past_ranking(closes):
    """The property that makes this safe: appending data never rewrites history.

    A full-sample rank would move every earlier value when new bars arrive.
    """
    btc = closes["BTC"]
    early, extended = btc.iloc[:400], btc.iloc[:600]

    early_result = expanding_percentile(early, min_periods=30)
    extended_result = expanding_percentile(extended, min_periods=30)

    pd.testing.assert_series_equal(early_result, extended_result.iloc[:400])


def test_differs_from_full_sample_rank_except_at_the_final_bar(closes):
    """Guards the subtle trap: the two agree at the last bar and nowhere else.

    Checking a full-sample implementation only at the newest bar would look
    correct while being wrong for every historical point.
    """
    btc = closes["BTC"]
    expanding = expanding_percentile(btc)
    full_sample = btc.rank(pct=True)

    assert expanding.iloc[-1] == pytest.approx(full_sample.iloc[-1])
    assert not np.isclose(expanding.iloc[500], full_sample.iloc[500])
