"""A4 — Participation and liquidity check.

Whether a price move came with volume behind it. Every figure is a ratio
against the asset's *own* baseline, which is not a stylistic choice: the
organizer files carry base-asset volume, and one BTC is not comparable to one
XRP, so no cross-asset volume comparison is possible from this data at all.

When the long baseline is unavailable the skill shortens the window rather
than dropping the section, and says that it did.
"""

from __future__ import annotations

import pandas as pd

from calc.indicators import (
    price_volume_cross,
    volume_mean_percentile,
    volume_mean_ratio,
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

SKILL_ID = "A4"
SKILL_NAME = "參與度與流動性檢查"

SHORT_WINDOW = 30
LONG_WINDOW = 365
FALLBACK_LONG_WINDOW = 90

DIRECTION_TEXT = {
    "up_on_rising_volume": "價漲且量增",
    "up_on_falling_volume": "價漲但量縮",
    "down_on_rising_volume": "價跌但量增",
    "down_on_falling_volume": "價跌且量縮",
}


def run(bundle: MarketBundle) -> SkillResult:
    required = 2 * SHORT_WINDOW
    if bundle.bars < required:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"可用 K 線 {bundle.bars} 根，未達價量對照所需的 {required} 根。",
        )

    volume = bundle.volume
    limitations: list[str] = []
    status = OK

    long_window = LONG_WINDOW
    if bundle.bars < LONG_WINDOW:
        long_window = FALLBACK_LONG_WINDOW
        status = DEGRADED
        limitations.append(
            f"K 線 {bundle.bars} 根不足 {LONG_WINDOW} 根，長期量能基準改用 "
            f"{FALLBACK_LONG_WINDOW} 日；視窗已縮短，與完整基準不可直接比較。"
        )

    ratio = volume_mean_ratio(volume, SHORT_WINDOW, long_window).iloc[-1]
    mean_percentile = volume_mean_percentile(volume, SHORT_WINDOW).iloc[-1]
    cross = price_volume_cross(bundle.close, volume, SHORT_WINDOW)
    recent_mean = float(volume.iloc[-SHORT_WINDOW:].mean())

    findings = {
        "volume_mean_ratio": None if pd.isna(ratio) else float(ratio),
        "short_window": SHORT_WINDOW,
        "long_window": long_window,
        "volume_mean_percentile": None if pd.isna(mean_percentile) else float(mean_percentile),
        "recent_mean_volume": recent_mean,
        "price_change": cross.price_change,
        "volume_change": cross.volume_change,
        "direction": cross.direction,
    }

    refs = [
        EvidenceRef(f"{SKILL_ID}.volume_ratio", f"volume_mean_ratio_{SHORT_WINDOW}_{long_window}",
                    None if pd.isna(ratio) else float(ratio),
                    "calc.indicators.volume_mean_ratio", long_window),
        EvidenceRef(f"{SKILL_ID}.recent_mean_volume", "recent_mean_volume", recent_mean,
                    "calc.indicators", SHORT_WINDOW),
        EvidenceRef(f"{SKILL_ID}.price_change", "price_change", cross.price_change,
                    "calc.indicators.price_volume_cross", SHORT_WINDOW),
        EvidenceRef(f"{SKILL_ID}.volume_change", "volume_change", cross.volume_change,
                    "calc.indicators.price_volume_cross", SHORT_WINDOW),
    ]
    if not pd.isna(mean_percentile):
        refs.append(EvidenceRef(f"{SKILL_ID}.volume_pctile", "volume_mean_percentile",
                                float(mean_percentile), "calc.indicators.volume_mean_percentile",
                                bundle.bars))

    if pd.isna(mean_percentile):
        status = DEGRADED
        limitations.append("量能百分位不可得，僅提供比值，缺少自身歷史基準。")

    limitations.append(
        "成交量為計價基礎資產單位，僅可與同一資產自身歷史比較；跨幣量能不可直接比較。"
    )
    limitations.append(
        "量能比值與百分位為兩種不同量度：比值對照長短期均值，百分位對照自身歷史排序，兩者不應互相取代。"
    )

    lines = [
        bullet(f"{SHORT_WINDOW} 日量均 ÷ {long_window} 日量均", fmt_ratio(ratio)),
        bullet(f"{SHORT_WINDOW} 日量均百分位", fmt_ratio(mean_percentile),
               f"自身 {bundle.bars} 根 K 線"),
        bullet(f"{SHORT_WINDOW} 日量均", fmt_num(recent_mean, 0), "基礎資產單位"),
        bullet(f"近 {SHORT_WINDOW} 日價格變動", fmt_pct(cross.price_change, signed=True)),
        bullet(f"近 {SHORT_WINDOW} 日量能變動", fmt_pct(cross.volume_change, signed=True),
               "對照前一個同長度區間"),
        bullet("價量交叉", DIRECTION_TEXT[cross.direction]),
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
