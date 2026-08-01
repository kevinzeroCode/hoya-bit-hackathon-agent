"""Provisional local domain types for the P2 ETL prototype.

These mirror the fields the shared contract will need. When P1 lands the
canonical Pydantic models (`models.py`), swap these for imports from there;
keep the field names identical so the swap is mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MarketBar:
    """One completed UTC daily OHLCV bar."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
