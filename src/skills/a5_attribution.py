"""A5 — Single-asset versus whole-market attribution.

The practically useful output: an asset moving in lockstep with the market is
unlikely to be explained by anything specific to itself, while one that has
decoupled probably is. That distinction is what makes it worth (or not worth)
spending a bounded research budget on asset-specific enquiry.

The skill states which of the two situations holds. It does not decide what to
do about it, and it draws no conclusion about *why* an asset decoupled --
price data cannot supply a cause.
"""

from __future__ import annotations

import pandas as pd

from calc.cross_asset import (
    dispersion,
    relative_return,
    relative_strength_percentile,
    rolling_beta,
    rolling_correlation,
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

SKILL_ID = "A5"
SKILL_NAME = "單幣特有 vs 全市場歸因"

CORRELATION_WINDOW = 90
RELATIVE_WINDOW = 365
RETURN_HORIZON = 30
HIGH_CORRELATION = 0.85


def run(bundle: MarketBundle) -> SkillResult:
    if bundle.asset == bundle.benchmark:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"分析標的即為基準（{bundle.benchmark}），與自身的相關性恆為 1，不具意義；"
            "此情形需改用其他基準或整體市場離散度。",
        )

    benchmark_close = bundle.benchmark_close()
    if benchmark_close is None:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"基準序列 {bundle.benchmark} 不可得，無法進行歸因。",
        )

    if bundle.bars < CORRELATION_WINDOW + 1:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"可用 K 線 {bundle.bars} 根，未達 {CORRELATION_WINDOW} 日滾動相關所需長度。",
        )

    close = bundle.close
    correlation = rolling_correlation(close, benchmark_close, CORRELATION_WINDOW).iloc[-1]
    beta = rolling_beta(close, benchmark_close, CORRELATION_WINDOW).iloc[-1]
    strength_percentile = relative_strength_percentile(close, benchmark_close, RELATIVE_WINDOW)
    excess = relative_return(close, benchmark_close, RETURN_HORIZON)

    peer_closes = {name: frame["close"] for name, frame in bundle.peers.items()}
    peer_closes[bundle.asset] = close
    group_dispersion = dispersion(peer_closes, RETURN_HORIZON)

    limitations: list[str] = []
    status = OK

    if pd.isna(strength_percentile):
        status = DEGRADED
        limitations.append(
            f"相對強弱百分位需 {RELATIVE_WINDOW} 根共同 K 線，目前不可得；"
            "不以較短視窗替代排序。"
        )
    if len(peer_closes) < 3:
        status = DEGRADED
        limitations.append(
            f"僅載入 {len(peer_closes)} 檔資產，市場離散度代表性有限。"
        )

    findings = {
        "benchmark": bundle.benchmark,
        "correlation_90d": None if pd.isna(correlation) else float(correlation),
        "beta_90d": None if pd.isna(beta) else float(beta),
        "relative_strength_percentile_1y": None if pd.isna(strength_percentile) else float(strength_percentile),
        "relative_return_30d": None if pd.isna(excess) else float(excess),
        "group_dispersion_30d": None if pd.isna(group_dispersion) else float(group_dispersion),
        "peer_count": len(peer_closes),
    }

    refs = [
        EvidenceRef(f"{SKILL_ID}.correlation", f"correlation_{CORRELATION_WINDOW}d",
                    None if pd.isna(correlation) else float(correlation),
                    "calc.cross_asset.rolling_correlation", CORRELATION_WINDOW),
        EvidenceRef(f"{SKILL_ID}.beta", f"beta_{CORRELATION_WINDOW}d",
                    None if pd.isna(beta) else float(beta),
                    "calc.cross_asset.rolling_beta", CORRELATION_WINDOW),
        EvidenceRef(f"{SKILL_ID}.relative_return", f"relative_return_{RETURN_HORIZON}d",
                    None if pd.isna(excess) else float(excess),
                    "calc.cross_asset.relative_return", RETURN_HORIZON),
    ]
    if not pd.isna(strength_percentile):
        refs.append(EvidenceRef(f"{SKILL_ID}.relative_strength", "relative_strength_percentile_1y",
                                float(strength_percentile),
                                "calc.cross_asset.relative_strength_percentile", RELATIVE_WINDOW))

    # The triage statement -- descriptive, and explicitly not a cause.
    if pd.isna(correlation):
        reading = "相關性不可得，無法判斷此資產屬單幣特有或全市場同步。"
    elif correlation >= HIGH_CORRELATION:
        reading = (
            f"近 {CORRELATION_WINDOW} 日與 {bundle.benchmark} 高度同步"
            f"（相關性 {fmt_ratio(correlation)}），價格變動大致可由全市場方向解釋，"
            "單幣特有因素的解釋空間相對有限。"
        )
    else:
        reading = (
            f"近 {CORRELATION_WINDOW} 日與 {bundle.benchmark} 同步程度較低"
            f"（相關性 {fmt_ratio(correlation)}），價格變動未能由全市場方向充分解釋，"
            "存在單幣特有因素的可能；價格資料無法指出該因素為何。"
        )

    limitations.append("相關性與 beta 僅描述同步程度與幅度，不表示任一方向的因果關係。")
    limitations.append(
        f"基準為 {bundle.benchmark}，其本身亦為單一資產而非市場總體指數；"
        "所謂「全市場」僅指本次載入的資產集合。"
    )

    lines = [
        bullet("基準", bundle.benchmark),
        bullet(f"{CORRELATION_WINDOW} 日相關性", fmt_ratio(correlation)),
        bullet(f"{CORRELATION_WINDOW} 日 beta", fmt_ratio(beta)),
        bullet("相對強弱 1 年百分位", fmt_ratio(strength_percentile)),
        bullet(f"近 {RETURN_HORIZON} 日相對表現", fmt_pct(excess, signed=True)),
        bullet(f"群體 {RETURN_HORIZON} 日報酬離散度", fmt_ratio(group_dispersion, 4),
               f"{len(peer_closes)} 檔資產"),
        "",
        reading,
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
