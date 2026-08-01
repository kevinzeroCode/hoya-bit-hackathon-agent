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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.clock import SystemClock
from hoya_agent.models import Asset, RunMode
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from hoya_agent.ui.presenter import summary_view

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


def main() -> None:
    st.set_page_config(page_title="HOYA Market Agent — Bronze", page_icon="🧾", layout="wide")
    st.title("🧾 加密市場分析 Agent")
    st.caption("多源資訊的信任提煉 · Bronze(離線、deterministic、無 Bedrock/AWS)· 研究導向,非投資建議")

    running = st.session_state.get("_run_in_flight", False)
    with st.form("req"):
        c1, c2, c3, c4 = st.columns([1.8, 4, 1.2, 1.1])
        # Five-asset allowlist, single-asset Bronze path. The second-asset opt-in
        # (dual comparison) belongs to Task 12 and stays disabled until it lands.
        asset = c1.selectbox("幣種(單幣;雙幣比較待 Task 12)", [a.value for a in Asset], index=0)
        assets = [asset]
        question = c2.text_input("題目 / 問題", placeholder="例:BTC 過去兩週表現?")
        mode = c3.selectbox("Run mode", ["rehearsal", "demo"], index=0)
        # Disabled while a run is in flight so one submit == one ApplicationService call.
        submitted = c4.form_submit_button("執行分析", use_container_width=True, disabled=running)

    if not submitted:
        st.info("選 1–2 個幣種、輸入題目,按「執行分析」。Bronze 為離線 rehearsal/demo,產出四個固定 artifact。")
        return
    if running:  # a submit queued while the previous run was still executing
        st.warning("上一個分析仍在進行,已忽略重複的執行請求。")
        return
    if not assets:
        st.warning("請至少選一個幣種。")
        return

    st.session_state["_run_in_flight"] = True
    try:
        with st.status("離線分析中(官方 CSV → 證據 → 報告 → artifacts)…", expanded=True) as status:
            summary = _run_offline(
                [Asset(a) for a in assets], question, RunMode(mode), progress=_StreamlitProgress(status)
            )
            status.update(label="分析完成", state="complete", expanded=False)
    finally:
        st.session_state["_run_in_flight"] = False

    _render_result(summary_view(summary))


if __name__ == "__main__":
    main()

