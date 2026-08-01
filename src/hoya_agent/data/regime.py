"""Market regime classification — deterministic synthesis of existing indicators.

Turns raw numbers (return, volatility, range position) into a readable market
state label, which is what the questions literally ask for ("整體市場狀態判斷",
"是否維持盤整"). No LLM. Coin-agnostic: the volatility comparison uses each
asset's OWN rolling history (a percentile), never absolute cross-asset values,
so it works for any of the five coins.

This is not a new raw indicator and not a trading signal (the brief explicitly
is "不是技術指標回測") — it is a description of state derived from indicators.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from hoya_agent.adapters.organizer_csv import INDEPENDENCE_GROUP, SOURCE_NAME
from hoya_agent.data.indicators import realized_volatility, simple_return
from hoya_agent.data.market_series import bars_asof, closes
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.policies import SourceClass, reliability_for
from hoya_agent.evidence.types import EvidenceDraft
from hoya_agent.models import Asset, MarketRegime as ContractMarketRegime, RegimeLabel as ContractRegimeLabel

UTC = timezone.utc
RegimeLabel = Literal["trending_up", "trending_down", "range_bound", "high_volatility", "mixed"]


@dataclass(frozen=True)
class RegimeThresholds:
    return_window: int = 14
    vol_window: int = 30
    range_window: int = 30
    trend_return_abs_min: float = 0.10   # |14d return| ≥ 10% → trending
    range_return_abs_max: float = 0.05   # |14d return| ≤ 5% → range-bound
    high_vol_pctile: float = 0.80        # vol in own top 20% → high-volatility


DEFAULT_THRESHOLDS = RegimeThresholds()

_LABEL_TXT: dict[str, str] = {
    "trending_up": "呈上升趨勢",
    "trending_down": "呈下降趨勢",
    "range_bound": "區間盤整",
    "high_volatility": "處於高波動",
    "mixed": "方向不明",
}


@dataclass(frozen=True)
class MarketRegime:
    asset: str
    label: RegimeLabel
    as_of: date
    return_window_pct: float
    vol_percentile: float
    range_position: float
    thresholds: RegimeThresholds


def _rolling_vols(cl: Sequence[float], window: int) -> list[float]:
    return [realized_volatility(cl[:i], window) for i in range(window + 1, len(cl) + 1)]


def classify_regime(
    asset: str,
    bars: Sequence[MarketBar],
    *,
    analysis_as_of: date,
    thresholds: RegimeThresholds = DEFAULT_THRESHOLDS,
) -> MarketRegime | None:
    t = thresholds
    cl = closes(bars_asof(bars, analysis_as_of))
    if len(cl) < max(t.return_window + 1, t.vol_window + 1, t.range_window):
        return None

    ret = simple_return(cl, t.return_window)
    vols = _rolling_vols(cl, t.vol_window)
    current_vol = vols[-1]
    vol_pctile = sum(1 for v in vols if v <= current_vol) / len(vols)

    window = cl[-t.range_window:]
    lo, hi = min(window), max(window)
    range_pos = 0.5 if hi == lo else (cl[-1] - lo) / (hi - lo)

    # First match wins.
    if vol_pctile >= t.high_vol_pctile:
        label: RegimeLabel = "high_volatility"
    elif abs(ret) >= t.trend_return_abs_min:
        label = "trending_up" if ret > 0 else "trending_down"
    elif abs(ret) <= t.range_return_abs_max:
        label = "range_bound"
    else:
        label = "mixed"

    last_date = bars_asof(bars, analysis_as_of)[-1].date
    return MarketRegime(asset, label, last_date, ret, vol_pctile, range_pos, t)


def classify_market_regime(
    asset: Asset,
    bars: Sequence[MarketBar],
    *,
    analysis_as_of: date,
    evidence_id: str | None = None,
    thresholds: RegimeThresholds = DEFAULT_THRESHOLDS,
) -> ContractMarketRegime:
    """Return the canonical contract shape, including an honest unavailable state."""
    computed = classify_regime(
        asset.value,
        bars,
        analysis_as_of=analysis_as_of,
        thresholds=thresholds,
    )
    if computed is None:
        return ContractMarketRegime(
            asset=asset,
            label=ContractRegimeLabel.unavailable,
            as_of=analysis_as_of.isoformat(),
            window_days=max(
                thresholds.return_window,
                thresholds.vol_window,
                thresholds.range_window,
            ),
        )
    return ContractMarketRegime(
        asset=asset,
        label=ContractRegimeLabel(computed.label),
        as_of=computed.as_of.isoformat(),
        window_days=max(
            thresholds.return_window,
            thresholds.vol_window,
            thresholds.range_window,
        ),
        metrics={
            "return_window": computed.return_window_pct,
            "realized_vol_percentile": computed.vol_percentile,
            "range_position": computed.range_position,
        },
        thresholds={
            "trend_return_abs_min": thresholds.trend_return_abs_min,
            "range_return_abs_max": thresholds.range_return_abs_max,
            "high_vol_pctile": thresholds.high_vol_pctile,
        },
        evidence_id=evidence_id,
    )


def build_regime_evidence(
    asset: str,
    bars: Sequence[MarketBar],
    *,
    analysis_as_of: date,
    source_name: str = SOURCE_NAME,
    independence_group: str = INDEPENDENCE_GROUP,
    source_url: str | None = None,
    thresholds: RegimeThresholds = DEFAULT_THRESHOLDS,
) -> WorkerResult:
    regime = classify_regime(asset, bars, analysis_as_of=analysis_as_of, thresholds=thresholds)
    if regime is None:
        return WorkerResult("failed", [], [f"regime unavailable for {asset}: not enough bars"])

    fetched_at = datetime.now(UTC)
    published_at = datetime(regime.as_of.year, regime.as_of.month, regime.as_of.day, tzinfo=UTC)
    fact = (
        f"{asset} 近 {thresholds.return_window} 日{_LABEL_TXT[regime.label]}"
        f"（報酬 {regime.return_window_pct:+.2%}、"
        f"波動處於自身歷史第 {regime.vol_percentile * 100:.0f} 百分位、"
        f"區間位置 {regime.range_position * 100:.0f}%，截至 {regime.as_of} UTC）"
    )
    draft = EvidenceDraft(
        asset=asset,
        source_type="market",
        source_name=source_name,
        source_url=source_url,
        published_at=published_at,
        fetched_at=fetched_at,
        query_or_parameters=(
            f"regime windows(ret={thresholds.return_window},vol={thresholds.vol_window},"
            f"range={thresholds.range_window}); thresholds(trend={thresholds.trend_return_abs_min},"
            f"range={thresholds.range_return_abs_max},hivol_pct={thresholds.high_vol_pctile})"
        ),
        content_reference=f"market regime = {regime.label} as of {regime.as_of}",
        normalized_fact=fact,
        reliability=reliability_for(SourceClass.DETERMINISTIC_CALC),
        independence_group=independence_group,
        metric_name="market_regime",
    )
    return WorkerResult("completed", [draft], [])
