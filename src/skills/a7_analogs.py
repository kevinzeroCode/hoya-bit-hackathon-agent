"""A7 — Historical analog base rates.

States what has followed similar conditions in this asset's own history. It is
the most easily misread section in the report, so the rendering is constrained
harder than anywhere else:

* outcomes appear as counts and an ordinal level, never as a percentage or a
  probability;
* the sample is reported three ways, including the two deflated ones;
* volatility and direction are presented separately, because the first is
  usually informative and the second usually is not -- and combining them
  would let the strong one carry the weak one.

The condition threshold defaults to an expanding window. The retrospective
alternative (``full_sample``) produces stronger-looking numbers by using data
that was not available at the time, and self-reports that when selected.
"""

from __future__ import annotations

from calc.analogs import volatility_compression_study

from .base import (
    OK,
    EvidenceRef,
    MarketBundle,
    SkillResult,
    fmt_ratio,
    render_section,
    unavailable,
)
from .lint import assert_no_advice

SKILL_ID = "A7"
SKILL_NAME = "歷史類比基準率"

HORIZON = 30
VOL_WINDOW = 30
MIN_BARS = 400

STRENGTH_TEXT = {
    "strong": "強",
    "moderate": "中等",
    "weak": "弱",
    "unavailable": "不可得",
}


def run(bundle: MarketBundle, mode: str = "expanding") -> SkillResult:
    if bundle.bars < MIN_BARS:
        return unavailable(
            SKILL_ID, SKILL_NAME, bundle,
            f"可用 K 線 {bundle.bars} 根，未達條件基準率所需的 {MIN_BARS} 根"
            f"（需涵蓋條件期間與 {HORIZON} 日前向水平）。",
        )

    study = volatility_compression_study(
        bundle.close, window=VOL_WINDOW, horizon=HORIZON, mode=mode
    )

    if study.status != OK:
        return SkillResult(
            skill_id=SKILL_ID,
            skill_name=SKILL_NAME,
            asset=bundle.asset,
            as_of=bundle.as_of,
            status="unavailable",
            findings={
                "condition": study.condition,
                "mode": study.mode,
                "observations": study.episodes.observations,
                "distinct_episodes": study.episodes.distinct_episodes,
            },
            evidence_refs=(),
            limitations=study.limitations,
            section_markdown=assert_no_advice(
                render_section(
                    SKILL_ID, SKILL_NAME,
                    [f"條件：{study.condition}", "", "獨立區間數不足，不輸出基準率。"],
                    study.limitations,
                )
            ),
        )

    volatility_rate = study.rates["volatility_expansion"]
    direction_rate = study.rates["direction_up"]

    findings = {
        "condition": study.condition,
        "mode": study.mode,
        "horizon": study.horizon,
        "observations": study.episodes.observations,
        "distinct_episodes": study.episodes.distinct_episodes,
        "effective_n": study.episodes.effective_n,
        "volatility_expansion": {
            "hits": volatility_rate.hits,
            "total": volatility_rate.total,
            "strength": volatility_rate.strength,
            "median_ratio": volatility_rate.median_ratio,
        },
        "direction_up": {
            "hits": direction_rate.hits,
            "total": direction_rate.total,
            "strength": direction_rate.strength,
        },
    }

    refs = (
        EvidenceRef(f"{SKILL_ID}.episodes", "distinct_episodes",
                    study.episodes.distinct_episodes, "calc.analogs.count_episodes", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.volatility_expansion", "volatility_expansion_count",
                    f"{volatility_rate.hits}/{volatility_rate.total}",
                    "calc.analogs.volatility_compression_study", bundle.bars),
        EvidenceRef(f"{SKILL_ID}.direction_up", "direction_up_count",
                    f"{direction_rate.hits}/{direction_rate.total}",
                    "calc.analogs.volatility_compression_study", bundle.bars),
    )

    median_text = (
        f"，中位擴張倍數 {fmt_ratio(volatility_rate.median_ratio)}×"
        if volatility_rate.median_ratio is not None
        else ""
    )

    lines = [
        f"條件：{study.condition}（門檻界定方式：`{study.mode}`）",
        "",
        (
            f"- 符合條件的觀測：{study.episodes.observations} 個，"
            f"對應約 {study.episodes.distinct_episodes} 段獨立區間"
        ),
        (
            f"- {HORIZON} 日後波動較高：{volatility_rate.hits}／{volatility_rate.total} 次"
            f"（強度 {STRENGTH_TEXT[volatility_rate.strength]}）{median_text}"
        ),
        (
            f"- {HORIZON} 日後價格較高：{direction_rate.hits}／{direction_rate.total} 次"
            f"（強度 {STRENGTH_TEXT[direction_rate.strength]}）"
        ),
        "",
        "以上為該資產自身歷史中曾經發生的次數統計，非對未來的預測，亦不構成機率陳述。",
    ]

    limitations = list(study.limitations)
    limitations.append(
        "波動與方向為兩項獨立統計：波動項的強度不得用以支持方向項的判讀。"
    )
    limitations.append(
        f"所提供的 {bundle.bars} 根 K 線若僅涵蓋單一市場循環，所有基準率均以該單一路徑為條件。"
    )

    return SkillResult(
        skill_id=SKILL_ID,
        skill_name=SKILL_NAME,
        asset=bundle.asset,
        as_of=bundle.as_of,
        status=OK,
        findings=findings,
        evidence_refs=refs,
        limitations=tuple(limitations),
        section_markdown=assert_no_advice(
            render_section(SKILL_ID, SKILL_NAME, lines, tuple(limitations))
        ),
    )
