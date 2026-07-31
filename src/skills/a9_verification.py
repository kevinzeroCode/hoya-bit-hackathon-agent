"""A9 — Cross-source verification and conflict flags (price side only).

This section cannot be completed from price data alone, and the skill is built
to say so rather than to approximate it. What price data *can* contribute is
supplied here:

* **Unexplained moves.** Days where the market moved more than the asset's own
  history would suggest is ordinary, for which this run holds no explanation.
  Naming them as unexplained is the honest output; inventing a cause is not.
* **Checkable price facts.** The same figures a later narrative would have to
  be reconciled against, recorded now in a form that can be checked rather
  than argued with.

Because no research sources exist in this run, the status is ``degraded`` by
construction. It can never report ``ok``: an unverified analysis must not be
presentable as a verified one.
"""

from __future__ import annotations

import pandas as pd

from calc.indicators import (
    multi_horizon_returns,
    price_volume_cross,
    volatility_percentile,
    zscore_anomalies,
)

from .base import (
    DEGRADED,
    EvidenceRef,
    MarketBundle,
    SkillResult,
    bullet,
    fmt_pct,
    fmt_ratio,
    render_section,
    unavailable,
)
from .lint import assert_no_advice

SKILL_ID = "A9"
SKILL_NAME = "跨來源驗證與衝突旗標"

LOOKBACK_DAYS = 90
SIGMA_THRESHOLD = 3.0
WINDOW = 30
MIN_BARS = 2 * WINDOW


def run(
    bundle: MarketBundle,
    lookback_days: int = LOOKBACK_DAYS,
    sources: tuple[str, ...] = (),
) -> SkillResult:
    """``sources`` names the research sources available this run.

    It is empty in every current run; the parameter exists so that when a
    research branch does supply sources, this skill's contract does not change.
    """
    if bundle.bars < MIN_BARS:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"可用 K 線 {bundle.bars} 根，未達 {MIN_BARS} 根，無法建立可供比對的價格事實。",
        )

    close = bundle.close
    anomalies = zscore_anomalies(close, SIGMA_THRESHOLD)
    recent = anomalies.iloc[-0:] if anomalies.empty else anomalies.tail(len(anomalies))
    if not anomalies.empty and isinstance(close.index, pd.DatetimeIndex):
        cutoff = close.index[-1] - pd.Timedelta(days=lookback_days)
        recent = anomalies[anomalies.index >= cutoff]

    unexplained = [
        {
            "date": index.date() if isinstance(index, pd.Timestamp) else str(index),
            "simple_return": float(row["simple_return"]),
            "zscore": float(row["zscore"]),
        }
        for index, row in recent.iterrows()
    ]

    returns = multi_horizon_returns(close, (1, 7, 30, 90))
    vol_percentile = volatility_percentile(close, WINDOW).iloc[-1]
    cross = price_volume_cross(close, bundle.volume, WINDOW)

    checkable_facts = {
        "return_7d": returns.get(7),
        "return_30d": returns.get(30),
        "return_90d": returns.get(90),
        "volatility_percentile": None if pd.isna(vol_percentile) else float(vol_percentile),
        "volume_change_30d": cross.volume_change,
        "price_volume_direction": cross.direction,
    }

    findings = {
        "sources_available": len(sources),
        "source_names": tuple(sources),
        "verification_performed": bool(sources),
        "unexplained_moves": unexplained,
        "lookback_days": lookback_days,
        "sigma_threshold": SIGMA_THRESHOLD,
        "checkable_price_facts": checkable_facts,
    }

    refs = [
        EvidenceRef(f"{SKILL_ID}.return_30d", "return_30d", returns.get(30),
                    "calc.indicators.multi_horizon_returns", 30),
        EvidenceRef(f"{SKILL_ID}.volume_change_30d", "volume_change_30d", cross.volume_change,
                    "calc.indicators.price_volume_cross", WINDOW),
    ]
    if not pd.isna(vol_percentile):
        refs.append(EvidenceRef(f"{SKILL_ID}.vol_pctile", "volatility_percentile",
                                float(vol_percentile), "calc.indicators.volatility_percentile",
                                bundle.bars))
    refs += [
        EvidenceRef(f"{SKILL_ID}.unexplained_{item['date']}", "anomalous_move",
                    item["simple_return"], "calc.indicators.zscore_anomalies", 1)
        for item in unexplained
    ]

    limitations = [
        (
            "本次執行未取得任何其他來源，無法進行跨來源驗證，亦無法判定是否存在實質衝突；"
            "本節僅提供價格側可供日後比對的事實。"
        ),
        (
            "價格資料可指出顯著變動發生於何時，無法指出原因；"
            "下列日期標示為「本次執行無來源可解釋」，並非斷定其無成因。"
        ),
        (
            f"異常判定以該資產自身 {bundle.bars} 根 K 線的報酬標準差為基準，"
            f"門檻 {SIGMA_THRESHOLD}σ 僅為統計界線，不代表事件重要性。"
        ),
    ]

    if unexplained:
        move_lines = [
            f"  - {item['date']}：{fmt_pct(item['simple_return'], signed=True)}"
            f"（z {item['zscore']:+.2f}）"
            for item in unexplained
        ]
        moves_block = [f"- 近 {lookback_days} 日內無來源可解釋的顯著變動："] + move_lines
    else:
        moves_block = [f"- 近 {lookback_days} 日內無超過 {SIGMA_THRESHOLD}σ 的顯著變動。"]

    lines = [
        bullet("可用其他來源數", str(len(sources))),
        bullet("是否已完成跨來源驗證", "否"),
        "",
        *moves_block,
        "",
        "可供日後比對的價格事實：",
        bullet("近 7 日報酬", fmt_pct(returns.get(7), signed=True)),
        bullet("近 30 日報酬", fmt_pct(returns.get(30), signed=True)),
        bullet("近 90 日報酬", fmt_pct(returns.get(90), signed=True)),
        bullet("波動百分位", fmt_ratio(vol_percentile)),
        bullet("近 30 日量能變動", fmt_pct(cross.volume_change, signed=True)),
    ]

    return SkillResult(
        skill_id=SKILL_ID,
        skill_name=SKILL_NAME,
        asset=bundle.asset,
        as_of=bundle.as_of,
        status=DEGRADED,
        findings=findings,
        evidence_refs=tuple(refs),
        limitations=tuple(limitations),
        section_markdown=assert_no_advice(
            render_section(SKILL_ID, SKILL_NAME, lines, tuple(limitations))
        ),
    )
