"""Shared fixtures: the real shipped dataset, loaded once per session.

Tests assert against the actual CSVs rather than synthetic stand-ins, so a
change in methodology shows up as a failing golden value rather than as a
test that still passes on invented data.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

DATASET_DIR = Path(__file__).resolve().parents[1] / "HOYA_BIT_crypto_market_dataset" / "data"
ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP")


def _load(asset: str) -> pd.DataFrame:
    df = pd.read_csv(DATASET_DIR / f"{asset}_daily_ohlcv.csv", parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


@pytest.fixture(scope="session")
def raw_frames() -> dict[str, pd.DataFrame]:
    """Untouched frames with ``date`` as a column, for integrity checks."""
    return {asset: _load(asset) for asset in ASSETS}


@pytest.fixture(scope="session")
def frames(raw_frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Frames indexed by date, the convention the calc functions expect."""
    return {asset: df.set_index("date") for asset, df in raw_frames.items()}


@pytest.fixture(scope="session")
def closes(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    return {asset: df["close"] for asset, df in frames.items()}
