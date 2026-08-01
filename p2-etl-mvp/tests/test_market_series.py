"""Tests for market-series helpers: extraction, as-of filtering, source cutover."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from adapters.organizer_csv import default_data_dir, load_organizer_csv
from data.indicators import simple_return
from data.market_series import (
    CUTOVER_DATE,
    bars_asof,
    closes,
    merge_with_cutover,
    volumes,
)
from data.types import MarketBar


def _bar(d: date, close: float, volume: float = 1.0) -> MarketBar:
    return MarketBar(date=d, open=close, high=close, low=close, close=close, volume=volume)


def test_closes_and_volumes_extract():
    bars = [_bar(date(2026, 5, 1), 10, 100), _bar(date(2026, 5, 2), 11, 200)]
    assert closes(bars) == [10.0, 11.0]
    assert volumes(bars) == [100.0, 200.0]


def test_bars_asof_filters_future():
    bars = [_bar(date(2026, 5, 1), 10), _bar(date(2026, 5, 2), 11), _bar(date(2026, 5, 3), 12)]
    kept = bars_asof(bars, date(2026, 5, 2))
    assert [b.date for b in kept] == [date(2026, 5, 1), date(2026, 5, 2)]


def test_merge_with_cutover_splits_by_date():
    csv_bars = [_bar(date(2026, 5, 30), 100), _bar(date(2026, 5, 31), 101)]
    live_bars = [_bar(date(2026, 6, 1), 103), _bar(date(2026, 6, 2), 104)]
    merged, report = merge_with_cutover(csv_bars, live_bars)
    assert [b.date for b in merged] == [
        date(2026, 5, 30),
        date(2026, 5, 31),
        date(2026, 6, 1),
        date(2026, 6, 2),
    ]
    assert report.cutover_date == CUTOVER_DATE
    assert report.overlap_dates == []


def test_merge_records_overlap_without_silent_overwrite():
    # live also returns a pre-cutover date with a different close -> disclose, keep CSV.
    csv_bars = [_bar(date(2026, 5, 31), 100.0)]
    live_bars = [_bar(date(2026, 5, 31), 110.0), _bar(date(2026, 6, 1), 120.0)]
    merged, report = merge_with_cutover(csv_bars, live_bars)
    # historical date keeps the CSV value, not the live one
    kept = {b.date: b.close for b in merged}
    assert kept[date(2026, 5, 31)] == 100.0
    assert kept[date(2026, 6, 1)] == 120.0
    assert date(2026, 5, 31) in report.overlap_dates
    assert report.close_diffs[date(2026, 5, 31)] == pytest.approx(110.0 / 100.0 - 1)


@pytest.mark.skipif(
    not (default_data_dir() / "BTC_daily_ohlcv.csv").exists(),
    reason="organizer dataset not reachable",
)
def test_real_csv_feeds_indicators():
    bars = load_organizer_csv(default_data_dir() / "BTC_daily_ohlcv.csv")
    assert simple_return(closes(bars), 14) == pytest.approx(-0.048843, abs=1e-6)
