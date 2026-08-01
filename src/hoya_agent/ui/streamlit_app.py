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
from hoya_agent.ui.presenter import summary_view, trust_funnel  # noqa: E402

UTC = timezone.utc
# Organizer CSV ends 2026-05-31; Bronze replays that frozen cutoff (offline).
BRONZE_CUTOFF = datetime(2026, 5, 31, tzinfo=UTC)
ARTIFACT_ORDER = ("final_report.md", "evidence.json", "execution_log.jsonl", "run_config.json")


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


def _run_offline(assets: list[Asset], question: str, run_mode: RunMode, progress=None) -> object:
    now = datetime.now(UTC)
    request = build_request(
        question=question or "市場狀況與資料整合",
        assets=assets,
        run_mode=run_mode,
        now=now,
        run_id_suffix="ui",
        analysis_as_of=BRONZE_CUTOFF,
    )
    service = ApplicationService(
        artifact_root=Path(tempfile.mkdtemp(prefix="hoya-ui-")),
        clock=SystemClock(),
        pipeline=OrganizerCsvPipeline(analysis_date=BRONZE_CUTOFF.date()),
        configured_sources=["public_market_data"],
    )
    return asyncio.run(service.run(request, progress=progress))


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


def _live_pipeline(now):
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
            return build_live_pipeline(clock=SystemClock(), llm=llm, analysis_as_of=now), True
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


def _run_live(assets: list[Asset], question: str, progress=None) -> object:
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
    pipeline, with_bedrock = _live_pipeline(now)
    sources = ["binance_spot", "fear_greed"] + (["bedrock"] if with_bedrock else [])
    service = ApplicationService(
        artifact_root=Path(tempfile.mkdtemp(prefix="hoya-live-")),
        clock=SystemClock(),
        pipeline=pipeline,
        configured_sources=sources,
    )
    return asyncio.run(service.run(request, progress=progress))


def _artifact_text(view: dict, name: str) -> str | None:
    path = view["artifacts"].get(name)
    if path and Path(path).exists():
        return Path(path).read_text(encoding="utf-8")
    return None


def _render_result(view: dict) -> None:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Run mode", f"{view['run_mode_icon']} {view['run_mode_label']}")
    m2.metric("執行狀態", f"{view['terminal_icon']} {view['terminal_label']}")
    m3.metric("證據筆數", view["evidence_count"])
    m4.metric("信心", view["confidence"].upper())
    st.caption(f"run_id: {view['run_id']}　·　artifact_dir: {view['artifact_dir']}")
    # H3 multi-agent debate is out of Bronze scope; make that explicit in the UI.
    st.caption("🚫 H3 多代理人辯論:未實作(Bronze 範圍外,Future Work)")

    if view["insufficient"]:
        st.warning("此增量無 Arbiter,依規格輸出 deterministic「資料不足」報告(方向性結論待 P3)。", icon="⚠️")

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

    # Report / Evidence / Execution Log as three tabs (spec §3.2 S3).
    tab_report, tab_evidence, tab_log = st.tabs(["📄 報告", "🧾 Evidence Ledger", "🪵 Execution Log"])
    with tab_report:
        st.caption("deterministic Renderer;已過投資建議 lint")
        st.markdown(view["report_markdown"] or "_(無)_")
    with tab_evidence:
        raw = _artifact_text(view, "evidence.json")
        if raw:
            st.json(json.loads(raw))
        else:
            st.write("_(無 evidence.json)_")
    with tab_log:
        raw = _artifact_text(view, "execution_log.jsonl")
        st.code(raw or "(無 execution_log.jsonl)", language="json")

    st.subheader("四個固定 artifact")
    dl = st.columns(len(ARTIFACT_ORDER))
    for col, name in zip(dl, ARTIFACT_ORDER):
        raw = _artifact_text(view, name)
        if raw is not None:
            col.download_button(f"⬇️ {name}", raw, file_name=name)
        else:
            col.write(f"❌ {name}")
    if view["missing_artifacts"]:
        st.error(f"缺少 artifact:{view['missing_artifacts']}")

    if view["degradation_notes"]:
        with st.expander(f"揭露(degradation) · {len(view['degradation_notes'])}"):
            for note in view["degradation_notes"]:
                st.write("•", note)


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
    st.caption("多源資訊的信任提煉 · 研究導向,非投資建議 · 即時(交易所+情緒)或離線(官方 CSV)")

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

    if not submitted:
        st.info(
            "選幣種、輸入研究型題目,按「執行分析」。**即時**打交易所現價 + 恐懼貪婪指數(免金鑰);"
            "**離線**只用官方 CSV。兩者皆產出四個固定 artifact。"
        )
        return
    if running:  # a submit queued while the previous run was still executing
        st.warning("上一個分析仍在進行,已忽略重複的執行請求。")
        return
    if not chosen:
        st.warning("請至少選一個幣種。")
        return

    assets = [Asset(a) for a in chosen]
    is_live = mode == _MODE_LIVE
    label = "即時分析中(Binance 現價 + 情緒 → 證據 → 報告)…" if is_live else "離線分析中(官方 CSV)…"
    st.session_state["_run_in_flight"] = True
    try:
        with st.status(label, expanded=True) as status:
            sink = _StreamlitProgress(status)
            if is_live:
                summary = _run_live(assets, question, progress=sink)
            else:
                run_mode = RunMode.demo if mode == _MODE_OFFLINE_DEMO else RunMode.rehearsal
                summary = _run_offline(assets, question, run_mode, progress=sink)
            status.update(label="分析完成", state="complete", expanded=False)
    finally:
        st.session_state["_run_in_flight"] = False

    _render_result(summary_view(summary))


if __name__ == "__main__":
    main()

