"""A3 — Volatility and risk profile.

The point of this section is the percentile, not the raw volatility figure.
An annualised 25% means nothing on its own and cannot be compared across
assets; the same number expressed as "the 2nd percentile of this asset's own
history" is both meaningful and coin-agnostic.

Distribution shape is included because volatility alone hides it: two assets
can share a volatility number while having entirely different tail behaviour.
"""

from __future__ import annotations

import pandas as pd

from calc.indicators import (
    atr,
    max_drawdown,
    realized_volatility,
    return_distribution,
    volatility_percentile,
)

from .base import (
    DEGRADED,
    OK,
    EvidenceRef,
    MarketBundle,
    SkillResult,
    bullet,
    fmt_num,
    fmt_pct,
    fmt_ratio,
    render_section,
    unavailable,
)
from .lint import assert_no_advice

SKILL_ID = "A3"
SKILL_NAME = "波動與風險輪廓"

VOL_WINDOW = 30
ATR_WINDOW = 14
MIN_BARS = VOL_WINDOW + 1


def run(bundle: MarketBundle) -> SkillResult:
    if bundle.bars < MIN_BARS:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"可用 K 線 {bundle.bars} 根，未達 {VOL_WINDOW} 日波動所需的 {MIN_BARS} 根。",
        )

    close = bundle.close
    vol = realized_volatility(close, VOL_WINDOW).iloc[-1]
    vol_pct = volatility_percentile(close, VOL_WINDOW).iloc[-1]
    atr_value = (
        atr(bundle.high, bundle.low, close, ATR_WINDOW).iloc[-1]
        if bundle.bars >= ATR_WINDOW + 1
        else float("nan")
    )
    last_close = float(close.iloc[-1])
    atr_ratio = float(atr_value) / last_close if not pd.isna(atr_value) else float("nan")
    skew, kurtosis = return_distribution(close)
    worst_drawdown = max_drawdown(close)

    findings = {
        "realized_volatility_30d": None if pd.isna(vol) else float(vol),
        "volatility_percentile": None if pd.isna(vol_pct) else float(vol_pct),
        "atr14": None if pd.isna(atr_value) else float(atr_value),
        "atr14_ratio": None if pd.isna(atr_ratio) else float(atr_ratio),
        "return_skew": skew,
        "return_excess_kurtosis": kurtosis,
        "max_drawdown": worst_drawdown,
        "history_bars": bundle.bars,
    }

    refs = [
        EvidenceRef(f"{SKILL_ID}.vol30", "realized_volatility_30d",
                    None if pd.isna(vol) else float(vol),
                    "calc.indicators.realized_volatility", VOL_WINDOW),
        EvidenceRef(f"{SKILL_ID}.skew", "return_skew", skew,
                    "calc.indicators.return_distribution", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.kurtosis", "return_excess_kurtosis", kurtosis,
                    "calc.indicators.return_distribution", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.max_drawdown", "max_drawdown", worst_drawdown,
                    "calc.indicators.max_drawdown", bundle.bars),
    ]
    if not pd.isna(vol_pct):
        refs.append(EvidenceRef(f"{SKILL_ID}.vol_pctile", "volatility_percentile", float(vol_pct),
                                "calc.indicators.volatility_percentile", bundle.bars))
    if not pd.isna(atr_value):
        refs.append(EvidenceRef(f"{SKILL_ID}.atr14", "atr14", float(atr_value),
                                "calc.indicators.atr", ATR_WINDOW))

    limitations: list[str] = []
    status = OK
    if pd.isna(vol_pct):
        status = DEGRADED
        limitations.append("波動百分位不可得，僅提供原始波動值，缺少自身歷史基準。")
    if pd.isna(atr_value):
        status = DEGRADED
        limitations.append(f"ATR{ATR_WINDOW} 需 {ATR_WINDOW + 1} 根 K 線，目前不可得。")

    limitations.append(
        f"波動百分位以自身 {bundle.bars} 根 K 線（約 {bundle.bars / 365:.1f} 年）排序；"
        "絕對波動率跨幣不可比，百分位亦僅在同幣內具意義。"
    )
    limitations.append(
        "全段最大回撤與分布形狀取自所提供區間，若區間僅涵蓋單一市場循環，其代表性有限。"
    )

    lines = [
        bullet(f"{VOL_WINDOW} 日已實現波動（年化）", fmt_pct(vol)),
        bullet("波動百分位", fmt_ratio(vol_pct), f"自身 {bundle.bars} 根 K 線"),
        bullet(f"ATR{ATR_WINDOW}", fmt_num(atr_value),
               f"約當收盤價 {fmt_pct(atr_ratio)}" if not pd.isna(atr_ratio) else ""),
        bullet("報酬偏態", fmt_ratio(skew)),
        bullet("報酬超額峰態", fmt_ratio(kurtosis, 1)),
        bullet("全段最大回撤", fmt_pct(worst_drawdown, signed=True)),
    ]

    return SkillResult(
        skill_id=SKILL_ID,
        skill_name=SKILL_NAME,
        asset=bundle.asset,
        as_of=bundle.as_of,
        status=status,
        findings=findings,
        evidence_refs=tuple(refs),
        limitations=tuple(limitations),
        section_markdown=assert_no_advice(
            render_section(SKILL_ID, SKILL_NAME, lines, tuple(limitations))
        ),
    )
