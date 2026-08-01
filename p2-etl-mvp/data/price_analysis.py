"""Extra deterministic price-analysis outputs, ported from the `price` branch
design doc (`price-data-analysis-outputs.html`, A5/A6/A7). All coin-agnostic,
pure-stdlib, reproducible; no LLM, no forward-fill.

- A6 `anomaly_days`      — ±Nσ event days (bounded query targets for Research).
- A5 attribution         — rolling correlation / beta / relative-strength percentile
                           vs a reference asset ("single-coin vs whole-market").
- A7 `analog_base_rates` — conditional self-history base rates (magnitude, not
                           direction; direction ≈ coin-flip and we say so).

Cross-asset rule respected: only returns/ratios/percentiles are compared across
coins — never base-asset volume.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone

from evidence.policies import SourceClass, reliability_for
from evidence.types import EvidenceDraft

from data.indicators import realized_volatility, simple_return
from data.market_series import bars_asof, closes
from data.market_worker import WorkerResult
from data.types import MarketBar

UTC = timezone.utc


# ── shared ──────────────────────────────────────────────────────────────────

def daily_log_returns(cl: Sequence[float]) -> list[float]:
    if len(cl) < 2:
        raise ValueError("need at least 2 closes")
    return [math.log(cl[i] / cl[i - 1]) for i in range(1, len(cl))]


def _quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (q in [0,1])."""
    s = sorted(values)
    if not s:
        raise ValueError("empty")
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ── A6 event timeline ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class AnomalyDay:
    day: date
    simple_return: float  # magnitude, reported to humans
    z: float              # log-return standardized (how extreme)


def anomaly_days(
    bars: Sequence[MarketBar], *, sigma: float = 3.0, min_history: int = 365
) -> list[AnomalyDay]:
    """Days whose log return is |z| >= sigma vs the asset's own full history."""
    cl = closes(bars)
    if len(cl) < min_history:
        raise ValueError(f"need >= {min_history} bars for a stable sigma")
    lr = daily_log_returns(cl)
    mean = statistics.fmean(lr)
    sd = statistics.pstdev(lr)
    if sd == 0:
        return []
    out: list[AnomalyDay] = []
    for i, r in enumerate(lr):
        z = (r - mean) / sd
        if abs(z) >= sigma:
            simple = cl[i + 1] / cl[i] - 1
            out.append(AnomalyDay(bars[i + 1].date, simple, z))
    return out


# ── A5 attribution (single-coin vs whole-market) ────────────────────────────

@dataclass(frozen=True)
class Attribution:
    reference: str
    correlation: float
    beta: float
    rel_strength_pctile: float  # ratio percentile over its own window


def _aligned_log_returns(a: Sequence[float], b: Sequence[float], window: int) -> tuple[list[float], list[float]]:
    n = min(len(a), len(b))
    la, lb = daily_log_returns(a[-n:]), daily_log_returns(b[-n:])
    if len(la) < window:
        raise ValueError("not enough overlapping history")
    return la[-window:], lb[-window:]


def rolling_correlation(a: Sequence[float], b: Sequence[float], window: int = 90) -> float:
    la, lb = _aligned_log_returns(a, b, window)
    return statistics.correlation(la, lb)


def rolling_beta(a: Sequence[float], b: Sequence[float], window: int = 90) -> float:
    """beta of a relative to b = cov(a,b) / var(b)."""
    la, lb = _aligned_log_returns(a, b, window)
    var_b = statistics.variance(lb)  # sample var, matches statistics.covariance (both n-1)
    if var_b == 0:
        raise ValueError("reference variance is zero")
    return statistics.covariance(la, lb) / var_b


def relative_strength_percentile(a: Sequence[float], b: Sequence[float], window: int = 252) -> float:
    n = min(len(a), len(b))
    ratios = [a[i] / b[i] for i in range(-n, 0)]
    win = ratios[-window:] if len(ratios) >= window else ratios
    last = win[-1]
    return sum(1 for r in win if r <= last) / len(win)


def attribution(
    target_closes: Sequence[float], reference_closes: Sequence[float],
    *, reference: str = "BTC", corr_window: int = 90, ratio_window: int = 252,
) -> Attribution:
    return Attribution(
        reference=reference,
        correlation=rolling_correlation(target_closes, reference_closes, corr_window),
        beta=rolling_beta(target_closes, reference_closes, corr_window),
        rel_strength_pctile=relative_strength_percentile(target_closes, reference_closes, ratio_window),
    )


# ── A7 historical analog base rates ─────────────────────────────────────────

@dataclass(frozen=True)
class BaseRates:
    condition_count: int
    vol_higher_frac: float  # magnitude signal (the honest one)
    up_frac: float          # direction signal (~coin-flip; disclosed as weak)


def _vol30_series(cl: Sequence[float], vol_window: int) -> list[tuple[int, float]]:
    """(index, vol30) for every day with enough history."""
    out = []
    for i in range(vol_window + 1, len(cl)):
        out.append((i, realized_volatility(cl[: i + 1], vol_window)))
    return out


def analog_base_rates(
    bars: Sequence[MarketBar], *, vol_window: int = 30, quantile: float = 0.2, horizon: int = 30
) -> BaseRates:
    """When vol30 is in its own lowest quintile, what happened `horizon` days later?"""
    cl = closes(bars)
    series = _vol30_series(cl, vol_window)
    if len(series) < 2:
        raise ValueError("not enough history for base rates")
    threshold = _quantile([v for _, v in series], quantile)
    vol_at = {i: v for i, v in series}
    condition = [i for i, v in series if v <= threshold]
    higher = up = usable = 0
    for i in condition:
        j = i + horizon
        if j not in vol_at:
            continue
        usable += 1
        if vol_at[j] > vol_at[i]:
            higher += 1
        if cl[j] > cl[i]:
            up += 1
    if usable == 0:
        raise ValueError("no analog windows with a full horizon")
    return BaseRates(usable, higher / usable, up / usable)


# ── evidence builders (market / high reliability, stanceless) ────────────────

def _draft(asset, fact, *, ref, params, metric, source_name, group, url, as_of) -> EvidenceDraft:
    return EvidenceDraft(
        asset=asset, source_type="market", source_name=source_name, source_url=url,
        published_at=datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC),
        fetched_at=datetime.now(UTC), query_or_parameters=params,
        content_reference=ref, normalized_fact=fact,
        reliability=reliability_for(SourceClass.DETERMINISTIC_CALC),
        independence_group=group, metric_name=metric,
    )


def build_event_timeline_evidence(
    asset: str, bars: Sequence[MarketBar], *, analysis_as_of: date,
    source_name: str = "public_market_data", independence_group: str = "organizer-public-market-data",
    source_url: str | None = None, sigma: float = 3.0,
) -> WorkerResult:
    window = bars_asof(bars, analysis_as_of)
    try:
        events = anomaly_days(window, sigma=sigma)
    except ValueError as exc:
        return WorkerResult("failed", [], [f"event timeline unavailable for {asset}: {exc}"])
    if not events:
        return WorkerResult("failed", [], [f"no ±{sigma:g}σ events for {asset}"])
    last = events[-1]
    fact = (
        f"{asset} 全段共 {len(events)} 個 ±{sigma:g}σ 異常日（截至 {window[-1].date} UTC）；"
        f"最近一次 {last.day}：單日 {last.simple_return:+.2%}（z {last.z:+.2f}）"
    )
    draft = _draft(
        asset, fact,
        ref=f"±{sigma:g}σ anomaly days = {len(events)}; latest {last.day}",
        params=f"anomaly_days sigma={sigma}; log-return z over full history",
        metric="anomaly_day_count", source_name=source_name, group=independence_group,
        url=source_url, as_of=window[-1].date,
    )
    return WorkerResult("completed", [draft], [])


def build_attribution_evidence(
    asset: str, target_bars: Sequence[MarketBar], reference_bars: Sequence[MarketBar],
    *, analysis_as_of: date, reference: str = "BTC",
    source_name: str = "public_market_data", independence_group: str = "organizer-public-market-data",
    source_url: str | None = None, corr_window: int = 90,
) -> WorkerResult:
    tc = closes(bars_asof(target_bars, analysis_as_of))
    rc = closes(bars_asof(reference_bars, analysis_as_of))
    try:
        attr = attribution(tc, rc, reference=reference, corr_window=corr_window)
    except (ValueError, statistics.StatisticsError) as exc:
        return WorkerResult("failed", [], [f"attribution unavailable for {asset}: {exc}"])
    fact = (
        f"{asset} 近 {corr_window} 日與 {reference} 相關性 {attr.correlation:.2f}、beta {attr.beta:.2f}、"
        f"相對強弱處於自身第 {attr.rel_strength_pctile * 100:.0f} 百分位"
        f"（相關性越高越隨全市場移動，非單幣事件）"
    )
    draft = _draft(
        asset, fact,
        ref=f"attribution vs {reference}: corr/beta over {corr_window}d",
        params=f"attribution ref={reference}; corr_window={corr_window}; log returns; ratio pctile 252d",
        metric="market_attribution", source_name=source_name, group=independence_group,
        url=source_url, as_of=bars_asof(target_bars, analysis_as_of)[-1].date,
    )
    return WorkerResult("completed", [draft], [])


# ── cross-asset comparison (1–2 coin contract; NEVER base-asset volume) ──────

def build_comparison_evidence(
    asset_a: str, asset_b: str, bars_a: Sequence[MarketBar], bars_b: Sequence[MarketBar],
    *, analysis_as_of: date, ret_window: int = 14, corr_window: int = 90, ratio_window: int = 252,
    source_name: str = "public_market_data", independence_group: str = "organizer-public-market-data",
    source_url: str | None = None,
) -> WorkerResult:
    """Deterministic cross-asset comparison facts (return / relative strength / correlation /
    beta). Coin-agnostic, stanceless. Cross-coin uses ONLY returns/ratios/percentiles —
    never base-asset volume (units differ)."""
    ca = closes(bars_asof(bars_a, analysis_as_of))
    cb = closes(bars_asof(bars_b, analysis_as_of))
    try:
        ret_a, ret_b = simple_return(ca, ret_window), simple_return(cb, ret_window)
        corr = rolling_correlation(ca, cb, corr_window)
        beta = rolling_beta(ca, cb, corr_window)
        pct = relative_strength_percentile(ca, cb, ratio_window)
    except (ValueError, statistics.StatisticsError) as exc:
        return WorkerResult("failed", [], [f"comparison unavailable for {asset_a} vs {asset_b}: {exc}"])

    as_of = bars_asof(bars_a, analysis_as_of)[-1].date
    stronger = asset_a if ret_a > ret_b else asset_b
    drafts = [
        _draft(
            asset_a,
            f"{asset_a} 近 {ret_window} 日報酬 {ret_a:+.2%}、{asset_b} {ret_b:+.2%}"
            f"（{stronger} 相對較強，差 {abs(ret_a - ret_b) * 100:.2f} 個百分點，截至 {as_of} UTC）",
            ref=f"relative {ret_window}d return {asset_a} vs {asset_b}",
            params=f"compare {asset_a} vs {asset_b}; return_window={ret_window}",
            metric=f"relative_return_{ret_window}d", source_name=source_name,
            group=independence_group, url=source_url, as_of=as_of,
        ),
        _draft(
            asset_a,
            f"{asset_a} 近 {corr_window} 日與 {asset_b} 相關性 {corr:.2f}、beta {beta:.2f}"
            f"（相關性越高越隨 {asset_b} 同向移動）",
            ref=f"correlation/beta {asset_a} vs {asset_b} over {corr_window}d",
            params=f"compare {asset_a} vs {asset_b}; corr_window={corr_window}; log returns",
            metric="pair_correlation", source_name=source_name,
            group=independence_group, url=source_url, as_of=as_of,
        ),
        _draft(
            asset_a,
            f"{asset_a}/{asset_b} 價格比值處於自身近 {ratio_window} 日第 {pct * 100:.0f} 百分位",
            ref=f"relative-strength ratio percentile {asset_a}/{asset_b}",
            params=f"compare {asset_a} vs {asset_b}; ratio percentile over {ratio_window}d",
            metric="relative_strength_pctile", source_name=source_name,
            group=independence_group, url=source_url, as_of=as_of,
        ),
    ]
    return WorkerResult("completed", drafts, [])
