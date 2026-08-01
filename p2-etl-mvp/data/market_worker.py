"""Market Worker: turn deterministic OHLCV metrics into traceable EvidenceDrafts.

No LLM, no network. Each metric becomes a high-reliability EvidenceDraft that
records the window, the date range, and the exact value, so every market number
in the report can be traced back to reproducible tool output.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

from adapters.organizer_csv import INDEPENDENCE_GROUP, SOURCE_NAME
from evidence.policies import SourceClass, reliability_for
from evidence.types import EvidenceDraft

from data.indicators import (
    max_drawdown,
    realized_volatility,
    rolling_volume_zscore,
    simple_return,
)
from data.market_series import bars_asof, closes, volumes
from data.types import MarketBar

WorkerStatus = Literal["completed", "partial", "failed"]


@dataclass(frozen=True)
class MarketWindows:
    return_window: int = 14
    vol_window: int = 30
    drawdown_window: int = 90
    volume_window: int = 30


DEFAULT_WINDOWS = MarketWindows()


@dataclass(frozen=True)
class WorkerResult:
    status: WorkerStatus
    drafts: list[EvidenceDraft]
    degradation: list[str] = field(default_factory=list)


def _pct(x: float) -> str:
    return f"{x:.2%}"


def build_market_evidence(
    asset: str,
    bars: Sequence[MarketBar],
    *,
    analysis_as_of: date,
    source_name: str = SOURCE_NAME,
    independence_group: str = INDEPENDENCE_GROUP,
    source_url: str | None = None,
    windows: MarketWindows = DEFAULT_WINDOWS,
) -> WorkerResult:
    """Compute metrics on completed bars <= analysis_as_of and emit EvidenceDrafts.

    A metric that cannot be computed (not enough bars, zero variance) is skipped
    with a disclosed degradation note rather than fabricated.
    """
    usable = bars_asof(bars, analysis_as_of)
    fetched_at = datetime.now(timezone.utc)
    # Market reliability comes from the static policy, never from an LLM.
    reliability = reliability_for(SourceClass.DETERMINISTIC_CALC)

    drafts: list[EvidenceDraft] = []
    degradation: list[str] = []

    if not usable:
        return WorkerResult("failed", [], [f"{asset}: no bars at or before {analysis_as_of}"])

    c = closes(usable)
    v = volumes(usable)
    last_date = usable[-1].date
    published_at = datetime(last_date.year, last_date.month, last_date.day, tzinfo=timezone.utc)
    first_date = usable[0].date

    def add(metric_name: str, value: float, window: int, fact: str) -> None:
        drafts.append(
            EvidenceDraft(
                asset=asset,
                source_type="market",
                source_name=source_name,
                source_url=source_url,
                published_at=published_at,
                fetched_at=fetched_at,
                query_or_parameters=f"metric={metric_name}; window={window}; "
                f"range={first_date.isoformat()}..{last_date.isoformat()} UTC daily close",
                content_reference=f"{window}-bar {metric_name} over "
                f"{first_date.isoformat()}..{last_date.isoformat()}",
                normalized_fact=fact,
                reliability=reliability,
                independence_group=independence_group,
                metric_name=metric_name,
                metric_value=value,
            )
        )

    # Each metric is attempted independently; a gap in one never drops the others.
    w = windows
    try:
        r = simple_return(c, w.return_window)
        fact = f"{asset} 近 {w.return_window} 日報酬為 {_pct(r)}（截至 {last_date} UTC）"
        add("return_14d", r, w.return_window, fact)
    except ValueError as e:
        degradation.append(f"return_{w.return_window}d unavailable: {e}")

    try:
        vol = realized_volatility(c, w.vol_window)
        fact = f"{asset} 近 {w.vol_window} 日已實現波動（日）為 {vol:.4f}（截至 {last_date} UTC）"
        add("realized_vol_30d", vol, w.vol_window, fact)
    except ValueError as e:
        degradation.append(f"realized_vol_{w.vol_window}d unavailable: {e}")

    try:
        mdd = max_drawdown(c, w.drawdown_window)
        fact = f"{asset} 近 {w.drawdown_window} 日最大回撤為 {_pct(mdd)}（截至 {last_date} UTC）"
        add("max_drawdown_90d", mdd, w.drawdown_window, fact)
    except ValueError as e:
        degradation.append(f"max_drawdown_{w.drawdown_window}d unavailable: {e}")

    try:
        z = rolling_volume_zscore(v, w.volume_window)
        fact = f"{asset} 最新成交量相對自身近 {w.volume_window} 日的 z-score 為 {z:.2f}"
        add("volume_zscore_30d", z, w.volume_window, fact)
    except ValueError as e:
        degradation.append(f"volume_zscore_{w.volume_window}d unavailable: {e}")

    if not drafts:
        return WorkerResult("failed", [], degradation)
    status: WorkerStatus = "completed" if not degradation else "partial"
    return WorkerResult(status, drafts, degradation)
