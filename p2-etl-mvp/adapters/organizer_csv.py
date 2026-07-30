"""Organizer CSV adapter.

Loads the organizer-provided Daily OHLCV benchmark. This is a common historical
benchmark named `public_market_data`; we must NOT infer that it came from
Binance or any specific exchange. Deterministic, offline, no LLM.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from data.types import MarketBar

SOURCE_NAME = "public_market_data"
INDEPENDENCE_GROUP = "organizer-public-market-data"

_REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def default_data_dir() -> Path:
    """Locate the organizer dataset whether run standalone or inside the repo."""
    base = Path(__file__).resolve().parents[2]
    candidates = [
        base / "HOYA_BIT_crypto_market_dataset" / "data",                      # inside the repo
        base / "hoya-bit-hackathon-agent" / "HOYA_BIT_crypto_market_dataset" / "data",  # sibling checkout
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def load_organizer_csv(path: Path) -> list[MarketBar]:
    """Parse and validate one organizer OHLCV CSV into sorted MarketBars.

    Raises ValueError on any schema or integrity violation so bad data can never
    silently reach an indicator or the Evidence Ledger.
    """
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        missing = [c for c in _REQUIRED_COLUMNS if c not in fields]
        if missing:
            raise ValueError(f"missing columns {missing} in {path}")
        rows = list(reader)

    bars: list[MarketBar] = []
    seen: set[date] = set()
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            d = date.fromisoformat(row["date"].strip())
            o, h, low, c, v = (
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
            )
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"unparseable row {i} in {path}: {exc}") from exc

        if d in seen:
            raise ValueError(f"duplicate date {d} in {path}")
        seen.add(d)

        if min(o, h, low, c) <= 0:
            raise ValueError(f"non-positive price on {d} in {path}")
        if v < 0:
            raise ValueError(f"negative volume on {d} in {path}")
        if h < low or h < o or h < c or low > o or low > c:
            raise ValueError(f"OHLC inconsistency on {d} in {path}")

        bars.append(MarketBar(date=d, open=o, high=h, low=low, close=c, volume=v))

    bars.sort(key=lambda b: b.date)
    return bars
