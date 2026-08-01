"""Market-series helpers: extraction, as-of filtering, and CSV/live cutover.

Deterministic and offline. The cutover logic implements the steering rule that
the organizer CSV and a live source are distinct sources: the 2026-06-01 switch
is explicit and overlapping observations are disclosed, never silently
overwritten.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from data.types import MarketBar

# CSV benchmark ends 2026-05-31; a live source provides 2026-06-01 onward.
CUTOVER_DATE = date(2026, 6, 1)


def closes(bars: Sequence[MarketBar]) -> list[float]:
    return [b.close for b in bars]


def volumes(bars: Sequence[MarketBar]) -> list[float]:
    return [b.volume for b in bars]


def bars_asof(bars: Sequence[MarketBar], as_of: date) -> list[MarketBar]:
    """Keep only completed bars dated on or before `as_of`."""
    return [b for b in bars if b.date <= as_of]


@dataclass(frozen=True)
class CutoverReport:
    """Disclosure of the CSV/live source switch and any overlap differences."""

    cutover_date: date
    overlap_dates: list[date]
    close_diffs: dict[date, float]  # live_close / csv_close - 1, per overlapping date


def merge_with_cutover(
    csv_bars: Sequence[MarketBar], live_bars: Sequence[MarketBar]
) -> tuple[list[MarketBar], CutoverReport]:
    """Merge CSV (authoritative before cutover) with live (from cutover onward).

    Dates before CUTOVER_DATE always come from the CSV benchmark; dates on/after
    it come from the live source. Overlapping pre-cutover dates supplied by the
    live source are recorded as differences for disclosure, but the CSV value is
    kept — the live data never silently overwrites the benchmark.
    """
    csv_by_date = {b.date: b for b in csv_bars}
    live_by_date = {b.date: b for b in live_bars}

    overlap = sorted(d for d in live_by_date if d < CUTOVER_DATE and d in csv_by_date)
    close_diffs = {
        d: live_by_date[d].close / csv_by_date[d].close - 1.0 for d in overlap
    }

    merged: dict[date, MarketBar] = {}
    for d, bar in csv_by_date.items():
        if d < CUTOVER_DATE:
            merged[d] = bar
    for d, bar in live_by_date.items():
        if d >= CUTOVER_DATE:
            merged[d] = bar

    ordered = [merged[d] for d in sorted(merged)]
    report = CutoverReport(
        cutover_date=CUTOVER_DATE, overlap_dates=overlap, close_diffs=close_diffs
    )
    return ordered, report
