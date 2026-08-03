"""S3 — Streamlit Bronze UI.

    streamlit run src/hoya_agent/ui/streamlit_app.py

The judge picks an asset (and question) and runs an **offline** analysis through
the real `ApplicationService` + deterministic `OrganizerCsvPipeline` (no live HTTP,
no Bedrock, no AWS). It shows the run-mode badge, terminal state, the deterministic
report and the four fixed artifacts (downloadable). The Renderer runs the
prohibited-investment-advice lint (`reporting.advice_lint`), so rendered text is safe
by construction. Pipeline `ExecutionEvent`s stream live into an `st.status` panel.

Business logic lives in `application.py` / `presenter.py`; this file is only glue.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Make `hoya_agent` importable when launched via
# `streamlit run src/hoya_agent/ui/streamlit_app.py` with no editable install or
# PYTHONPATH (a judge just running the file). Docker installs the package, so
# `src` is simply already on the path there and this is a harmless no-op.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st  # noqa: E402

from hoya_agent.adapters.live_sources import binance_bar_loader, fear_greed_drafts  # noqa: E402
from hoya_agent.application import ApplicationService, build_request  # noqa: E402
from hoya_agent.clock import SystemClock  # noqa: E402
from hoya_agent.models import Asset, RunMode  # noqa: E402
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline  # noqa: E402
from hoya_agent.ui.presenter import (  # noqa: E402
    agent_judgment_view,
    summary_view,
    triangulation_view,
    trust_funnel,
)

UTC = timezone.utc
# Organizer CSV ends 2026-05-31; Bronze replays that frozen cutoff (offline).
BRONZE_CUTOFF = datetime(2026, 5, 31, tzinfo=UTC)
# Ordered to mirror the competition 提交清單; labels map each fixed filename to
# the deliverable a judge is looking for.
ARTIFACT_ORDER = (
    "final_report.html",
    "final_report.md",
    "evidence_list.json",
    "evidence.json",
    "execution_log.jsonl",
    "run_config.json",
)
ARTIFACT_LABELS = {
    "final_report.html": "① 完整 HTML 分析報告",
    "final_report.md": "① 分析報告 Final Report",
    "evidence_list.json": "② 證據清單 Evidence List",
    "evidence.json": "② 完整證據 Ledger(佐證)",
    "execution_log.jsonl": "③ 執行紀錄 Execution Log",
    "run_config.json": "④ 執行配置 Run Config",
}


class _StreamlitProgress:
    """ProgressSink that streams pipeline events into a live `st.status` panel.

    `emit` is sync (per the ProgressSink seam) and runs on the same thread as
    `asyncio.run`, so each write repaints the status label in real time as the
    Planner → Market → Evidence → Renderer stages fire. Carries no secrets:
    ExecutionEvent never holds prompts, tokens or credentials.
    """

    def __init__(self, status) -> None:
        self._status = status
        self._n = 0

    def emit(self, event) -> None:  # duck-typed ExecutionEvent (avoids a provisional-seam import)
        self._n += 1
        message = getattr(event, "message", "")
        detail = f" — {message}" if message else ""
        line = f"[{event.stage}] {event.event_type} · {event.status}{detail}"
        self._status.update(label=line)
        self._status.write(f"`{self._n:02d}` {line}")


def _run_offline(assets: list[Asset], question: str, run_mode: RunMode, progress=None) -> tuple:
    now = datetime.now(UTC)
    request = build_request(
        question=question or "市場狀況與資料整合",
        assets=assets,
        run_mode=run_mode,
        now=now,
        run_id_suffix="ui",
        analysis_as_of=BRONZE_CUTOFF,
    )
    pipeline = OrganizerCsvPipeline(analysis_date=BRONZE_CUTOFF.date())
    service = ApplicationService(
        artifact_root=Path(tempfile.mkdtemp(prefix="hoya-ui-")),
        clock=SystemClock(),
        pipeline=pipeline,
        configured_sources=["public_market_data"],
    )
    summary = asyncio.run(service.run(request, progress=progress))
    return summary, getattr(pipeline, "last_bars_by_asset", {})


def _bedrock_env() -> tuple[str, str] | None:
    """Return (region, model_id) if Bedrock is configured via env, else None.

    Credentials themselves come from the standard AWS chain (EC2 IAM role or local
    env) — never read or stored here. Only presence of region + model id gates
    whether we attempt the reasoning layer.
    """
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    model_id = os.getenv("BEDROCK_PRIMARY_MODEL_ID")
    if region and model_id:
        return region.strip(), model_id.strip()
    return None


def _live_pipeline(now, assets, question):
    """Bedrock-reasoning pipeline when configured; else deterministic live data.

    Any failure building the reasoning path degrades to the deterministic market
    + sentiment pipeline, which itself renders an honest report — the run never
    crashes.
    """
    bedrock = _bedrock_env()
    if bedrock is not None:
        try:
            from hoya_agent.composition import build_bedrock_llm, build_live_pipeline

            region, model_id = bedrock
            llm = build_bedrock_llm(
                region=region,
                primary_model_id=model_id,
                fallback_model_id=os.getenv("BEDROCK_FALLBACK_MODEL_ID") or None,
            )
            pipeline = build_live_pipeline(
                clock=SystemClock(), llm=llm, analysis_as_of=now, assets=assets, question=question
            )
            return pipeline, True
        except Exception:  # noqa: BLE001 - fall back to deterministic live data
            pass
    return (
        OrganizerCsvPipeline(
            load_bars=binance_bar_loader(now),
            extra_drafts=fear_greed_drafts(now),
            analysis_date=now.date(),
            market_source_name="binance_spot",
            market_independence_group="binance",
            market_source_url="https://api.binance.com/api/v3/klines",
        ),
        False,
    )


def _run_live(assets: list[Asset], question: str, progress=None) -> tuple:
    """Real-time run: live Binance market + Fear & Greed; Arbiter reasons when
    Bedrock is configured (EC2 IAM role / env), otherwise deterministic evidence."""
    now = datetime.now(UTC)
    request = build_request(
        question=question or "即時市場狀況與資料整合",
        assets=assets,
        run_mode=RunMode.official,
        now=now,
        run_id_suffix="live",
    )
    pipeline, with_bedrock = _live_pipeline(now, assets, question)
    sources = ["binance_spot", "fear_greed"] + (["coindesk_rss", "bedrock"] if with_bedrock else [])
    service = ApplicationService(
        artifact_root=Path(tempfile.mkdtemp(prefix="hoya-live-")),
        clock=SystemClock(),
        pipeline=pipeline,
        configured_sources=sources,
    )
    summary = asyncio.run(service.run(request, progress=progress))
    return summary, getattr(pipeline, "last_bars_by_asset", {})


def _artifact_text(view: dict, name: str) -> str | None:
    path = view["artifacts"].get(name)
    if path and Path(path).exists():
        return Path(path).read_text(encoding="utf-8")
    return None


# `st.iframe(..., height="content")` measures the srcdoc document and sizes both
# the frame *and* its element container, so the report flows with the page instead
# of scrolling inside a fixed viewport. Sizing the iframe alone is not enough: the
# container keeps the declared height and the report then overlaps everything
# below it (the download row, the other tab panels).
_TOC_MARKER = "hoya-report-toc"
_TOC_SCRIPT = """
<script id="hoya-report-toc">
'use strict';
(function () {
  // A content-sized frame never scrolls, so the report's own TOC anchors would
  // be dead links. Scroll the host page instead. Streamlit's scrolling box is
  // not always the window, so walk up for the frame's nearest scrollable
  // ancestor. Same-origin access is granted by the iframe's `allow-same-origin`.
  var frame = window.frameElement;
  if (!frame) return;  // cross-origin: leave the default anchor behaviour

  // Streamlit measures this document and posts the size to the host, but only
  // when the measurement *changes* — and a srcdoc frame can load before the host
  // attaches its listener, so the one and only measurement is lost and the frame
  // stays at its unmeasured height (a short box with an inner scrollbar). The
  // report is static, so nothing ever triggers a resend. Perturb the height by
  // 1px and restore it: each change re-fires Streamlit's observer, and the final
  // post carries the true height.
  function nudge() {
    document.body.style.paddingBottom = '1px';
    setTimeout(function () { document.body.style.paddingBottom = ''; }, 50);
  }
  [250, 900, 2000].forEach(function (delay) { setTimeout(nudge, delay); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(nudge);

  function host() {
    var doc = window.parent.document;
    var el = frame.parentElement;
    while (el && el !== doc.documentElement) {
      var overflow = window.parent.getComputedStyle(el).overflowY;
      if (/(auto|scroll|overlay)/.test(overflow) && el.scrollHeight > el.clientHeight + 1) return el;
      el = el.parentElement;
    }
    return window.parent;
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest ? event.target.closest('a[href^="#"]') : null;
    if (!link) return;
    var target = document.getElementById(link.getAttribute('href').slice(1));
    if (!target) return;
    try {
      // The frame never scrolls, so the target's rect inside it is its offset
      // from the frame top; the frame's own rect is in host viewport coords.
      var delta = frame.getBoundingClientRect().top + target.getBoundingClientRect().top - 12;
      host().scrollBy({ top: delta, behavior: 'smooth' });
      event.preventDefault();
    } catch (err) { /* cross-origin parent: leave the default anchor behaviour */ }
  });
})();
</script>
"""


def _embeddable_report(html: str) -> str:
    """The report document plus the TOC-navigation script, for the report frame.

    Injected here and not in `reporting.html_renderer` so the downloadable
    `final_report.html` artifact stays free of Streamlit-specific script.
    """
    if "</body>" not in html:
        return html + _TOC_SCRIPT
    return html.replace("</body>", _TOC_SCRIPT + "</body>", 1)


def _embed_report(html: str) -> None:
    """Show the report inline, sized to its content.

    `st.iframe` (Streamlit 1.6x) sizes the element container from the measured
    document. On older Streamlit — `pyproject` allows `>=1.36` — fall back to the
    fixed-height component, which keeps its own inner scrollbar but never
    overlaps the surrounding layout.
    """
    embeddable = _embeddable_report(html)
    if hasattr(st, "iframe"):
        st.iframe(embeddable, height="content")
    else:
        st.components.v1.html(embeddable, height=1100, scrolling=True)


def _source_links_markdown(items: list[dict]) -> str:
    """A prominent, clickable list of every source with a URL.

    The report table already links sources, but those cells sit inside a wide,
    horizontally-scrolling table and are easy to miss. This surfaces the same
    URLs as big, obvious markdown links — Streamlit opens external links in a new
    tab, so following a source never navigates away from the run.
    """
    lines: list[str] = []
    for it in items:
        url = it.get("source_url")
        if not url:
            continue
        eid = it.get("evidence_id", "")
        name = it.get("source_name", "來源")
        fact = it.get("normalized_fact") or it.get("content_reference") or ""
        # For news the headline is the meaningful anchor; for market/social the
        # source name is, with the fact as trailing context.
        if it.get("source_type") == "news" and fact:
            label = f"{fact} — {name}"
        else:
            label = f"{name}{f' — {fact}' if fact else ''}"
        lines.append(f"- `{eid}` · [{label}]({url})")
    return "\n".join(lines)


def _render_result(view: dict, bars_by_asset: dict | None = None) -> None:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Run mode", f"{view['run_mode_icon']} {view['run_mode_label']}")
    m2.metric("執行狀態", f"{view['terminal_icon']} {view['terminal_label']}")
    m3.metric("證據筆數", view["evidence_count"])
    m4.metric("信心", view["confidence"].upper())
    st.caption(f"分析編號：{view['run_id']}")

    if view["insufficient"]:
        st.warning("本次資料不足，以下內容僅呈現已驗證資訊，不形成方向性結論。", icon="⚠️")

    # Trust funnel: how scattered evidence distils into few independent voices.
    raw_ledger = _artifact_text(view, "evidence.json")
    if raw_ledger:
        f = trust_funnel(json.loads(raw_ledger))
        st.subheader("信任漏斗(多源資訊的信任提煉)")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("證據(去重後)", f["evidence_count"])
        g2.metric("來源類型", f["source_type_count"], help="、".join(f["source_types"]) or "—")
        g3.metric("獨立來源群", f["independence_group_count"], help="轉載/同源已併為同一群")
        g4.metric("矛盾訊號", f["conflict_count"])
        mix = f["reliability_mix"]
        st.caption(
            f"可信度組成 — 🟢 high {mix['high']}　·　🟡 medium {mix['medium']}　·　⚪ low {mix['low']}"
        )
        st.progress(
            (f["independence_group_count"] / f["evidence_count"]) if f["evidence_count"] else 0.0,
            text="獨立性:獨立來源群 / 證據筆數(越高代表越不是轉載堆疊)",
        )

        # Cross-source triangulation (Gold-Plan G2): market anomaly days that
        # independent research evidence corroborates around the same date.
        # Needs the run's own bars (not just evidence.json), so it silently
        # skips rather than errors when bars_by_asset is empty (e.g. a run
        # whose pipeline never exposed last_bars_by_asset).
        if bars_by_asset:
            tri = triangulation_view(json.loads(raw_ledger), bars_by_asset)
            any_available = any(a["available"] for a in tri.values())
            if any_available:
                st.subheader("跨源三角驗證(市場異動 × 獨立研究)")
                for asset, asset_view in tri.items():
                    if not asset_view["available"]:
                        st.caption(f"{asset}：歷史資料不足，無法計算異動日（{asset_view['reason']}）")
                        continue
                    events = asset_view["events"]
                    if not events:
                        st.caption(f"{asset}：本次分析期間無顯著市場異動日。")
                        continue
                    for event in events[:5]:
                        icon = "🟢" if event["strength"] >= 2 else "⚪"
                        st.markdown(f"{icon} **{asset} {event['day']}** — {event['note']}")
                        if event["corroborating_evidence_ids"]:
                            st.caption("佐證：" + "、".join(f"`{eid}`" for eid in event["corroborating_evidence_ids"]))

    # Report / Evidence / Execution Log as three tabs (spec §3.2 S3).
    tab_report, tab_evidence, tab_log = st.tabs(["📄 報告", "🧾 證據來源", "🪵 執行紀錄"])
    with tab_report:
        st.caption("完整研究報告")
        html_report = _artifact_text(view, "final_report.html")
        if html_report:
            _embed_report(html_report)
        else:
            st.markdown(view["report_markdown"] or "_(無)_")
    with tab_evidence:
        raw = _artifact_text(view, "evidence.json")
        if raw:
            ledger = json.loads(raw)
            links_md = _source_links_markdown(ledger.get("items", []))
            if links_md:
                st.markdown("**🔗 來源連結(點擊開新分頁,可追溯每筆證據)**")
                st.markdown(links_md)
            with st.expander("檢視完整證據資料"):
                st.json(ledger)
        else:
            st.write("_(無 evidence.json)_")
    with tab_log:
        raw = _artifact_text(view, "execution_log.jsonl")
        raw_ledger_text = _artifact_text(view, "evidence.json")
        if raw:
            judgment = agent_judgment_view(raw, json.loads(raw_ledger_text) if raw_ledger_text else {})
            if judgment["plan_decision"] or judgment["degradation_count"]:
                st.subheader("Agent 判斷(這次為什麼跑這些來源)")
                if judgment["plan_decision"]:
                    st.markdown(f"🧭 {judgment['plan_decision']}")
                if judgment["degradation_messages"]:
                    with st.expander(f"降級/資料缺口揭露({judgment['degradation_count']})"):
                        for msg in judgment["degradation_messages"]:
                            st.caption(f"- {msg}")
                if judgment["conflict_count"]:
                    st.caption(f"⚠️ 偵測到 {judgment['conflict_count']} 筆矛盾證據，詳見報告第 5 段。")
        st.code(raw or "（目前沒有執行紀錄）", language="json")

    st.subheader("下載研究資料")
    dl = st.columns(len(ARTIFACT_ORDER))
    for col, name in zip(dl, ARTIFACT_ORDER):
        label = ARTIFACT_LABELS.get(name, name)
        raw = _artifact_text(view, name)
        if raw is not None:
            col.download_button(f"⬇️ {label}", raw, file_name=name, help=name)
        else:
            col.write(f"❌ {label}")

    # PDF (Task 20): additive, generated on demand from the same report text
    # already in final_report.md — not a fifth required artifact, not written
    # to the run directory, no re-summarization. A rendering failure must
    # never break the page; the four/five required artifacts above are
    # unaffected either way.
    if view["report_markdown"]:
        try:
            from hoya_agent.reporting.pdf_renderer import render_pdf

            pdf_bytes = render_pdf(view["report_markdown"])
            st.download_button(
                "⬇️ PDF 版報告（額外格式）",
                pdf_bytes,
                file_name="final_report.pdf",
                mime="application/pdf",
                help="final_report.pdf（衍生自同一份 final_report.md，非四項必要 artifacts 之一）",
            )
        except Exception:  # noqa: BLE001 - an optional export failing must not break the page
            st.caption("PDF 匯出目前無法產生（不影響其他 artifacts）。")

    if view["missing_artifacts"]:
        st.error("部分研究資料未能完整建立，請重新執行分析。")

    if view["degradation_notes"]:
        with st.expander("資料限制與處理說明"):
            st.info("本次分析包含資料或處理限制，詳情請參閱報告中的「限制與資料缺口」。")


# Editorial design tokens mirroring the P4 report prototype: serif display
# headings, mono uppercase labels, distillation-green accent on a warm paper
# ground. No webfont CDN (offline/Docker-safe) — system serif/mono fallbacks.
_THEME_CSS = """
<style>
:root{--ink:#151815;--muted:#767d75;--line:#d8d8cf;--green:#087f5b;--paper:#fffefa;
--serif:"Noto Serif TC","Source Han Serif TC",Georgia,serif;
--mono:ui-monospace,"Cascadia Mono",Consolas,monospace;}
.block-container{max-width:1160px;padding-top:2.2rem;}
h1,h2,h3{font-family:var(--serif)!important;letter-spacing:-.01em;color:var(--ink);}
h1{font-weight:650;}
/* uppercase mono eyebrows for section subheaders */
h3{border-left:3px solid var(--green);padding-left:.55rem;}
/* captions -> muted mono labels */
[data-testid="stCaptionContainer"]{font-family:var(--mono);color:var(--muted);letter-spacing:.02em;}
/* metrics -> paper cards with mono labels + serif values */
[data-testid="stMetric"]{background:var(--paper);border:1px solid var(--line);
border-radius:12px;padding:14px 16px;}
[data-testid="stMetricLabel"]{font-family:var(--mono);text-transform:uppercase;
letter-spacing:.06em;color:var(--muted);font-size:.72rem;}
/* smaller serif + allow wrap so long values (OFFICIAL / 完成(含降級)) show in full */
[data-testid="stMetricValue"]{font-family:var(--serif);font-size:1.5rem;line-height:1.2;
white-space:normal;overflow:visible;overflow-wrap:anywhere;}
[data-testid="stMetricValue"]>div{white-space:normal;overflow:visible;text-overflow:clip;}
/* primary action + tabs pick up the green accent */
.stButton>button,.stFormSubmitButton>button{border-radius:999px;font-weight:600;}
[data-baseweb="tab-list"]{gap:.4rem;}
hr{border-color:var(--line);}
</style>
"""


_MODE_OFFLINE_REHEARSAL = "離線 rehearsal(官方 CSV)"
_MODE_OFFLINE_DEMO = "離線 demo(官方 CSV)"
_MODE_LIVE = "即時 official(Binance + 情緒)"
_MODES = [_MODE_LIVE, _MODE_OFFLINE_REHEARSAL, _MODE_OFFLINE_DEMO]


def main() -> None:
    st.set_page_config(page_title="HOYA Market Agent", page_icon="🧾", layout="wide")
    st.markdown(_THEME_CSS, unsafe_allow_html=True)
    st.title("🧾 加密市場分析 Agent")
    st.caption("多源資訊的信任提煉 · 研究導向 · 非投資建議")

    running = st.session_state.get("_run_in_flight", False)
    with st.form("req"):
        c1, c2, c3, c4 = st.columns([1.7, 3.2, 1.9, 1.1])
        # Five-asset allowlist; 1–2 assets. Two assets triggers the cross-asset
        # comparison path (S9B / Task 12) — comparison questions need this.
        chosen = c1.multiselect(
            "幣種(1–2;選 2 個 = 跨幣比較)", [a.value for a in Asset], default=["BTC"], max_selections=2
        )
        question = c2.text_input("題目 / 問題", placeholder="例:BTC 過去兩週表現?/ ETH 與 BTC 相對強弱?")
        mode = c3.selectbox("模式", _MODES, index=0)
        # Disabled while a run is in flight so one submit == one ApplicationService call.
        submitted = c4.form_submit_button("執行分析", use_container_width=True, disabled=running)

    if submitted and running:  # a submit queued while the previous run was still executing
        st.warning("上一個分析仍在進行,已忽略重複的執行請求。")
    elif submitted and not chosen:
        st.warning("請至少選一個幣種。")
    elif submitted:
        assets = [Asset(a) for a in chosen]
        is_live = mode == _MODE_LIVE
        label = "即時分析中(Binance 現價 + 情緒 → 證據 → 報告)…" if is_live else "離線分析中(官方 CSV)…"
        st.session_state["_run_in_flight"] = True
        try:
            with st.status(label, expanded=True) as status:
                sink = _StreamlitProgress(status)
                if is_live:
                    summary, bars_by_asset = _run_live(assets, question, progress=sink)
                else:
                    run_mode = RunMode.demo if mode == _MODE_OFFLINE_DEMO else RunMode.rehearsal
                    summary, bars_by_asset = _run_offline(assets, question, run_mode, progress=sink)
                status.update(label="分析完成", state="complete", expanded=False)
        finally:
            st.session_state["_run_in_flight"] = False
        # Persist the rendered view. st.download_button reruns the whole script on
        # click; without this, the rerun sees submitted=False and the report would
        # vanish back to the initial screen. Rendering from session_state keeps the
        # same page (and its four download buttons) alive across download clicks.
        st.session_state["_last_view"] = summary_view(summary)
        st.session_state["_last_bars"] = bars_by_asset

    last_view = st.session_state.get("_last_view")
    if last_view is not None:
        _render_result(last_view, st.session_state.get("_last_bars") or {})
    elif not submitted:
        st.info(
            "選擇幣種並輸入研究型題目後，按「執行分析」。"
            "即時模式使用交易所與市場情緒資料；離線模式使用官方 CSV。"
        )


if __name__ == "__main__":
    main()
