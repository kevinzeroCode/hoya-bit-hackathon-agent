"""OHLCV integrity checks.

Every calculation in this package assumes the bars are complete, ordered and
internally consistent. That assumption is cheap to verify and expensive to
get wrong, so it is checked explicitly rather than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class IntegrityReport:
    """Findings from an OHLCV integrity check."""

    rows: int
    missing_columns: tuple[str, ...]
    duplicate_dates: int
    missing_dates: int
    nan_cells: int
    high_low_violations: int
    open_out_of_range: int
    close_out_of_range: int
    non_positive_volume: int
    max_open_gap: float
    open_gaps_over_threshold: int
    first_date: pd.Timestamp | None
    last_date: pd.Timestamp | None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        """True when nothing that would corrupt a calculation was found.

        Open-vs-previous-close gaps are excluded: a real gap is a fact about
        the market, not a defect in the file.
        """
        return (
            not self.missing_columns
            and self.duplicate_dates == 0
            and self.missing_dates == 0
            and self.nan_cells == 0
            and self.high_low_violations == 0
            and self.open_out_of_range == 0
            and self.close_out_of_range == 0
            and self.non_positive_volume == 0
        )


def check_ohlc_integrity(df: pd.DataFrame, gap_threshold: float = 0.001) -> IntegrityReport:
    """Validate an OHLCV frame and report what is wrong, without raising.

    Checks that the calculations downstream depend on: required columns
    present, one row per calendar day with no duplicates or gaps, no NaNs,
    ``high >= low``, open/close inside the bar's range, and positive volume.

    Also measures how far each ``open`` sits from the previous ``close``.
    A file where that deviation is always ~0 has no overnight gaps, which
    means ``open`` carries almost no information the previous ``close`` does
    not already carry -- worth knowing before building anything on it.
    ``gap_threshold`` defaults to 0.1%.
    """
    missing_columns = tuple(c for c in REQUIRED_COLUMNS if c not in df.columns)
    if missing_columns:
        return IntegrityReport(
            rows=len(df),
            missing_columns=missing_columns,
            duplicate_dates=0,
            missing_dates=0,
            nan_cells=int(df.isna().sum().sum()),
            high_low_violations=0,
            open_out_of_range=0,
            close_out_of_range=0,
            non_positive_volume=0,
            max_open_gap=float("nan"),
            open_gaps_over_threshold=0,
            first_date=None,
            last_date=None,
            notes=(f"missing required columns: {', '.join(missing_columns)}",),
        )

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False)
    frame = frame.sort_values("date").reset_index(drop=True)

    expected = pd.date_range(frame["date"].min(), frame["date"].max(), freq="D")
    missing_dates = len(expected.difference(pd.DatetimeIndex(frame["date"])))

    prev_close = frame["close"].shift(1)
    open_gap = ((frame["open"] - prev_close).abs() / prev_close).dropna()

    notes: list[str] = []
    if not open_gap.empty and open_gap.max() < gap_threshold * 2:
        notes.append(
            "every open is within a fraction of the prior close: this series has no "
            "overnight gaps, so `open` adds essentially no information beyond `close`"
        )
    if missing_dates:
        notes.append(f"{missing_dates} calendar day(s) absent between first and last row")

    return IntegrityReport(
        rows=len(frame),
        missing_columns=(),
        duplicate_dates=int(frame["date"].duplicated().sum()),
        missing_dates=missing_dates,
        nan_cells=int(frame.isna().sum().sum()),
        high_low_violations=int((frame["high"] < frame["low"]).sum()),
        open_out_of_range=int(((frame["open"] > frame["high"]) | (frame["open"] < frame["low"])).sum()),
        close_out_of_range=int(((frame["close"] > frame["high"]) | (frame["close"] < frame["low"])).sum()),
        non_positive_volume=int((frame["volume"] <= 0).sum()),
        max_open_gap=float(open_gap.max()) if not open_gap.empty else float("nan"),
        open_gaps_over_threshold=int((open_gap > gap_threshold).sum()),
        first_date=frame["date"].iloc[0],
        last_date=frame["date"].iloc[-1],
        notes=tuple(notes),
    )
