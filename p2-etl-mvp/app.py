"""前端(Streamlit)：沿用 P4 報告模板(task/7)的風格，上面加一個「需求對話框」。

    streamlit run app.py

使用者在對話框下需求(選幣種 + 輸入題目 + 執行)→ pipeline.collect_evidence()
→ 把真實資料灌進 P4 的 HTML 報告模板 → 直接嵌入顯示(同一套風格)。

界線(誠實)：報告中「方向性結論 / 推理鏈 / 正反立場」由 P3 推理層產生，模板已標「待 P3」；
本頁只填 P2 能 deterministic 提供的部分。正式產品 UI 由 P4；本頁為 P2 層互動 demo。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from evidence.evidence_json import build_evidence_payload
from pipeline import collect_evidence
from render_report import build_values, render

UTC = timezone.utc
ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"]
_TEMPLATE = Path(__file__).resolve().parent / "render" / "report_template.html"

st.set_page_config(page_title="HOYA 加密市場分析 Agent", page_icon="🧾", layout="wide")

# 讓 Streamlit 外框收斂，聚焦在對話框 + 報告
st.markdown(
    "<style>.block-container{padding-top:1.6rem;max-width:1160px}"
    "header[data-testid='stHeader']{background:transparent}</style>",
    unsafe_allow_html=True,
)

# ── 需求對話框(唯一新增的互動元件) ─────────────────────────────
st.markdown("### 🧾 加密市場分析 Agent — 下需求")
with st.form("req"):
    c1, c2, c3, c4 = st.columns([1, 4, 1.2, 1.2])
    asset = c1.selectbox("幣種", ASSETS, index=0)
    question = c2.text_input("題目 / 問題", placeholder="例：BTC 過去兩週表現與短期方向？")
    offline = c3.checkbox("離線模式", value=False, help="只用官方 CSV，不打網路/LLM")
    submitted = c4.form_submit_button("執行分析", use_container_width=True)

if not submitted:
    st.info("在上方對話框選幣種、輸入題目，按「執行分析」。線上模式會抓多源即時資料 + LLM 語意抽取。")
    st.stop()

with st.spinner(f"蒐集 {asset} 多源證據並產生報告中…"):
    bundle = collect_evidence(asset, offline=offline)
    values = build_values({
        "asset": bundle.asset, "as_of": bundle.as_of, "bars": bundle.bars,
        "regime": bundle.regime, "ledger": bundle.ledger,
        "notes": bundle.notes, "live_ok": bundle.live_ok, "question": question,
    })
    report_html = render(values, _TEMPLATE.read_text(encoding="utf-8"))

# ── 沿用 P4 模板風格：直接嵌入渲染好的報告 ──────────────────────
if question:
    st.caption(f"題目：{question}　·　LLM：{bundle.provider}　·　"
               f"證據 {len(bundle.ledger.items)} 筆／獨立群 {bundle.ledger.independence_group_count}")
components.html(report_html, height=1600, scrolling=True)

# ── 下載比賽固定 artifact ───────────────────────────────────────
payload = build_evidence_payload(
    bundle.ledger, asset=asset, analysis_as_of=bundle.as_of,
    run_id=f"ui-{asset.lower()}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
    run_mode="rehearsal", llm_provider=bundle.provider,
)
st.download_button("⬇️ 下載 evidence.json", json.dumps(payload, ensure_ascii=False, indent=2),
                   file_name="evidence.json", mime="application/json")
