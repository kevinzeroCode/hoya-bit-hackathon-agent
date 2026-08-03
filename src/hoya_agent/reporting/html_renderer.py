
# ruff: noqa: E501
"""Self-contained, deterministic HTML report in the P4 editorial style.

The renderer accepts only validated domain objects, performs no I/O, and escapes
every dynamic value.  It deliberately contains no remote fonts, scripts, images,
analytics, or model-generated markup, so the artifact remains portable offline.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import datetime
from html import escape
from urllib.parse import urlsplit

from hoya_agent.models import (
    AnalysisResult,
    Claim,
    EvidenceLedger,
    Reliability,
    RunMode,
    Stance,
    TrustLevel,
    TrustScorecard,
)

LintHook = Callable[[str], Sequence[str]]

_MODE_LABELS = {
    RunMode.official: "OFFICIAL · LIVE",
    RunMode.rehearsal: "REHEARSAL · REPLAY",
    RunMode.demo: "DEMO · FALLBACK POSSIBLE",
}
_LEVEL_PIPS = {
    TrustLevel.strong: 3,
    TrustLevel.moderate: 2,
    TrustLevel.weak: 1,
    TrustLevel.unavailable: 0,
}


def render_html(
    result: AnalysisResult,
    ledger: EvidenceLedger,
    *,
    terminal_state: str = "completed",
    prompt_version: str = "v1",
    policy_version: str = "1.0",
    lint: LintHook | None = None,
) -> str:
    """Render the complete, standalone Traditional Chinese HTML report."""
    links_by_claim = {
        claim.claim_id: [link for link in result.claim_evidence_links if link.claim_id == claim.claim_id]
        for claim in result.claims
    }
    support = [link for link in result.claim_evidence_links if link.stance is Stance.supports]
    oppose = [link for link in result.claim_evidence_links if link.stance is Stance.opposes]
    groups = {item.independence_group for item in ledger.items}
    source_types = {item.source_type.value for item in ledger.items}
    high = sum(item.reliability is Reliability.high for item in ledger.items)
    medium = sum(item.reliability is Reliability.medium for item in ledger.items)
    stale = sum(item.is_stale for item in ledger.items)
    regime = result.market_regime.label.value if result.market_regime else "unavailable"
    status_class = "ok" if terminal_state == "completed" else "warn"
    disclosure = _disclosure(result, ledger)

    document = f"""<!doctype html>
<html lang="zh-Hant" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>HOYA Market Agent｜{_e(result.question)}</title>
<style>{_CSS}</style>
</head>
<body><div class="shell">
<nav class="toolbar" aria-label="報告工具"><div class="brand"><span class="mark">H</span><span>HOYA MARKET AGENT</span></div><div class="tools"><button class="tool" id="theme" type="button">深色</button><button class="tool" id="print" type="button">列印／PDF</button></div></nav>
<header class="hero"><div class="hero-grid"><div><p class="eyebrow">多源資訊的信任提煉</p><h1>{_e(result.question)}</h1><p class="standfirst">{_e(result.direct_answer)}</p></div>
<aside class="status"><div class="row"><span class="chip {status_class}">{_e(_MODE_LABELS[ledger.run_mode])}</span><span class="runid">{_e(result.run_id)}</span></div><p class="verdict">{_e(result.confidence.value.upper())} confidence</p><p class="reason">{_e(result.confidence_rationale)}</p><dl class="meta"><div><dt>分析截點</dt><dd>{_iso(result.analysis_as_of)}</dd></div><div><dt>執行狀態</dt><dd>{_e(terminal_state)}</dd></div><div><dt>分析資產</dt><dd>{_e(' · '.join(a.value for a in result.assets))}</dd></div></dl></aside></div>
<div class="notice" role="note"><b>資料說明</b><span>{_e(disclosure)}</span></div>
<div class="stats"><article class="stat"><small>市場狀態</small><strong>{_e(regime)}</strong><p>依市場資料判定；無資料時明確標示。</p></article><article class="stat"><small>結論信心</small><strong>{_e(result.confidence.value)}</strong><p>{len(support)} 個支持證據 · {len(oppose)} 個反方證據</p></article><article class="stat"><small>證據筆數</small><strong>{len(ledger.items)}</strong><p>去重後保留的可追溯資料。</p></article><article class="stat"><small>來源多樣性</small><strong>{len(source_types)} 類</strong><p>{len(groups)} 個獨立來源群組</p></article></div></header>
<main><aside class="toc"><b>報告導覽</b><a href="#answer">01 直接回答</a><a href="#market">02 市場狀況</a><a href="#reasoning">03 推理鏈</a><a href="#evidence">04 正反證據</a><a href="#trust">05 信任評分</a><a href="#limits">06 限制與推翻條件</a><a href="#watch">07 後續觀察</a><a href="#ledger">08 證據明細</a><a href="#reproduce">09 資料與檔案</a></aside><div class="content">
{_section('answer', '01 · 直接回答', '先回答題目，再展示推理', '<div class="answer"><p>'+_e(result.direct_answer)+'</p><div class="answer-foot"><span>信心 · '+_e(result.confidence.value.upper())+'</span><span>支持 · '+str(len(support))+'</span><span>反方 · '+str(len(oppose))+'</span></div></div>')}
{_market_section(result)}
{_reasoning_section(result.claims, links_by_claim)}
{_evidence_section(ledger, result)}
{_trust_section(result, ledger, high, medium, stale)}
{_limits_section(result, ledger)}
{_watch_section(result)}
{_ledger_section(ledger, result)}
{_reproducibility_section(result, ledger, terminal_state, prompt_version, policy_version)}
</div></main>
<footer><div class="foot"><p><strong>重要聲明：</strong>本報告僅供研究與市場資訊理解，不提供交易操作或個人化投資指引。所有結論只適用於本次 immutable run 與標示的分析截點。</p><p class="footmark">HOYA MARKET AGENT<br>TRACEABLE BY DESIGN</p></div></footer>
</div><script>'use strict';const r=document.documentElement,t=document.getElementById('theme');t.addEventListener('click',()=>{{const n=r.dataset.theme==='dark'?'light':'dark';r.dataset.theme=n;t.textContent=n==='dark'?'淺色':'深色'}});document.getElementById('print').addEventListener('click',()=>window.print());</script></body></html>
"""
    if lint is not None:
        violations = list(lint(document))
        if violations:
            raise ValueError("HTML report failed prohibited-advice lint: " + "; ".join(violations))
    return document


def _market_section(result: AnalysisResult) -> str:
    if result.market_context:
        context = (
            f"<p class=\"lead\">{_e(result.market_context.summary)}</p>"
            f"<div class=\"panel\"><b>時間範圍</b><p>{_e(result.market_context.time_range.start)} — "
            f"{_e(result.market_context.time_range.end)} · UTC 日界</p></div>"
        )
    else:
        context = '<p class="empty">本次 run 未取得可驗證的市場範圍描述。</p>'
    if result.market_regime:
        r = result.market_regime
        context += (
            f'<div class="panel"><b>Market Regime · {_e(r.label.value)}</b>'
            f'<p>{_e(r.asset.value)} · {r.window_days} 日視窗 · Evidence '
            f'<span class="cite">{_e(r.evidence_id or "unavailable")}</span></p></div>'
        )
    return _section("market", "02 · 市場狀況", "市場狀況與時間範圍", context)


def _reasoning_section(claims: list[Claim], links_by_claim: dict[str, list]) -> str:
    cards: list[str] = []
    for claim in claims:
        refs = "".join(
            f'<span class="tag">{_e(link.evidence_id)} · {_e(link.stance.value)}</span>'
            for link in links_by_claim.get(claim.claim_id, [])
        )
        deps = "".join(f'<span class="tag">BASED ON {_e(cid)}</span>' for cid in claim.based_on_claim_ids)
        cards.append(
            f'<article class="claim"><div class="ctype">{_e(claim.claim_type.value)} · {_e(claim.claim_id)}</div>'
            f'<p>{_e(claim.text)}</p><div class="tags">{deps}{refs}</div></article>'
        )
    body = '<div class="chain">' + "".join(cards) + "</div>" if cards else '<p class="empty">本次 run 沒有經驗證的 claim；不得補寫推論。</p>'
    return _section("reasoning", "03 · 推理脈絡", "事實 → 推論 → 結論", body)


def _evidence_section(ledger: EvidenceLedger, result: AnalysisResult) -> str:
    by_id = {item.evidence_id: item for item in ledger.items}
    supporting: list[str] = []
    opposing: list[str] = []
    for link in result.claim_evidence_links:
        item = by_id.get(link.evidence_id)
        if item is None:
            continue
        row = f'<li>{_e(item.normalized_fact)} <span class="cite">{_e(item.evidence_id)}</span><small>{_e(link.reason)}</small></li>'
        (supporting if link.stance is Stance.supports else opposing if link.stance is Stance.opposes else []).append(row)
    def card(kind: str, title: str, rows: list[str]) -> str:
        content = "".join(rows) or '<li class="empty">沒有對應證據。</li>'
        return f'<article class="ecard {kind}"><p>{title} · {len(rows)}</p><ul>{content}</ul></article>'
    body = '<div class="egrid">' + card("support", "支持訊號", supporting) + card("oppose", "反方／矛盾訊號", opposing) + "</div>"
    return _section("evidence", "04 · 證據比較", "支持與反方證據並列", body)


def _trust_section(result: AnalysisResult, ledger: EvidenceLedger, high: int, medium: int, stale: int) -> str:
    if result.trust_scorecards:
        blocks = []
        for card in result.trust_scorecards:
            values = [
                ("獨立性", card.source_independence.level, f"{card.source_independence.distinct_groups} 個獨立來源群組"),
                ("來源多樣性", card.source_diversity.level, f"{card.source_diversity.distinct_source_types} 類來源"),
                ("可信度組成", _mix_level(card.reliability_mix.high, card.reliability_mix.medium), f"high {card.reliability_mix.high} · medium {card.reliability_mix.medium} · low {card.reliability_mix.low}"),
                ("一致性", card.consistency.level, f"{card.consistency.opposing_count} 個反方訊號"),
                ("時效性", card.freshness.level, "含較舊資料" if card.freshness.has_stale else "資料具時效性"),
            ]
            cards = "".join(_score_card(*value) for value in values)
            radar = _trust_radar_svg(card)
            blocks.append(
                f'<div class="scorecard-block"><h3>結論 <code>{_e(card.claim_id)}</code></h3>'
                f'<div class="scorecard-row">{radar}<div class="scores">{cards}</div></div></div>'
            )
        body = "".join(blocks)
    else:
        values = [
            ("獨立性", TrustLevel.unavailable, "沒有 conclusion scorecard"),
            ("來源多樣性", TrustLevel.unavailable, f"Ledger 有 {len({i.source_type for i in ledger.items})} 類來源"),
            ("可信度組成", _mix_level(high, medium), f"high {high} · medium {medium}"),
            ("一致性", TrustLevel.unavailable, f"{len(ledger.conflict_indicators)} 個矛盾訊號"),
            ("時效性", TrustLevel.unavailable, f"{stale} 筆較舊資料"),
        ]
        cards = "".join(_score_card(*value) for value in values)
        body = f'<div class="scores">{cards}</div>'
    return _section("trust", "05 · 信任評分", "不用假精確百分比，直接說可信在哪裡", body)


def _limits_section(result: AnalysisResult, ledger: EvidenceLedger) -> str:
    limitations = [*result.limitations, *result.degradation_notes]
    limitations.extend(event.message for event in ledger.degradation_events)
    left = _numbered_list(limitations, "本次 run 沒有額外限制紀錄。")
    conditions = []
    for condition in result.invalidation_conditions:
        detail = condition.text
        if condition.metric is not None:
            detail += f"（{condition.metric} {condition.operator.value} {condition.threshold} · {condition.basis_evidence_id}）"
        conditions.append(detail)
    right = _numbered_list(conditions, "本次 run 沒有經 Evidence 支持的量化推翻條件。")
    body = f'<div class="split"><article class="panel"><h3>已知限制與降級</h3>{left}</article><article class="panel"><h3>推翻條件</h3>{right}</article></div>'
    return _section("limits", "06 · 限制與推翻條件", "主動揭露資料缺口，以及什麼會推翻結論", body)


def _watch_section(result: AnalysisResult) -> str:
    return _section("watch", "07 · 後續觀察", "後續觀察重點", f'<div class="panel">{_numbered_list(result.watch_items, "目前沒有可驗證的後續觀察項目。")}</div>')


def _ledger_section(ledger: EvidenceLedger, result: AnalysisResult) -> str:
    related: dict[str, list[str]] = {}
    for link in result.claim_evidence_links:
        related.setdefault(link.evidence_id, []).append(f"{link.claim_id} · {link.stance.value}")
    rows = []
    for item in ledger.items:
        name = _e(item.source_name)
        url = _safe_url(item.source_url)
        source = f'<a href="{url}" target="_blank" rel="noreferrer">{name}</a>' if url else name
        rows.append(
            f'<tr><td>{_e(item.evidence_id)}</td><td>{source}</td><td>{_iso(item.fetched_at)}</td>'
            f'<td>{_e(item.content_reference)}</td><td>{_e(" · ".join(related.get(item.evidence_id, [])) or "—")}</td>'
            f'<td class="{_e(item.reliability.value)}">{_e(item.reliability.value)}</td></tr>'
        )
    body = "".join(rows) or '<tr><td colspan="6">Ledger 為空；原因見限制與降級。</td></tr>'
    table = f'<details open><summary>檢視 Evidence List · {len(ledger.items)} 筆</summary><div class="tablewrap"><table><thead><tr><th>ID</th><th>來源</th><th>取得時間</th><th>內容參照</th><th>關聯主張</th><th>可信度</th></tr></thead><tbody>{body}</tbody></table></div></details>'
    return _section("ledger", "08 · 證據明細", "每個關鍵結論都可回溯", table)


def _reproducibility_section(result: AnalysisResult, ledger: EvidenceLedger, terminal_state: str, prompt_version: str, policy_version: str) -> str:
    body = f'<div class="panel"><div class="panel-head"><div><h3>資料與檔案</h3><p>本次分析的來源、證據與執行紀錄均保留，可供查閱。</p></div><span class="chip warn">{_e(terminal_state)}</span></div><dl class="meta"><div><dt>分析截點</dt><dd>{_iso(result.analysis_as_of)}</dd></div><div><dt>分析資產</dt><dd>{_e(" · ".join(a.value for a in result.assets))}</dd></div><div><dt>證據筆數</dt><dd>{len(ledger.items)}</dd></div><div><dt>來源群組</dt><dd>{len({item.independence_group for item in ledger.items})}</dd></div></dl></div><div class="downloads"><a class="download" href="final_report.md"><b>FINAL_REPORT.MD</b><small>文字版報告</small></a><a class="download" href="evidence.json"><b>EVIDENCE.JSON</b><small>完整證據</small></a><a class="download" href="execution_log.jsonl"><b>EXECUTION LOG</b><small>執行紀錄</small></a><a class="download" href="run_config.json"><b>RUN CONFIG</b><small>分析設定</small></a></div>'
    return _section("reproduce", "09 · 資料與檔案", "保留完整來源與分析紀錄", body)


def _section(section_id: str, kicker: str, title: str, body: str) -> str:
    return f'<section id="{section_id}"><span class="kicker">{kicker}</span><h2>{title}</h2>{body}</section>'


_RADAR_AXES = ("獨立性", "多樣性", "可信度", "一致性", "時效性")


def _radar_point(cx: float, cy: float, radius: float, index: int, total: int) -> tuple[float, float]:
    angle = -math.pi / 2 + (2 * math.pi * index / total)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _trust_radar_svg(card: TrustScorecard) -> str:
    """Deterministic inline SVG radar chart for one conclusion's Trust Scorecard
    (Task 20 additional visualization). No new data source: every point plotted
    is already a field on `card`, mapped through the same 0-3 ordinal pip scale
    `_score_card` already uses — never a synthetic single percentage.
    """
    levels = [
        card.source_independence.level,
        card.source_diversity.level,
        _mix_level(card.reliability_mix.high, card.reliability_mix.medium),
        card.consistency.level,
        card.freshness.level,
    ]
    cx, cy, max_r = 120.0, 115.0, 62.0
    n = len(_RADAR_AXES)

    grid = "".join(
        '<polygon points="'
        + " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in (_radar_point(cx, cy, max_r * ring / 3, i, n) for i in range(n))
        )
        + '" fill="none" stroke="#d8d8cf" stroke-width="1"/>'
        for ring in (1, 2, 3)
    )
    axes = "".join(
        f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
        f'stroke="#d8d8cf" stroke-width="1"/>'
        for x, y in (_radar_point(cx, cy, max_r, i, n) for i in range(n))
    )
    labels = "".join(
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="10" fill="#4e544e" text-anchor="middle">'
        f"{escape(axis)}</text>"
        for axis, (x, y) in zip(
            _RADAR_AXES, (_radar_point(cx, cy, max_r + 20, i, n) for i in range(n)), strict=True
        )
    )
    data_points = [
        _radar_point(cx, cy, max_r * _LEVEL_PIPS[level] / 3, i, n) for i, level in enumerate(levels)
    ]
    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_points)
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="#087f5b"/>' for x, y in data_points)
    return (
        '<svg viewBox="0 0 240 240" width="200" height="200" role="img" '
        f'aria-label="Trust Scorecard radar for {escape(card.claim_id)}">'
        f"{grid}{axes}"
        f'<polygon points="{polygon}" fill="#087f5b" fill-opacity="0.22" '
        f'stroke="#087f5b" stroke-width="2"/>'
        f"{dots}{labels}"
        "</svg>"
    )


def _score_card(label: str, level: TrustLevel, detail: str) -> str:
    pips = "".join(f'<i class="pip{" on" if i < _LEVEL_PIPS[level] else ""}"></i>' for i in range(3))
    return f'<article class="score"><small>{_e(label)}</small><strong>{_e(level.value)}</strong><p>{_e(detail)}</p><div class="pips">{pips}</div></article>'


def _mix_level(high: int, medium: int) -> TrustLevel:
    if high >= 2:
        return TrustLevel.strong
    if high + medium >= 2:
        return TrustLevel.moderate
    if high + medium == 1:
        return TrustLevel.weak
    return TrustLevel.unavailable


def _numbered_list(items: Sequence[str], empty: str) -> str:
    values = list(items) or [empty]
    return '<ol class="clean">' + "".join(f'<li><span class="idx">{i:02d}</span><p>{_e(value)}</p></li>' for i, value in enumerate(values, 1)) + "</ol>"


def _disclosure(result: AnalysisResult, ledger: EvidenceLedger) -> str:
    if ledger.run_mode is RunMode.official:
        base = "本頁內容來自本次即時資料分析。"
    elif ledger.run_mode is RunMode.rehearsal:
        base = "本頁為 rehearsal 可重現資料結果，不得標示為 live official。"
    else:
        base = "本頁為展示資料結果，不代表即時分析。"
    if result.insufficient_data:
        base += " 分析結果標記為資料不足；頁面不補寫方向性結論。"
    return base


def _safe_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    return escape(value, quote=True) if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _iso(value: datetime) -> str:
    return _e(value.strftime("%Y-%m-%dT%H:%M:%SZ"))


_CSS = r"""
:root{color-scheme:light;--page:#f5f4ef;--paper:#fffefa;--ink:#151815;--ink2:#4e544e;--muted:#767d75;--line:#d8d8cf;--green:#087f5b;--green2:#dff3ea;--amber:#a55f00;--amber2:#fff0cf;--red:#b23a32;--red2:#fbe6e3;--blue:#2867b2;--blue2:#e2edf9;--mono:ui-monospace,"Cascadia Mono",Consolas,monospace;--sans:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;--serif:"Noto Serif TC","Source Han Serif TC",Georgia,serif;--shadow:0 14px 40px rgba(22,25,22,.07)}
:root[data-theme="dark"]{color-scheme:dark;--page:#101310;--paper:#171b17;--ink:#f3f5ef;--ink2:#c4c9c1;--muted:#969d94;--line:#353b35;--green:#5ed4a3;--green2:#173b2e;--amber:#f3bc5b;--amber2:#493514;--red:#ff8a80;--red2:#48221f;--blue:#84b7ee;--blue2:#1d3550;--shadow:0 14px 40px rgba(0,0,0,.28)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 78% -10%,rgba(8,127,91,.12),transparent 36rem),var(--page);color:var(--ink);font:16px/1.68 var(--sans);-webkit-font-smoothing:antialiased}a{color:var(--blue);text-underline-offset:3px}a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid var(--blue);outline-offset:3px}.shell{max-width:1160px;margin:auto;padding:0 28px 90px}.toolbar{min-height:64px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);font:12px var(--mono)}.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.08em}.mark{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--ink);color:var(--paper);font:700 15px var(--serif)}.tools{display:flex;gap:8px}.tool{padding:7px 12px;border:1px solid var(--line);border-radius:999px;background:var(--paper);color:var(--ink2);cursor:pointer}.hero{padding:70px 0 44px;border-bottom:1px solid var(--line)}.hero-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(270px,.7fr);gap:54px}.eyebrow,.kicker{color:var(--green);font:700 11px var(--mono);letter-spacing:.1em;text-transform:uppercase}h1{margin:0 0 20px;font:650 clamp(38px,5.7vw,66px)/1.08 var(--serif);letter-spacing:-.03em}h2{max-width:27ch;margin:0 0 18px;font:650 clamp(28px,4vw,42px)/1.15 var(--serif)}h3{margin:0 0 8px}.standfirst,.lead{color:var(--ink2);font-size:18px}.status,.panel,.ecard,.score,.answer,details{background:var(--paper);border:1px solid var(--line);border-radius:14px}.status{align-self:end;padding:24px;box-shadow:var(--shadow)}.row,.panel-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.chip{padding:5px 10px;border-radius:999px;font:700 11px var(--mono);letter-spacing:.06em}.chip.ok{color:var(--green);background:var(--green2)}.chip.warn{color:var(--amber);background:var(--amber2)}.runid{color:var(--muted);font:11px var(--mono)}.verdict{margin:24px 0 5px;font:28px/1.25 var(--serif)}.reason{margin:0;color:var(--ink2);font-size:14px}.meta{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px}.meta dt{color:var(--muted);font:10px var(--mono);text-transform:uppercase}.meta dd{margin:2px 0;font-size:13px;font-weight:650}.notice{display:grid;grid-template-columns:auto 1fr;gap:14px;margin-top:28px;padding:15px 18px;border:1px solid var(--line);border-radius:12px;background:var(--amber2);font-size:14px}.notice b{font:700 11px var(--mono)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin-top:34px;overflow:hidden;border:1px solid var(--line);border-radius:14px;background:var(--line)}.stat{min-height:145px;padding:22px;background:var(--paper)}.stat small,.score small{color:var(--muted);font:10px var(--mono);text-transform:uppercase}.stat strong{display:block;margin-top:15px;font:31px var(--serif)}.stat p,.score p{color:var(--ink2);font-size:13px}main{display:grid;grid-template-columns:185px minmax(0,1fr);gap:58px}.toc{position:sticky;top:22px;align-self:start;padding-top:58px}.toc b{display:block;margin-bottom:13px;color:var(--muted);font:10px var(--mono)}.toc a{display:block;padding:5px 0;color:var(--muted);font-size:13px;text-decoration:none}.content{min-width:0}section{padding-top:64px;scroll-margin-top:20px}.kicker{display:block;margin-bottom:12px}.answer{margin-top:28px;padding:28px 30px;border-left:5px solid var(--green);box-shadow:var(--shadow)}.answer p{margin:0;font:23px/1.55 var(--serif)}.answer-foot{display:flex;flex-wrap:wrap;gap:18px;margin-top:18px;color:var(--muted);font:11px var(--mono)}.panel{margin-top:18px;padding:24px}.chain{display:grid;gap:14px;margin-top:28px}.claim{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(300px,1.2fr);grid-template-rows:auto 1fr;gap:10px 24px;padding:20px;border:1px solid var(--line);border-radius:12px;background:var(--paper)}.ctype{grid-column:1;grid-row:1;color:var(--green);font:700 11px var(--mono);text-transform:uppercase}.claim p{grid-column:1;grid-row:2;margin:0;color:var(--ink2);font-size:18px;line-height:1.6}.tags{grid-column:2;grid-row:1 / span 2;display:flex;flex-wrap:wrap;gap:8px;align-content:start;align-items:flex-start;justify-content:flex-start;padding-top:2px}.tag{padding:5px 9px;border:1px solid var(--line);border-radius:5px;color:var(--blue);background:var(--blue2);font:10px var(--mono);white-space:normal;overflow-wrap:anywhere}.egrid,.split{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:28px}.ecard{padding:22px}.ecard.support{border-top:4px solid var(--green)}.ecard.oppose{border-top:4px solid var(--red)}.ecard>p{font:700 11px var(--mono);text-transform:uppercase}.ecard li+li{margin-top:12px}.ecard small{display:block;color:var(--muted)}.scorecard-block{margin-top:28px}.scorecard-block h3{font:700 13px var(--mono);text-transform:uppercase;color:var(--muted)}.scorecard-row{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}.scorecard-row svg{flex:none}.scores{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:28px;flex:1;min-width:280px}.scorecard-row .scores{margin-top:0}.score{min-height:150px;padding:18px}.score strong{display:block;margin:18px 0 6px;font:22px var(--serif)}.pips{display:flex;gap:4px;margin-top:13px}.pip{width:18px;height:5px;border-radius:4px;background:var(--line)}.pip.on{background:var(--green)}.clean{margin:0;padding:0;list-style:none}.clean li{display:grid;grid-template-columns:28px 1fr;gap:10px;padding:14px 0;border-bottom:1px solid var(--line)}.idx{color:var(--muted);font:11px var(--mono)}.clean p{margin:0}.empty{color:var(--muted)}details{margin-top:24px}summary{padding:16px 20px;cursor:pointer;font-weight:700}.tablewrap{overflow:auto;padding:0 20px 20px}table{width:100%;min-width:780px;border-collapse:collapse;font-size:13px}th,td{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font:10px var(--mono);text-transform:uppercase}td:first-child,.cite{color:var(--blue);font:11px var(--mono)}.high{color:var(--green);font-weight:700}.medium{color:var(--amber);font-weight:700}.low{color:var(--red);font-weight:700}.downloads{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:24px}.download{display:block;padding:15px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink);text-decoration:none}.download b{display:block;font:11px var(--mono)}.download small{color:var(--muted)}footer{margin-top:72px;padding-top:28px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}.foot{display:grid;grid-template-columns:1fr auto;gap:24px}.footmark{font-family:var(--mono);text-align:right}
@media(max-width:900px){.hero-grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}main{grid-template-columns:1fr}.toc{display:none}.scores{grid-template-columns:repeat(2,1fr)}.downloads{grid-template-columns:1fr 1fr}}@media(max-width:620px){.shell{padding:0 18px 64px}.hero{padding-top:48px}.stats,.egrid,.split,.scores,.downloads{grid-template-columns:1fr}.claim{grid-template-columns:1fr}.tags{justify-content:start}.panel-head,.foot{display:block}.footmark{text-align:left}}@media print{body{background:#fff;color:#111;font-size:11pt}.shell{max-width:none;padding:0 12mm 15mm}.toolbar,.toc{display:none!important}.hero{padding-top:18mm}main{display:block}section{break-inside:avoid;padding-top:12mm}.panel,.claim,.ecard,.score,details{box-shadow:none;break-inside:avoid}.downloads{display:none}details>*{display:block!important}a{color:inherit;text-decoration:none}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

