"""Assemble skill results into one Traditional Chinese analysis document.

Deterministic string assembly only -- no model is involved in producing report
text. The lint runs over the finished document as well as over each section,
so a phrasing problem introduced by the assembly itself cannot slip through.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import (
    a1_regime,
    a2_position,
    a3_risk,
    a4_participation,
    a5_attribution,
    a7_analogs,
    a9_verification,
)
from .base import DEGRADED, OK, UNAVAILABLE, MarketBundle, SkillResult, unavailable
from .html_report import render_report_html
from .lint import assert_no_advice

SKILL_ORDER = ("A1", "A2", "A3", "A4", "A5", "A7", "A9")

SKILL_RUNNERS = {
    "A1": a1_regime.run,
    "A2": a2_position.run,
    "A3": a3_risk.run,
    "A4": a4_participation.run,
    "A5": a5_attribution.run,
    "A7": a7_analogs.run,
    "A9": a9_verification.run,
}

SKILL_NAMES = {
    "A1": a1_regime.SKILL_NAME,
    "A2": a2_position.SKILL_NAME,
    "A3": a3_risk.SKILL_NAME,
    "A4": a4_participation.SKILL_NAME,
    "A5": a5_attribution.SKILL_NAME,
    "A7": a7_analogs.SKILL_NAME,
    "A9": a9_verification.SKILL_NAME,
}

STATUS_TEXT = {OK: "完成", DEGRADED: "部分降級", UNAVAILABLE: "不可得"}


@dataclass(frozen=True)
class AnalysisReport:
    """A rendered report plus the structured results behind it.

    Both renderings are produced from one run of the skills, so the Markdown
    and the HTML always describe the same numbers.
    """

    asset: str
    as_of: date | None
    results: tuple[SkillResult, ...]
    markdown: str
    html: str

    @property
    def statuses(self) -> dict[str, str]:
        return {r.skill_id: r.status for r in self.results}

    def result(self, skill_id: str) -> SkillResult | None:
        return next((r for r in self.results if r.skill_id == skill_id), None)


def run_skills(bundle: MarketBundle, skill_ids: tuple[str, ...] = SKILL_ORDER) -> tuple[SkillResult, ...]:
    """Run the requested skills in report order.

    One skill failing internally must not take the others with it, so an
    unexpected exception is converted into an ``unavailable`` result rather
    than propagating. Skills are not supposed to raise; this is the net under
    that contract, not a substitute for it.
    """
    results: list[SkillResult] = []
    for skill_id in skill_ids:
        runner = SKILL_RUNNERS.get(skill_id)
        if runner is None:
            continue
        try:
            results.append(runner(bundle))
        except Exception as exc:  # noqa: BLE001 - deliberate net; see docstring
            results.append(
                unavailable(
                    skill_id,
                    SKILL_NAMES.get(skill_id, skill_id),
                    bundle,
                    f"技能執行時發生非預期錯誤（{type(exc).__name__}），已標示為不可得。",
                )
            )
    return tuple(results)


def render_report(bundle: MarketBundle, results: tuple[SkillResult, ...]) -> str:
    """Compose the document: header, coverage table, sections, disclosure."""
    as_of = bundle.as_of.isoformat() if bundle.as_of else "不可得"
    header = [
        f"# {bundle.asset} 價格資料分析",
        "",
        f"- 分析基準日（as_of）：{as_of}",
        f"- 可用 K 線：{bundle.bars} 根（約 {bundle.bars / 365:.1f} 年）",
        "- 資料來源類型：`public_market_data`",
        "",
        "## 產出覆蓋狀態",
        "",
        "| 產出 | 名稱 | 狀態 |",
        "|---|---|---|",
    ]
    header += [
        f"| {r.skill_id} | {r.skill_name} | {STATUS_TEXT.get(r.status, r.status)} |"
        for r in results
    ]

    sections = ["", "## 分析產出", ""]
    for result in results:
        sections.append(result.section_markdown)
        sections.append("")

    all_limitations: list[str] = []
    for result in results:
        for item in result.limitations:
            entry = f"（{result.skill_id}）{item}"
            if entry not in all_limitations:
                all_limitations.append(entry)

    footer = [
        "## 總體限制與揭露",
        "",
        *[f"- {item}" for item in all_limitations],
        "",
        "本文所有數值由決定性計算產生，未經模型生成或調整；相同輸入與相同 as_of 可完整重現。",
        "本文僅描述市場資料所呈現的狀態，不對任何交易或決策提供指引。",
    ]

    return assert_no_advice("\n".join(header + sections + footer) + "\n")


def build_report(bundle: MarketBundle, skill_ids: tuple[str, ...] = SKILL_ORDER) -> AnalysisReport:
    """Run the skills once and render both output formats from that one run."""
    results = run_skills(bundle, skill_ids)
    return AnalysisReport(
        asset=bundle.asset,
        as_of=bundle.as_of,
        results=results,
        markdown=render_report(bundle, results),
        html=render_report_html(bundle, results),
    )
