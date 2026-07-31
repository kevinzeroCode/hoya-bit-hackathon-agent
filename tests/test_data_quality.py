"""Integrity tests for the shipped dataset and the checker itself."""

from __future__ import annotations

import pandas as pd
import pytest

from calc.data_quality import check_ohlc_integrity

ALL_ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP")


@pytest.mark.parametrize("asset", ALL_ASSETS)
def test_shipped_files_are_clean(raw_frames, asset):
    report = check_ohlc_integrity(raw_frames[asset])

    assert report.is_clean
    assert report.rows == 1826
    assert report.duplicate_dates == 0
    assert report.missing_dates == 0
    assert report.nan_cells == 0
    assert report.high_low_violations == 0
    assert report.open_out_of_range == 0
    assert report.close_out_of_range == 0
    assert report.non_positive_volume == 0
    assert report.first_date == pd.Timestamp("2021-06-01")
    assert report.last_date == pd.Timestamp("2026-05-31")


@pytest.mark.parametrize("asset", ALL_ASSETS)
def test_every_open_tracks_the_previous_close(raw_frames, asset):
    """Confirms the report's ~0.10% maximum-deviation claim across all assets.

    The true worst case is SOL at 0.1010%, which the report rounds to 0.10%.
    """
    report = check_ohlc_integrity(raw_frames[asset])

    assert report.max_open_gap <= 0.00102


def test_only_sol_exceeds_the_gap_threshold_and_only_twice(raw_frames):
    """Matches the report: SOL alone has 2 rows above 0.1%, the rest have none."""
    over = {a: check_ohlc_integrity(raw_frames[a]).open_gaps_over_threshold for a in ALL_ASSETS}

    assert over == {"BTC": 0, "ETH": 0, "SOL": 2, "BNB": 0, "XRP": 0}


def test_absent_overnight_gaps_are_flagged_as_a_note(raw_frames):
    """`open` carries no information the previous `close` lacks -- worth stating."""
    report = check_ohlc_integrity(raw_frames["BTC"])

    assert any("open" in note and "close" in note for note in report.notes)


# --------------------------------------------------------------------------
# the checker detects what it claims to detect
# --------------------------------------------------------------------------

def _valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4),
            "open": [10.0, 11.0, 12.0, 13.0],
            "high": [11.5, 12.5, 13.5, 14.5],
            "low": [9.5, 10.5, 11.5, 12.5],
            "close": [11.0, 12.0, 13.0, 14.0],
            "volume": [100.0, 110.0, 120.0, 130.0],
        }
    )


def test_missing_columns_short_circuit_without_raising():
    report = check_ohlc_integrity(_valid_frame().drop(columns=["volume"]))

    assert report.missing_columns == ("volume",)
    assert not report.is_clean


def test_detects_high_below_low():
    frame = _valid_frame()
    frame.loc[2, "high"] = 1.0

    assert check_ohlc_integrity(frame).high_low_violations == 1


def test_detects_close_outside_the_bar_range():
    frame = _valid_frame()
    frame.loc[1, "close"] = 99.0

    assert check_ohlc_integrity(frame).close_out_of_range == 1


def test_detects_a_missing_calendar_day():
    frame = _valid_frame().drop(index=2).reset_index(drop=True)
    report = check_ohlc_integrity(frame)

    assert report.missing_dates == 1
    assert not report.is_clean
    assert any("absent" in note for note in report.notes)


def test_detects_duplicate_dates():
    frame = pd.concat([_valid_frame(), _valid_frame().iloc[[0]]], ignore_index=True)

    assert check_ohlc_integrity(frame).duplicate_dates == 1


def test_detects_non_positive_volume():
    frame = _valid_frame()
    frame.loc[0, "volume"] = 0.0

    assert check_ohlc_integrity(frame).non_positive_volume == 1


def test_unsorted_input_is_ordered_before_checking():
    """Row order in the file must not change the verdict."""
    shuffled = _valid_frame().iloc[::-1].reset_index(drop=True)
    report = check_ohlc_integrity(shuffled)

    assert report.is_clean
    assert report.first_date == pd.Timestamp("2024-01-01")
