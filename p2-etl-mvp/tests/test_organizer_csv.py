"""Tests for the organizer CSV adapter (deterministic, offline)."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from adapters.organizer_csv import (
    INDEPENDENCE_GROUP,
    SOURCE_NAME,
    default_data_dir,
    load_organizer_csv,
)
from data.types import MarketBar

HEADER = ["date", "open", "high", "low", "close", "volume"]


def _write_csv(path: Path, rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def test_load_valid_csv(tmp_path: Path):
    p = tmp_path / "BTC_daily_ohlcv.csv"
    _write_csv(
        p,
        [
            ["2021-06-01", 100, 110, 95, 105, 12.5],
            ["2021-06-02", 105, 120, 104, 118, 20.0],
        ],
    )
    bars = load_organizer_csv(p)
    assert len(bars) == 2
    assert isinstance(bars[0], MarketBar)
    assert bars[0].date == date(2021, 6, 1)
    assert bars[0].close == 105.0
    assert bars[1].date == date(2021, 6, 2)


def test_source_metadata_constants():
    # Must not imply any specific exchange.
    assert SOURCE_NAME == "public_market_data"
    assert INDEPENDENCE_GROUP == "organizer-public-market-data"


def test_missing_column_raises(tmp_path: Path):
    p = tmp_path / "x.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close"])  # no volume
        w.writerow(["2021-06-01", 1, 2, 0.5, 1.5])
    with pytest.raises(ValueError):
        load_organizer_csv(p)


def test_high_low_inconsistent_raises(tmp_path: Path):
    p = tmp_path / "x.csv"
    _write_csv(p, [["2021-06-01", 100, 90, 95, 98, 1.0]])  # high < low
    with pytest.raises(ValueError):
        load_organizer_csv(p)


def test_nonpositive_price_raises(tmp_path: Path):
    p = tmp_path / "x.csv"
    _write_csv(p, [["2021-06-01", 100, 110, 0, 105, 1.0]])  # low = 0
    with pytest.raises(ValueError):
        load_organizer_csv(p)


def test_duplicate_date_raises(tmp_path: Path):
    p = tmp_path / "x.csv"
    _write_csv(
        p,
        [
            ["2021-06-01", 100, 110, 95, 105, 1.0],
            ["2021-06-01", 100, 110, 95, 105, 1.0],
        ],
    )
    with pytest.raises(ValueError):
        load_organizer_csv(p)


def test_unsorted_input_is_sorted(tmp_path: Path):
    p = tmp_path / "x.csv"
    _write_csv(
        p,
        [
            ["2021-06-02", 105, 120, 104, 118, 2.0],
            ["2021-06-01", 100, 110, 95, 105, 1.0],
        ],
    )
    bars = load_organizer_csv(p)
    assert [b.date for b in bars] == [date(2021, 6, 1), date(2021, 6, 2)]


@pytest.mark.skipif(
    not (default_data_dir() / "BTC_daily_ohlcv.csv").exists(),
    reason="organizer dataset not reachable",
)
def test_real_btc_csv_loads():
    bars = load_organizer_csv(default_data_dir() / "BTC_daily_ohlcv.csv")
    assert len(bars) == 1826
    assert bars[0].date == date(2021, 6, 1)
    assert bars[-1].date == date(2026, 5, 31)
    assert all(bars[i].date < bars[i + 1].date for i in range(len(bars) - 1))
