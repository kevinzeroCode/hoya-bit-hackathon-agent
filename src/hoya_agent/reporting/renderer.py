"""Deterministic Traditional Chinese report renderer.

The renderer is a pure function of `AnalysisResult` plus the Evidence Ledger. It
never calls an LLM, never reaches the network, and never states a fact that is
absent from its two inputs. The 11 fixed sections come from `docs/Features.md`
§3; Requirement 17 adds a twelfth section only for a two-asset run.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from hoya_agent.models import (
    AnalysisResult,
    Asset,
    ClaimType,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunMode,
    Stance,
)

LintHook = Callable[[str], Sequence[str]]

REPORT_SECTION_TITLES: tuple[str, ...] = (
    "直接回答",
    "市場狀況與時間範圍",
    "已確認事實",
    "主要支持證據",
    "主要反方或矛盾證據",
    "推論",
    "結論",
    "信心與原因",
    "限制與資料缺口",
    "失效條件（Invalidation Conditions）",
    "後續觀察重點",
)

INSUFFICIENT_DATA_HEADLINE = "目前無法可靠判定"

_RUN_MODE_LABELS: dict[RunMode, str] = {
    RunMode.official: "official（live 來源）",
    # rehearsal permits deterministic fixtures *or* replayable real data with a
    # supplied cutoff, so the label must not assert which one was used.
    RunMode.rehearsal: "rehearsal（可重現資料與自訂 cutoff，非 live official 結果）",
    RunMode.demo: "demo（展示資料，非即時分析）",
}

_STANCE_LABELS: dict[Stance, str] = {
    Stance.supports: "supports（支持）",
    Stance.opposes: "opposes（反對）",
    Stance.neutral: "neutral（背景）",
}

_NONE = "—"


def render(
    result: AnalysisResult,
    ledger: EvidenceLedger,
    *,
    lint: LintHook | None = None,
) -> str:
    """Render the fixed 11-section Traditional Chinese report.

    `lint` is the prohibited-advice string check. It always runs last, on the
    finished text, and any violation aborts the render rather than shipping a
    report containing prescriptive investment language.
    """
    items_by_id = {item.evidence_id: item for item in ledger.items}
    lines: list[str] = []
    lines += _render_header(result, ledger)
    lines += _section(1, _render_direct_answer(result))
    lines += _section(2, _render_market_context(result))
    lines += _section(3, _render_claim_layer(result, ClaimType.fact, "事實"))
    lines += _section(4, _render_supporting_evidence(result, ledger, items_by_id))
    lines += _section(5, _render_counter_evidence(result, ledger, items_by_id))
    lines += _section(6, _render_claim_layer(result, ClaimType.inference, "推論"))
    lines += _section(7, _render_claim_layer(result, ClaimType.conclusion, "結論"))
    lines += _section(8, _render_confidence(result))
    lines += _section(9, _render_limitations(result, ledger))
    lines += _section(10, _render_invalidation(result))
    lines += _section(11, _render_watch_items(result))
    if len(result.assets) == 2:
        lines += ["", "## 12. 跨幣比較", "", *_render_comparison(result, ledger)]

    report = "\n".join(lines).rstrip() + "\n"

    if lint is not None:
        violations = list(lint(report))
        if violations:
            raise ValueError("report failed prohibited-advice lint: " + "; ".join(violations))
    return report


def build_insufficient_data_result(
    *,
    run_id: str,
    question: str,
    assets: list[Asset],
    analysis_as_of: datetime,
    reason: str,
) -> AnalysisResult:
    """Build the deterministic insufficient-data result used when analysis is missing.

    This keeps a single rendering path: the fallback report is the normal report
    of an explicitly insufficient result, so it cannot silently look complete.
    """
    reason_text = reason.strip().rstrip("。.")
    return AnalysisResult(
        run_id=run_id,
        question=question,
        assets=assets,
        analysis_as_of=analysis_as_of,
        direct_answer=(
            f"{INSUFFICIENT_DATA_HEADLINE}。原因：{reason_text}。"
            "本次 run 未取得經驗證的分析結果，以下僅呈現已取得的證據與資料缺口。"
        ),
        market_context=None,
        claims=[],
        claim_evidence_links=[],
        confidence=Reliability.low,
        confidence_rationale=(
            "資料或分析不足，整體信心標示為 low，且不升級。"
        ),
        limitations=[
            f"分析未完成：{reason_text}。",
            "本報告為資料不足結果，不含經驗證的推論或結論。",
        ],
        invalidation_conditions=[],
        watch_items=[],
        insufficient_data=True,
        degradation_notes=[f"分析階段未產出可驗證結果：{reason_text}。"],
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _render_header(result: AnalysisResult, ledger: EvidenceLedger) -> list[str]:
    return [
        "# HOYA 市場分析報告",
        "",
        "| 項目 | 內容 |",
        "|---|---|",
        f"| Run ID | `{result.run_id}` |",
        f"| 執行模式 | {_RUN_MODE_LABELS[ledger.run_mode]} |",
        f"| 分析基準時間 `analysis_as_of` | {_iso(result.analysis_as_of)} |",
        f"| 分析資產 | {_assets(result.assets)} |",
        f"| 分析問題 | {result.question} |",
        f"| 整體信心 | {result.confidence.value} |",
        f"| 資料是否不足 | {'是' if result.insufficient_data else '否'} |",
        "",
        "> 本報告依已驗證資料與來源紀錄產生，"
        "不含任何模型自行補寫的數值，也不提供投資建議。",
    ]


def _render_direct_answer(result: AnalysisResult) -> list[str]:
    return [result.direct_answer]


def _render_market_context(result: AnalysisResult) -> list[str]:
    context = result.market_context
    if context is None:
        lines = ["本次 run 未取得可驗證的市場範圍描述，因此不呈現市場狀況摘要。"]
    else:
        lines = [
            context.summary,
            "",
            f"- 分析時間範圍：{context.time_range.start} ~ {context.time_range.end}（UTC 日界）",
            f"- 分析基準時間：{_iso(result.analysis_as_of)}",
        ]
    if result.market_regime is not None:
        regime = result.market_regime
        lines += [
            "",
            "**Market Regime（依資料判定）**",
            f"- {regime.asset.value}: `{regime.label.value}`（截至 {regime.as_of}，"
            f"window={regime.window_days} 日，Evidence `{regime.evidence_id or _NONE}`）",
        ]
    return lines


def _render_claim_layer(result: AnalysisResult, claim_type: ClaimType, label: str) -> list[str]:
    claims = [claim for claim in result.claims if claim.claim_type is claim_type]
    if not claims:
        return [f"本次 run 未產出可驗證的{label}層 claim。"]

    lines: list[str] = []
    for claim in claims:
        supporting = _evidence_ids(result, claim.claim_id, Stance.supports)
        opposing = _evidence_ids(result, claim.claim_id, Stance.opposes)
        depends = "、".join(f"`{cid}`" for cid in claim.based_on_claim_ids) or _NONE
        lines.append(f"- **`{claim.claim_id}`**（confidence：{claim.confidence.value}）{claim.text}")
        lines.append(
            f"  - 時間範圍：{claim.time_range.start} ~ {claim.time_range.end}"
            f"｜資產：{_assets(claim.assets)}"
        )
        lines.append(f"  - 支持證據：{_ids(supporting)}｜反方證據：{_ids(opposing)}｜依據 claim：{depends}")
        for limitation in claim.limitations:
            lines.append(f"  - 限制：{limitation}")
        for condition in claim.invalidation_conditions:
            lines.append(f"  - 失效條件：{condition}")
    return lines


def _render_supporting_evidence(
    result: AnalysisResult,
    ledger: EvidenceLedger,
    items_by_id: dict[str, EvidenceItem],
) -> list[str]:
    if not ledger.items:
        return ["本次 run 未取得任何可用證據，Evidence Ledger 為空並已記錄原因。"]

    supporting_ids = {
        link.evidence_id
        for link in result.claim_evidence_links
        if link.stance is Stance.supports and link.evidence_id in items_by_id
    }
    lines = _evidence_table([items_by_id[eid] for eid in sorted(supporting_ids)], result)
    if not supporting_ids:
        lines = ["尚無任何證據被連結為支持某個 claim。"]

    remaining = [item for item in ledger.items if item.evidence_id not in supporting_ids]
    if remaining:
        lines.append("")
        lines.append("**其他已取得證據（未列為支持證據，仍完整保留可追溯性）**")
        lines.append("")
        lines += _evidence_table(remaining, result)
    return lines


def _render_counter_evidence(
    result: AnalysisResult,
    ledger: EvidenceLedger,
    items_by_id: dict[str, EvidenceItem],
) -> list[str]:
    opposing_links = [
        link for link in result.claim_evidence_links if link.stance is Stance.opposes
    ]
    lines: list[str] = []
    if opposing_links:
        for link in opposing_links:
            item = items_by_id.get(link.evidence_id)
            source = (
                f"{item.source_name}（{item.independence_group}，reliability {item.reliability.value}）"
                if item is not None
                else "來源不在 Ledger 中"
            )
            lines.append(
                f"- claim `{link.claim_id}` ← 反方證據 `{link.evidence_id}`：{source}"
            )
            lines.append(f"  - 關聯理由：{link.reason}")
            if item is not None:
                lines.append(f"  - 內容：{item.normalized_fact}")
    else:
        searched = "、".join(sorted({item.source_name for item in ledger.items})) or _NONE
        lines.append(
            "未找到 reliability 至少 medium 的可信反方訊號。"
            "此為本次 run 的限制，並未以任何方式補寫反方敘事。"
        )
        lines.append(f"- 已查詢來源：{searched}")

    if ledger.conflict_indicators:
        lines.append("")
        lines.append("**material conflict（雙方證據皆保留，受影響 claim 的 confidence 已受上限約束）**")
        lines.append("")
        for indicator in ledger.conflict_indicators:
            lines.append(
                f"- claim `{indicator.claim_id}`：支持 {_ids(indicator.supporting_evidence_ids)}"
                f"｜反對 {_ids(indicator.opposing_evidence_ids)}"
            )
            groups = "、".join(indicator.independence_groups) or _NONE
            lines.append(f"  - 獨立上游：{groups}｜規則版本：{indicator.rule_version}")
    else:
        lines.append("")
        lines.append("本次 run 未偵測到符合判定條件的 material conflict（矛盾）。")
    return lines


def _render_confidence(result: AnalysisResult) -> list[str]:
    lines = [
        f"整體信心：**{result.confidence.value}**（僅使用 high / medium / low 三級序數標籤，"
        "不代表任何已校準的預測數值）",
        "",
        result.confidence_rationale,
    ]
    if result.claims:
        lines.append("")
        lines.append("各層 claim 的信心：")
        for claim in result.claims:
            lines.append(
                f"- `{claim.claim_id}`（{claim.claim_type.value}）：{claim.confidence.value}"
            )
    if result.trust_scorecards:
        lines += ["", "**Trust Scorecard（ordinal，不是機率）**", ""]
        for card in result.trust_scorecards:
            mix = card.reliability_mix
            fresh_age = card.freshness.newest_evidence_age_hours
            age = _NONE if fresh_age is None else f"{fresh_age:.1f}h"
            lines.append(
                f"- `{card.claim_id}`：獨立性 {card.source_independence.level.value} "
                f"({card.source_independence.distinct_groups})｜來源多樣性 "
                f"{card.source_diversity.level.value} ({card.source_diversity.distinct_source_types})｜"
                f"一致性 {card.consistency.level.value}｜新鮮度 {card.freshness.level.value} ({age})"
            )
            lines.append(
                f"  - reliability mix: high={mix.high}, medium={mix.medium}, low={mix.low}；"
                f"{card.rationale}"
            )
    return lines


def _render_comparison(result: AnalysisResult, ledger: EvidenceLedger) -> list[str]:
    left, right = result.assets
    comparison = [
        item
        for item in ledger.items
        if left.value in item.normalized_fact
        and right.value in item.normalized_fact
        and "compare " in item.query_or_parameters
    ]
    claims = [claim for claim in result.claims if set(claim.assets) == {left, right}]
    if not comparison:
        return [
            f"{left.value}/{right.value} 比較 unavailable：缺少同一 UTC 日期對齊的可驗證市場證據；"
            "未使用 forward-fill，也未比較不同幣的 base volume。"
        ]
    lines = [
        f"本段在單一 run、單一 cutoff、同一份 Ledger 中比較 {left.value} 與 {right.value}；"
        "不比較跨幣 base volume。",
        "",
    ]
    regimes = [
        item
        for item in ledger.items
        if item.asset in {left, right} and item.content_reference.startswith("market regime")
    ]
    if regimes:
        lines.append("**各資產 Market Regime（不合併為單一標籤）**")
        for item in regimes:
            lines.append(f"- {item.asset.value}: `{item.evidence_id}` {item.normalized_fact}")
        lines.append("")
    for item in comparison:
        lines.append(f"- `{item.evidence_id}`：{item.normalized_fact}")
    for claim in claims:
        lines.append(f"- 比較型 Claim `{claim.claim_id}`：{claim.text}")
    return lines


def _render_limitations(result: AnalysisResult, ledger: EvidenceLedger) -> list[str]:
    lines: list[str] = []
    if result.limitations:
        for limitation in result.limitations:
            lines.append(f"- {limitation}")
    else:
        lines.append("- 本次 run 未記錄額外限制。")

    if result.degradation_notes:
        lines.append("")
        lines.append("**降級說明**")
        lines.append("")
        for note in result.degradation_notes:
            lines.append(f"- {note}")

    if ledger.degradation_events:
        lines.append("")
        lines.append("**Evidence Ledger 降級事件**")
        lines.append("")
        for event in ledger.degradation_events:
            lines.append(
                f"- [{_iso(event.timestamp)}] {event.stage} / {event.event_type}"
                f"（{event.source}）：{event.message}"
            )

    stale = [item.evidence_id for item in ledger.items if item.is_stale]
    cached = [item.evidence_id for item in ledger.items if item.is_cached]
    if cached:
        lines.append("")
        lines.append(f"- 使用 cache 的證據：{_ids(cached)}（cache 時間已列於證據表）")
    if stale:
        lines.append(f"- 標記為 stale 的證據：{_ids(stale)}")
    return lines


def _render_invalidation(result: AnalysisResult) -> list[str]:
    if not result.invalidation_conditions:
        return ["本次 run 未產出可驗證的失效條件。"]
    lines: list[str] = []
    for condition in result.invalidation_conditions:
        lines.append(f"- {condition.text}")
        if condition.metric is not None:
            operator = condition.operator.value if condition.operator is not None else _NONE
            lines.append(
                f"  - 量化門檻：`{condition.metric}` {operator} {condition.threshold}"
                f"｜依據證據：`{condition.basis_evidence_id}`"
            )
        else:
            lines.append("  - 量化門檻：不適用（本條為質性失效條件）")
    return lines


def _render_watch_items(result: AnalysisResult) -> list[str]:
    if not result.watch_items:
        return ["本次 run 未產出後續觀察重點。"]
    return [f"- {item}" for item in result.watch_items]


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------


def _section(index: int, body: list[str]) -> list[str]:
    return ["", f"## {index}. {REPORT_SECTION_TITLES[index - 1]}", "", *body]


def _evidence_table(items: list[EvidenceItem], result: AnalysisResult) -> list[str]:
    lines = [
        "| Evidence ID | 資產 | 來源類型 | 來源 | reliability | 獨立上游 | 取得時間 (UTC) | 內容 | 關聯 claim |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in items:
        related = "、".join(
            f"`{link.claim_id}`({link.stance.value})"
            for link in result.claim_evidence_links
            if link.evidence_id == item.evidence_id
        )
        source = item.source_name
        if item.source_url:
            source = f"[{item.source_name}]({item.source_url})"
        cache = ""
        if item.is_cached and item.cache_time is not None:
            cache = f"（cache 時間 {_iso(item.cache_time)}{'，stale' if item.is_stale else ''}）"
        lines.append(
            f"| `{item.evidence_id}` | {item.asset.value if item.asset else '全市場'} "
            f"| {item.source_type.value} | {source} | {item.reliability.value} "
            f"| {item.independence_group} | {_iso(item.fetched_at)}{cache} "
            f"| {item.normalized_fact} | {related or _NONE} |"
        )
    return lines


def _evidence_ids(result: AnalysisResult, claim_id: str, stance: Stance) -> list[str]:
    return [
        link.evidence_id
        for link in result.claim_evidence_links
        if link.claim_id == claim_id and link.stance is stance
    ]


def _ids(ids: Sequence[str]) -> str:
    return "、".join(f"`{i}`" for i in ids) if ids else _NONE


def _assets(assets: Sequence[Asset]) -> str:
    return "、".join(asset.value for asset in assets)


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
