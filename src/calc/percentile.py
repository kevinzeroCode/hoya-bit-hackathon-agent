"""Shared look-ahead-safe percentile primitive.

Every percentile used elsewhere in this package (volatility percentile,
volume percentile, relative-strength percentile, the compression detector)
must rank a value only against points that existed at or before it in time.
Ranking against the full sample instead leaks future bars into a value
that is supposed to describe "as of this day" -- see
docs/price-data-analysis-outputs.html Section 5.1.
"""

from __future__ import annotations

import pandas as pd


def expanding_percentile(series: pd.Series, min_periods: int = 1) -> pd.Series:
    """Percentile rank (0..1) of each point among itself and all prior points.

    Ties are resolved with average rank. Points before ``min_periods``
    observations are available are ``NaN`` rather than silently ranked
    against a too-small sample.
    """
    return series.expanding(min_periods=min_periods).rank(pct=True)
