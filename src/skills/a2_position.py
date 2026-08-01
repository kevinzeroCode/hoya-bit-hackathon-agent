"""A2 — Price position and trend snapshot.

Answers "where is this now" relative to the asset's own history. Every figure
here stands alone, so this skill degrades per-metric rather than as a whole:
losing MA200 to insufficient history should not also cost the report MA20.
"""

from __future__ import annotations

import pandas as pd

from calc.indicators import all_time_high_stats, distance_from_ma, range_position

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

SKILL_ID = "A2"
SKILL_NAME = "價格位置與趨勢快照"

MA_WINDOWS = (20, 50, 200)
RANGE_WINDOW_DAYS = 252


def run(bundle: MarketBundle) -> SkillResult:
    if bundle.bars < 2:
        return unavailable(SKILL_ID, SKILL_NAME, bundle, "K 線不足，無法計算任何位置指標。")

    close = bundle.close
    last_close = float(close.iloc[-1])

    ma_distances: dict[int, float | None] = {}
    unavailable_windows: list[int] = []
    for window in MA_WINDOWS:
        if bundle.bars < window:
            ma_distances[window] = None
            unavailable_windows.append(window)
            continue
        value = distance_from_ma(close, window).iloc[-1]
        ma_distances[window] = None if pd.isna(value) else float(value)
        if pd.isna(value):
            unavailable_windows.append(window)

    position = float("nan")
    if bundle.bars >= RANGE_WINDOW_DAYS:
        position = range_position(close, bundle.high, bundle.low, RANGE_WINDOW_DAYS).iloc[-1]

    ath = all_time_high_stats(close, bundle.high)

    findings = {
        "close": last_close,
        "ma_distance": ma_distances,
        "range_position": None if pd.isna(position) else float(position),
        "ath_close": ath.ath_close,
        "ath_close_date": ath.ath_close_date.date() if ath.ath_close_date is not None else None,
        "days_since_ath_close": ath.days_since_ath_close,
        "drawdown_from_ath_close": ath.drawdown_from_ath_close,
        "drawdown_from_ath_high": ath.drawdown_from_ath_high,
    }

    refs = [
        EvidenceRef(f"{SKILL_ID}.close", "close", last_close, "organizer_csv", 1),
        EvidenceRef(f"{SKILL_ID}.ath_close", "ath_close", ath.ath_close,
                    "calc.indicators.all_time_high_stats", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.drawdown_from_ath_close", "drawdown_from_ath_close",
                    ath.drawdown_from_ath_close, "calc.indicators.all_time_high_stats", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.drawdown_from_ath_high", "drawdown_from_ath_high",
                    ath.drawdown_from_ath_high, "calc.indicators.all_time_high_stats", bundle.bars),
    ]
    refs += [
        EvidenceRef(f"{SKILL_ID}.ma{w}", f"distance_from_ma{w}", ma_distances[w],
                    "calc.indicators.distance_from_ma", w)
        for w in MA_WINDOWS if ma_distances[w] is not None
    ]
    if not pd.isna(position):
        refs.append(EvidenceRef(f"{SKILL_ID}.range_position", "range_position", float(position),
                                "calc.indicators.range_position", RANGE_WINDOW_DAYS))

    limitations: list[str] = []
    status = OK
    if unavailable_windows:
        status = DEGRADED
        limitations.append(
            f"K 線 {bundle.bars} 根不足以計算 MA{'／MA'.join(str(w) for w in unavailable_windows)}；"
            "該項標示為不可得，其餘指標仍照常輸出。"
        )
    if pd.isna(position):
        status = DEGRADED
        limitations.append(f"52 週區間位置需 {RANGE_WINDOW_DAYS} 根 K 線，目前不可得。")

    # The two drawdowns answer different questions and are easy to conflate.
    limitations.append(
        "「距 ATH」有兩種基準：對最高收盤為 "
        f"{fmt_pct(ath.drawdown_from_ath_close, signed=True)}，對盤中最高價為 "
        f"{fmt_pct(ath.drawdown_from_ath_high, signed=True)}；兩者不可混用。"
    )
    limitations.append(
        f"此處「歷史高點」僅指所提供的 {bundle.bars} 根 K 線範圍內，非該資產真正的歷史高點。"
    )

    lines = [
        bullet("收盤價", fmt_num(last_close)),
    ]
    for window in MA_WINDOWS:
        value = ma_distances[window]    
        lines.append(bullet(f"距 MA{window}", fmt_pct(value, signed=True) if value is not None else "不可得"))
    lines += [
        bullet("52 週區間位置", fmt_ratio(position), "0 為區間下緣、1 為上緣"),
        bullet("最高收盤", fmt_num(ath.ath_close),
               f"{ath.ath_close_date.date()}，距今 {ath.days_since_ath_close} 天"
               if ath.ath_close_date is not None else ""),
        bullet("距最高收盤", fmt_pct(ath.drawdown_from_ath_close, signed=True)),
        bullet("距盤中最高價", fmt_pct(ath.drawdown_from_ath_high, signed=True)),
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
