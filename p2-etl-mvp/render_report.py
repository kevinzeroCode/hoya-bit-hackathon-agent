"""Local integration: fill P4's Task-7 HTML report template with REAL P2 data.

This is a PRESENTER PROTOTYPE, not a shared contract. It runs P2's pipeline and
injects the parts P2 deterministically owns — market chart, market regime,
Evidence Ledger, trust counts, coverage, diversity, degradation — into
`render/report_template.html`, writing `render/out/hoya-report-<ASSET>.html`.

Boundary respected: judgment slots (directional conclusion, claim reasoning,
support/oppose STANCE, consistency) belong to P3 and are marked "待 P3 推理層"
rather than fabricated. Market numbers stay deterministic; reliability stays from
the static table; nothing is labelled `official`.

    python render_report.py BTC        # offline (real CSV) + best-effort live
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import httpx
from adapters.alternative_me import fetch_fear_greed
from adapters.okx import CANDLES_URL as OKX_URL
from adapters.okx import INDEPENDENCE_GROUP as OKX_GROUP
from adapters.okx import SOURCE_NAME as OKX_SOURCE
from adapters.okx import fetch_okx_daily
from adapters.organizer_csv import default_data_dir, load_organizer_csv
from adapters.reddit import fetch_reddit_posts
from adapters.rss import fetch_rss_news
from data.market_series import closes
from data.market_worker import build_market_evidence
from data.price_analysis import build_attribution_evidence, build_event_timeline_evidence
from data.regime import build_regime_evidence, classify_regime
from evidence.policies import ConfidenceSignals, max_confidence
from evidence.processor import build_ledger

UTC = timezone.utc
_HERE = Path(__file__).resolve().parent
_TEMPLATE = _HERE / "render" / "report_template.html"
_OUT_DIR = _HERE / "render" / "out"

_REGIME_ZH = {
    "trending_up": "趨勢向上", "trending_down": "趨勢向下", "range_bound": "區間盤整",
    "high_volatility": "高波動", "mixed": "方向不明",
}
_FEEDS = [
    ("https://www.coindesk.com/arc/outboundfeeds/rss?outputType=xml", "CoinDesk", "coindesk.com"),
    ("https://www.theblock.co/rss.xml", "The Block", "theblock.co"),
    ("https://bitcoinmagazine.com/feed", "Bitcoin Magazine", "bitcoinmagazine.com"),
    ("https://cryptoslate.com/feed/", "CryptoSlate", "cryptoslate.com"),
    ("https://decrypt.co/feed", "Decrypt", "decrypt.co"),
    ("https://cointelegraph.com/rss", "Cointelegraph", "cointelegraph.com"),
]


# ── data gathering ──────────────────────────────────────────────────────────

def gather(asset: str) -> dict:
    bars = load_organizer_csv(default_data_dir() / f"{asset}_daily_ohlcv.csv")
    as_of = bars[-1].date
    drafts = list(build_market_evidence(asset, bars, analysis_as_of=as_of).drafts)
    drafts += list(build_regime_evidence(asset, bars, analysis_as_of=as_of).drafts)
    regime = classify_regime(asset, bars, analysis_as_of=as_of)
    notes: list[str] = []

    # A6 event timeline (self) + A5 attribution vs BTC — deterministic, high.
    drafts += list(build_event_timeline_evidence(asset, bars, analysis_as_of=as_of).drafts)
    if asset != "BTC":
        btc_bars = load_organizer_csv(default_data_dir() / "BTC_daily_ohlcv.csv")
        drafts += list(build_attribution_evidence(asset, bars, btc_bars, analysis_as_of=as_of).drafts)

    # Best-effort live sources — offline still renders (market-only).
    now = datetime.now(UTC)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (research; hoya-market-agent/0.1)"},
        follow_redirects=True, timeout=12.0,
    )
    live_ok = True
    try:
        okx_bars, deg = fetch_okx_daily(asset, analysis_as_of=now, client=client)
        notes += deg
        if okx_bars:
            drafts += list(build_market_evidence(
                asset, okx_bars, analysis_as_of=okx_bars[-1].date,
                source_name=OKX_SOURCE, independence_group=OKX_GROUP, source_url=OKX_URL,
            ).drafts)
    except httpx.HTTPError:
        live_ok = False
        notes.append("OKX live unavailable (offline)")
    for url, name, dom in _FEEDS:
        try:
            r = fetch_rss_news(asset, analysis_as_of=now, client=client,
                               feed_url=url, source_name=name, publisher_domain=dom, lookback_days=30)
            drafts += list(r.drafts)
        except httpx.HTTPError:
            live_ok = False
    try:
        rd = fetch_reddit_posts(asset, analysis_as_of=now, client=client)
        drafts += list(rd.drafts)
        notes += rd.degradation
    except httpx.HTTPError:
        pass
    try:
        fg = fetch_fear_greed(analysis_as_of=now, client=client)
        drafts += list(fg.drafts)
        notes += fg.degradation
    except httpx.HTTPError:
        pass

    ledger = build_ledger(drafts)
    return {
        "asset": asset, "as_of": as_of, "bars": bars, "regime": regime,
        "ledger": ledger, "notes": notes, "live_ok": live_ok,
    }


# ── derived presentation values (all deterministic) ─────────────────────────

def _ordinal(n: int, strong: int, moderate: int) -> str:
    return "Strong" if n >= strong else "Moderate" if n >= moderate else "Weak"


def _svg_paths(cl: list[float], n: int = 14) -> tuple[str, str, str]:
    """price, area, 7-day MA paths mapped into the template's 760x300 viewBox."""
    window = cl[-n:] if len(cl) >= n else cl[:]
    x0, x1, ytop, ybot, base = 54.0, 730.0, 55.0, 235.0, 250.0
    lo, hi = min(window), max(window)
    span = (hi - lo) or 1.0
    m = len(window)
    xs = [x0 + i * (x1 - x0) / (m - 1) for i in range(m)] if m > 1 else [x0]
    ys = [ybot - (c - lo) / span * (ybot - ytop) for c in window]
    price = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in zip(xs, ys))
    area = price + f" L {x1:.0f} {base:.0f} L {x0:.0f} {base:.0f} Z"
    ma = []
    for i in range(m):
        seg = window[max(0, i - 6): i + 1]
        avg = sum(seg) / len(seg)
        ma.append(ybot - (avg - lo) / span * (ybot - ytop))
    avgline = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in zip(xs, ma))
    return price, area, avgline


def build_values(d: dict) -> dict:
    asset, ledger, regime = d["asset"], d["ledger"], d["regime"]
    items = ledger.items
    rel = {"high": 0, "medium": 0, "low": 0}
    for it in items:
        rel[it.reliability] = rel.get(it.reliability, 0) + 1
    types = {it.source_type for it in items}
    groups = ledger.independence_group_count
    top_rel = "high" if rel["high"] else "medium" if rel["medium"] else "low"
    cap = max_confidence(ConfidenceSignals(
        supporting_groups=groups, max_supporting_reliability=top_rel,
        insufficient_data=len(items) < 3,
    ))
    with_pub = sum(1 for it in items if it.published_at is not None)

    cl = closes(d["bars"])
    price, area, avgline = _svg_paths(cl)
    window_dates = [b.date for b in d["bars"]][-14:]

    regime_zh = _REGIME_ZH.get(regime.label, "—") if regime else "—"
    regime_desc = (
        f"14 日報酬 {regime.return_window_pct * 100:+.2f}%、波動處於自身歷史第 "
        f"{regime.vol_percentile * 100:.0f} 百分位、區間位置 {regime.range_position * 100:.0f}%"
        if regime else "資料不足"
    )
    return {
        "asset": asset, "as_of": d["as_of"], "cap": cap, "regime_zh": regime_zh,
        "regime_desc": regime_desc, "n_items": len(items), "n_drop": ledger.dropped_duplicates,
        "n_types": len(types), "type_list": "、".join(sorted(t for t in types)),
        "groups": groups, "rel": rel, "top_rel": top_rel, "with_pub": with_pub,
        "price": price, "area": area, "avgline": avgline, "window_dates": window_dates,
        "items": items, "live_ok": d["live_ok"], "notes": d["notes"],
        "question": (d.get("question") or "").strip(),
    }


# ── template injection ──────────────────────────────────────────────────────

def _ledger_rows(items, limit: int = 14) -> str:
    rows = []
    for it in items[:limit]:
        ref = (it.content_reference or it.normalized_fact or "")[:60]
        ts = it.fetched_at.strftime("%Y-%m-%dT%H:%MZ") if it.fetched_at else "—"
        cls = "high" if it.reliability == "high" else "medium" if it.reliability == "medium" else ""
        rows.append(
            f"<tr><td>{it.evidence_id}</td><td>{escape(it.source_name or '—')}</td>"
            f"<td>{ts}</td><td>{escape(ref)}</td><td>—（待 P3 連結）</td>"
            f'<td class="{cls}">{it.reliability}</td></tr>'
        )
    return "".join(rows)


def render(v: dict, template: str) -> str:
    h = template
    a = v["asset"]
    run_state = "REHEARSAL · 真實資料" if v["live_ok"] else "REHEARSAL · 離線(僅市場)"

    def rep(old: str, new: str) -> None:
        nonlocal h
        if old not in h:
            raise SystemExit(f"[render] anchor not found (template changed?): {old[:50]}")
        h = h.replace(old, new, 1)

    # header
    rep("<h1>BTC 市場狀況與短期方向判斷</h1>",
        f"<h1>{a} 市場狀況與資料／證據整合</h1>")
    q = v.get("question", "")
    if q:
        standfirst = (
            f"本次題目：「{escape(q)}」。本頁整合 {a} 的市場、新聞與情緒證據並揭露限制；"
            f"方向性結論由 P3 推理層產生，且不提供價格預測（研究導向，非投資建議）。"
        )
    else:
        standfirst = (
            f"整合 {a} 的市場、新聞與情緒證據並揭露限制；方向性結論由 P3 推理層產生"
            f"（研究導向，非投資建議）。"
        )
    rep("<p class=\"standfirst\">針對 BTC 過去兩週的市場表現，整合價格、新聞與市場情緒，"
        "說明訊號一致程度、主要風險與可能推翻結論的條件。</p>",
        f'<p class="standfirst">{standfirst}</p>')
    rep('<span class="chip demo">DEMO · 錄製資料</span>',
        f'<span class="chip demo">{run_state}</span>')
    rep('<span class="runid">demo-btc-001</span>',
        f'<span class="runid">p2-local-{a.lower()}-{datetime.now(UTC):%Y%m%d}</span>')
    rep("<p class=\"verdict\">偏多，但尚未形成高信心趨勢</p>",
        f'<p class="verdict">市場狀態：{v["regime_zh"]}（方向性結論待 P3）</p>')
    rep("<p class=\"reason\">這是展示模板，不代表即時市場判斷。</p>",
        '<p class="reason">P2 本地整合：市場/證據為真實資料；方向判斷由 P3 推理層產生。</p>')
    rep("<dd>2026-05-31 UTC</dd>", f"<dd>{v['as_of']} UTC</dd>")

    # stats (4)
    rep("<small>Market Regime</small><strong>Mixed</strong><p>動能偏正，波動與量能未同步確認</p>",
        f"<small>Market Regime</small><strong>{v['regime_zh']}</strong><p>{escape(v['regime_desc'])}</p>")
    rep("<small>Conclusion Confidence</small><strong>Medium</strong><p>3 個獨立來源群組，存在 1 個反方訊號</p>",
        f"<small>Confidence 上限</small><strong>{v['cap'].capitalize()}</strong>"
        f"<p>{v['groups']} 個獨立來源群（deterministic 上限，最終值待 P3）</p>")
    rep("<small>Evidence Coverage</small><strong>8 / 10</strong><p>價格與新聞完整；鏈上資料降級</p>",
        f"<small>Evidence Coverage</small><strong>{v['n_items']} 筆</strong>"
        f"<p>去重後保留 {v['n_items']} 筆（丟棄重複 {v['n_drop']}）</p>")
    rep("<small>Source Diversity</small><strong>3 類</strong><p>市場資料、官方公告、公開新聞</p>",
        f"<small>Source Diversity</small><strong>{v['n_types']} 類</strong><p>{escape(v['type_list'])}</p>")

    # market chart
    rep("<p>展示資料 · 2026-05-18 至 2026-05-31 · USDT</p>",
        f"<p>真實資料 · {v['window_dates'][0]} 至 {v['window_dates'][-1]} · 官方 CSV</p>")
    h = re.sub(r'(<path class="area" d=")[^"]*(")', lambda m: m.group(1) + v["area"] + m.group(2), h, count=1)
    h = re.sub(r'(<path class="price" d=")[^"]*(")', lambda m: m.group(1) + v["price"] + m.group(2), h, count=1)
    h = re.sub(r'(<path class="avgline" d=")[^"]*(")', lambda m: m.group(1) + v["avgline"] + m.group(2), h, count=1)
    labels = v["window_dates"]
    mid = labels[len(labels) // 2]
    h = h.replace(">05/18</text>", f">{labels[0]:%m/%d}</text>", 1)
    h = h.replace(">05/24</text>", f">{mid:%m/%d}</text>", 1)
    h = h.replace(">05/31</text>", f">{labels[-1]:%m/%d}</text>", 1)
    rep("主辦方 OHLCV CSV；圖中數值僅為模板示意，正式 Renderer 必須使用該次 run 的確定性計算結果。",
        f"主辦方 OHLCV CSV（{a}）；收盤價與 7 日均線為 deterministic 計算結果（近 14 日）。")

    # evidence ledger — real rows
    h = re.sub(r"<tbody>.*?</tbody>", "<tbody>" + _ledger_rows(v["items"]) + "</tbody>", h, count=1, flags=re.S)

    # trust scorecard (P2-owned three) + honest markers for P3-owned
    rep("<small>獨立性</small><strong>Strong</strong><p>3 個 independence groups</p>",
        f"<small>獨立性</small><strong>{_ordinal(v['groups'],3,2)}</strong><p>{v['groups']} 個 independence groups</p>")
    rep("<small>來源多樣性</small><strong>Moderate</strong><p>3 類；缺鏈上</p>",
        f"<small>來源多樣性</small><strong>{_ordinal(v['n_types'],3,2)}</strong>"
        f"<p>{v['n_types']} 類：{escape(v['type_list'])}</p>")
    rep("<small>可信度組成</small><strong>Strong</strong><p>high 4 · medium 3</p>",
        f"<small>可信度組成</small><strong>{'Strong' if v['rel']['high'] else 'Moderate'}</strong>"
        f"<p>high {v['rel']['high']} · medium {v['rel']['medium']} · low {v['rel']['low']}</p>")
    rep("<small>一致性</small><strong>Moderate</strong><p>1 個反方訊號</p>",
        "<small>一致性</small><strong>待 P3</strong><p>需 claim 立場（矛盾偵測）</p>")
    rep("<small>時效性</small><strong>Moderate</strong><p>1 個來源 freshness 未知</p>",
        f"<small>時效性</small><strong>—</strong><p>{v['with_pub']}/{v['n_items']} 筆具 published_at</p>")

    # direct-answer + reasoning: mark as P3's
    rep("<p>目前證據較支持「市場處於偏多但仍混合的狀態」，而不是已確認的單邊上升趨勢。"
        "價格動能提供支持，但量能與外部風險訊號仍不足以把信心提高至 high。</p>",
        f"<p>P2 提供的 deterministic 市場狀態為「{v['regime_zh']}」（{escape(v['regime_desc'])}）。"
        f"方向性結論與信心值由 P3 推理層依下方 Evidence Ledger 產生——此處不由 P2 判斷。</p>")
    rep("<div class=\"answer-foot\"><span>CONCLUSION · C-03</span>"
        "<span>CONFIDENCE · MEDIUM</span>"
        "<span>SUPPORT · E-001, E-003, E-006</span>"
        "<span>OPPOSE · E-008</span></div>",
        f'<div class="answer-foot"><span>EVIDENCE · {v["n_items"]} 筆</span>'
        f'<span>CONFIDENCE 上限 · {v["cap"].upper()}</span>'
        f'<span>獨立群 · {v["groups"]}</span><span>STANCE · 待 P3</span></div>')
    rep("本頁使用示意資料展示報告結構。正式執行必須替換為該次 run 的 Evidence Ledger、"
        "原始時間戳與真實降級狀態；fixture 不得標示為 official。",
        "本頁為 P2 本地整合：市場圖表、Evidence Ledger、信任計數為該次 run 的真實 deterministic 資料；"
        "推理鏈與正反立場區塊仍為 P3 待接（示意）。非 official run。")
    return h


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    asset = (sys.argv[1] if len(sys.argv) > 1 else "BTC").upper()
    template = _TEMPLATE.read_text(encoding="utf-8")
    v = build_values(gather(asset))
    out_html = render(v, template)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / f"hoya-report-{asset}.html"
    out_path.write_text(out_html, encoding="utf-8")
    print(f"[render] {asset}: {v['n_items']} 筆證據、{v['groups']} 獨立群、狀態={v['regime_zh']}、"
          f"confidence 上限={v['cap']}、live={'yes' if v['live_ok'] else 'offline'}")
    print(f"[render] 已輸出：{out_path}")


if __name__ == "__main__":
    main()


# ── comparison rendering (P4 template style, two rebased price lines) ─────────

def _svg_two_paths(cl_a, cl_b, n: int = 14):
    """Two price lines rebased to 100, mapped into the template's 760x300 viewBox."""
    wa = (cl_a[-n:] if len(cl_a) >= n else cl_a[:])
    wb = (cl_b[-n:] if len(cl_b) >= n else cl_b[:])
    m = min(len(wa), len(wb))
    wa, wb = wa[-m:], wb[-m:]
    ra = [c / wa[0] * 100 for c in wa]
    rb = [c / wb[0] * 100 for c in wb]
    x0, x1, ytop, ybot, base = 54.0, 730.0, 55.0, 235.0, 250.0
    lo = min(min(ra), min(rb))
    hi = max(max(ra), max(rb))
    span = (hi - lo) or 1.0
    xs = [x0 + i * (x1 - x0) / (m - 1) for i in range(m)] if m > 1 else [x0]
    ya = [ybot - (v - lo) / span * (ybot - ytop) for v in ra]
    yb = [ybot - (v - lo) / span * (ybot - ytop) for v in rb]
    pa = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in zip(xs, ya))
    pb = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in zip(xs, yb))
    return pa, pa + f" L {x1:.0f} {base:.0f} L {x0:.0f} {base:.0f} Z", pb


def render_comparison(cb, template: str) -> str:
    """Fill the P4 report template for a 1–2 coin comparison (same visual language)."""
    h = template
    a, b = cb.asset_a, cb.asset_b
    items = cb.ledger.items
    rel = {"high": 0, "medium": 0, "low": 0}
    for it in items:
        rel[it.reliability] = rel.get(it.reliability, 0) + 1
    types = {it.source_type for it in items}
    groups = cb.ledger.independence_group_count
    with_pub = sum(1 for it in items if it.published_at is not None)
    m = cb.metrics or {}
    ret_a, ret_b = m.get("ret_a", 0.0), m.get("ret_b", 0.0)
    corr, beta, pct = m.get("corr", 0.0), m.get("beta", 0.0), m.get("pct", 0.0)

    def rep(old: str, new: str) -> None:
        nonlocal h
        if old in h:
            h = h.replace(old, new, 1)

    rep("<h1>BTC 市場狀況與短期方向判斷</h1>", f"<h1>{a} vs {b} 跨幣比較</h1>")
    rep("<p class=\"standfirst\">針對 BTC 過去兩週的市場表現，整合價格、新聞與市場情緒，"
        "說明訊號一致程度、主要風險與可能推翻結論的條件。</p>",
        f'<p class="standfirst">比較 {a} 與 {b} 的相對表現（報酬、相關性、相對強弱）；'
        f'跨幣只用報酬/比值，不比 base volume。方向性結論由 P3 產生，不預測價格。</p>')
    rep('<span class="chip demo">DEMO · 錄製資料</span>', '<span class="chip demo">REHEARSAL · 真實資料</span>')
    rep('<span class="runid">demo-btc-001</span>',
        f'<span class="runid">p2-cmp-{a.lower()}-{b.lower()}-{datetime.now(UTC):%Y%m%d}</span>')
    rep("<p class=\"verdict\">偏多，但尚未形成高信心趨勢</p>",
        f'<p class="verdict">{a} 近 14 日相對 {b} {"較強" if ret_a >= ret_b else "較弱"}（方向性結論待 P3）</p>')
    rep("<p class=\"reason\">這是展示模板，不代表即時市場判斷。</p>",
        '<p class="reason">P2 跨幣比較：市場/證據為真實資料；方向判斷由 P3 推理層產生。</p>')
    rep("<dd>2026-05-31 UTC</dd>", f"<dd>{cb.as_of} UTC</dd>")

    rep("<small>Market Regime</small><strong>Mixed</strong><p>動能偏正，波動與量能未同步確認</p>",
        f"<small>相對報酬(14日)</small><strong>{(ret_a - ret_b) * 100:+.2f}%</strong>"
        f"<p>{a} {ret_a:+.2%}、{b} {ret_b:+.2%}</p>")
    rep("<small>Conclusion Confidence</small><strong>Medium</strong><p>3 個獨立來源群組，存在 1 個反方訊號</p>",
        f"<small>相關性(90日)</small><strong>{corr:.2f}</strong><p>越高越隨 {b} 同向</p>")
    rep("<small>Evidence Coverage</small><strong>8 / 10</strong><p>價格與新聞完整；鏈上資料降級</p>",
        f"<small>Beta</small><strong>{beta:.2f}</strong><p>{a} 對 {b} 的敏感度</p>")
    rep("<small>Source Diversity</small><strong>3 類</strong><p>市場資料、官方公告、公開新聞</p>",
        f"<small>相對強弱</small><strong>{pct * 100:.0f} 百分位</strong><p>{a}/{b} 比值(近 252 日)</p>")

    # chart：兩幣 rebased=100 疊線
    cl_a = [bar.close for bar in cb.bars_a]
    cl_b = [bar.close for bar in cb.bars_b]
    if cl_a and cl_b:
        pa, area_a, pb = _svg_two_paths(cl_a, cl_b)
        h = re.sub(r'(<path class="area" d=")[^"]*(")', lambda mo: mo.group(1) + area_a + mo.group(2), h, count=1)
        h = re.sub(r'(<path class="price" d=")[^"]*(")', lambda mo: mo.group(1) + pa + mo.group(2), h, count=1)
        h = re.sub(r'(<path class="avgline" d=")[^"]*(")', lambda mo: mo.group(1) + pb + mo.group(2), h, count=1)
        wd = [bar.date for bar in cb.bars_a][-14:]
        if wd:
            h = h.replace(">05/18</text>", f">{wd[0]:%m/%d}</text>", 1)
            h = h.replace(">05/24</text>", f">{wd[len(wd)//2]:%m/%d}</text>", 1)
            h = h.replace(">05/31</text>", f">{wd[-1]:%m/%d}</text>", 1)
    rep("<p>展示資料 · 2026-05-18 至 2026-05-31 · USDT</p>",
        f"<p>真實資料 · {a} vs {b} · 近 14 日收盤(rebased=100)</p>")
    rep("<span><i></i>收盤價</span><span><i class=\"avg\"></i>7 日均線</span>",
        f'<span><i></i>{a}</span><span><i class="avg"></i>{b}</span>')
    rep("主辦方 OHLCV CSV；圖中數值僅為模板示意，正式 Renderer 必須使用該次 run 的確定性計算結果。",
        f"{a} 與 {b} 近 14 日收盤(rebased 到 100)；deterministic 計算，跨幣只用報酬/比值，不比 base volume。")

    h = re.sub(r"<tbody>.*?</tbody>", "<tbody>" + _ledger_rows(items) + "</tbody>", h, count=1, flags=re.S)

    rep("<small>獨立性</small><strong>Strong</strong><p>3 個 independence groups</p>",
        f"<small>獨立性</small><strong>{_ordinal(groups,3,2)}</strong><p>{groups} 個 independence groups</p>")
    rep("<small>來源多樣性</small><strong>Moderate</strong><p>3 類；缺鏈上</p>",
        f"<small>來源多樣性</small><strong>{_ordinal(len(types),3,2)}</strong><p>{len(types)} 類</p>")
    rep("<small>可信度組成</small><strong>Strong</strong><p>high 4 · medium 3</p>",
        f"<small>可信度組成</small><strong>{'Strong' if rel['high'] else 'Moderate'}</strong>"
        f"<p>high {rel['high']} · medium {rel['medium']} · low {rel['low']}</p>")
    rep("<small>一致性</small><strong>Moderate</strong><p>1 個反方訊號</p>",
        "<small>一致性</small><strong>待 P3</strong><p>需 claim 立場（矛盾偵測）</p>")
    rep("<small>時效性</small><strong>Moderate</strong><p>1 個來源 freshness 未知</p>",
        f"<small>時效性</small><strong>—</strong><p>{with_pub}/{len(items)} 筆具 published_at</p>")

    rep("<p>目前證據較支持「市場處於偏多但仍混合的狀態」，而不是已確認的單邊上升趨勢。"
        "價格動能提供支持，但量能與外部風險訊號仍不足以把信心提高至 high。</p>",
        f"<p>P2 提供 {a} 與 {b} 的 deterministic 跨幣比較(相對報酬 {(ret_a-ret_b)*100:+.2f} 個百分點、"
        f"相關性 {corr:.2f}、beta {beta:.2f})。哪一個較值得布局的方向性結論由 P3 推理層產生——此處不由 P2 判斷。</p>")
    rep("<div class=\"answer-foot\"><span>CONCLUSION · C-03</span>"
        "<span>CONFIDENCE · MEDIUM</span>"
        "<span>SUPPORT · E-001, E-003, E-006</span>"
        "<span>OPPOSE · E-008</span></div>",
        f'<div class="answer-foot"><span>比較 · {a} vs {b}</span><span>證據 · {len(items)} 筆</span>'
        f'<span>獨立群 · {groups}</span><span>STANCE · 待 P3</span></div>')
    rep("本頁使用示意資料展示報告結構。正式執行必須替換為該次 run 的 Evidence Ledger、"
        "原始時間戳與真實降級狀態；fixture 不得標示為 official。",
        "本頁為 P2 跨幣比較(輕量,保留 1–2 幣契約)：市場/比較證據為真實 deterministic 資料；"
        "推理與方向結論待 P3。非 official run。")
    return h
