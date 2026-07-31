"""A1 — Market regime headline.

Applies the assignment rules from `.kiro/steering/evidence-contracts.md` §16.3
exactly as written, against the asset's own rolling history.

The label enum has a name for the top of the volatility range
(``high_volatility``) and none for the bottom. An asset sitting at the floor
of its own volatility history therefore surfaces as ``range_bound`` or
``mixed``, discarding the most distinctive available fact about it. This skill
does **not** invent a label to fix that -- the enum belongs to the spec. It
reports the spec label, and separately discloses the compression state as its
own finding so the information is not lost.
"""

from __future__ import annotations

import pandas as pd

from calc.indicators import (
    multi_horizon_returns,
    range_position,
    realized_volatility,
    volatility_compression,
    volatility_percentile,
)

from .base import (
    DEGRADED,
    OK,
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

SKILL_ID = "A1"
SKILL_NAME = "市場體制標籤"

# §16.3 thresholds. Changing these changes published labels, so they are named.
TREND_RETURN_ABS_MIN = 0.10
RANGE_RETURN_ABS_MAX = 0.05
HIGH_VOL_PCTILE = 0.80
RETURN_WINDOW_DAYS = 30
RANGE_WINDOW_DAYS = 252
MIN_BARS = 252

LABEL_TEXT = {
    "trending_up": "上行趨勢",
    "trending_down": "下行趨勢",
    "range_bound": "區間整理",
    "high_volatility": "高波動",
    "mixed": "混合",
}


def assign_label(return_window: float, vol_percentile: float) -> str:
    """§16.3 assignment order, first match wins."""
    if vol_percentile >= HIGH_VOL_PCTILE:
        return "high_volatility"
    if abs(return_window) >= TREND_RETURN_ABS_MIN:
        return "trending_up" if return_window > 0 else "trending_down"
    if abs(return_window) <= RANGE_RETURN_ABS_MAX:
        return "range_bound"
    return "mixed"


def run(bundle: MarketBundle) -> SkillResult:
    if bundle.bars < MIN_BARS:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"可用 K 線 {bundle.bars} 根，未達區間位置所需的 {MIN_BARS} 根；不前向填補。",
        )

    close = bundle.close
    return_window = multi_horizon_returns(close, (RETURN_WINDOW_DAYS,))[RETURN_WINDOW_DAYS]
    vol_pct = volatility_percentile(close, RETURN_WINDOW_DAYS).iloc[-1]
    position = range_position(close, bundle.high, bundle.low, RANGE_WINDOW_DAYS).iloc[-1]

    if pd.isna(return_window) or pd.isna(vol_pct):
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            "報酬或波動百分位不可得，無法套用 §16.3 規則。",
        )

    label = assign_label(float(return_window), float(vol_pct))
    compression = volatility_compression(close)
    realized = realized_volatility(close, RETURN_WINDOW_DAYS).iloc[-1]

    findings = {
        "label": label,
        "window_days": RETURN_WINDOW_DAYS,
        "metrics": {
            "return_window": float(return_window),
            "realized_vol_pctile": float(vol_pct),
            "range_position": None if pd.isna(position) else float(position),
        },
        "thresholds": {
            "trend_return_abs_min": TREND_RETURN_ABS_MIN,
            "range_return_abs_max": RANGE_RETURN_ABS_MAX,
            "high_vol_pctile": HIGH_VOL_PCTILE,
        },
        "compression": {
            "status": compression.status,
            "volatility_percentile": compression.volatility_percentile,
            "days_in_compression": compression.days_in_compression,
            "history_bars": compression.history_bars,
        },
    }

    refs = (
        EvidenceRef(f"{SKILL_ID}.return_window", "return_30d", float(return_window),
                    "calc.indicators.multi_horizon_returns", RETURN_WINDOW_DAYS),
        EvidenceRef(f"{SKILL_ID}.vol_pctile", "realized_vol_pctile", float(vol_pct),
                    "calc.indicators.volatility_percentile", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.range_position", "range_position",
                    None if pd.isna(position) else float(position),
                    "calc.indicators.range_position", RANGE_WINDOW_DAYS),
        EvidenceRef(f"{SKILL_ID}.regime_label", "market_regime", label,
                    "skills.a1_regime.assign_label", bundle.bars),
    )

    limitations: list[str] = []
    status = OK

    # The gap this skill can see but not express in the enum.
    if compression.is_compressed and label not in ("high_volatility",):
        status = DEGRADED
        limitations.append(
            f"標籤列舉（§16.3）無低波動／壓縮狀態，本資產已實現波動處於自身歷史第 "
            f"{compression.volatility_percentile:.1%} 且持續 {compression.days_in_compression} 根 K 線，"
            f"此資訊無法由 `{label}` 表達，另列於下方壓縮狀態。是否新增標籤屬規格層決策。"
        )

    limitations.append(
        f"百分位以該資產自身 {compression.history_bars} 根 K 線（約 "
        f"{compression.history_bars / 365:.1f} 年）為基準，非跨幣可比，亦非長期母體。"
    )

    lines = [
        bullet("體制標籤", f"`{label}`（{LABEL_TEXT[label]}）"),
        bullet(f"{RETURN_WINDOW_DAYS} 日報酬", fmt_pct(return_window, signed=True)),
        bullet("已實現波動（年化）", fmt_pct(realized)),
        bullet("波動百分位", fmt_ratio(vol_pct), f"自身 {compression.history_bars} 根 K 線"),
        bullet("52 週區間位置", fmt_ratio(position)),
        "",
        (
            f"套用門檻：`trend_return_abs_min={TREND_RETURN_ABS_MIN}`、"
            f"`range_return_abs_max={RANGE_RETURN_ABS_MAX}`、"
            f"`high_vol_pctile={HIGH_VOL_PCTILE}`"
        ),
        "",
        bullet("波動壓縮狀態", f"`{compression.status}`",
               f"連續 {compression.days_in_compression} 根 K 線"
               if compression.days_in_compression else "未達持續性門檻"),
    ]

    return SkillResult(
        skill_id=SKILL_ID,
        skill_name=SKILL_NAME,
        asset=bundle.asset,
        as_of=bundle.as_of,
        status=status,
        findings=findings,
        evidence_refs=refs,
        limitations=tuple(limitations),
        section_markdown=assert_no_advice(
            render_section(SKILL_ID, SKILL_NAME, lines, tuple(limitations))
        ),
    )
