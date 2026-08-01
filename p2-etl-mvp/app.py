"""前端(Streamlit)：沿用 P4 報告模板(task/7)風格 + 需求對話框。

    streamlit run app.py

- 選 1 個幣種 → 灌真實資料進 P4 報告模板,嵌入顯示(同一套風格)。
- 選 2 個幣種 → 輕量跨幣比較(相對報酬/相關性/beta;不比 base volume)。

界線(誠實)：方向性結論 / 推理由 P3 產生(報告已標「待 P3」);本系統不預測價格。
正式產品 UI 由 P4;本頁為 P2 層互動 demo。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from evidence.evidence_json import build_evidence_payload
from pipeline import collect_comparison, collect_evidence
from render_report import build_values, render, render_comparison

UTC = timezone.utc
ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"]
_TEMPLATE = Path(__file__).resolve().parent / "render" / "report_template.html"
_REGIME_ZH = {"trending_up": "趨勢向上", "trending_down": "趨勢向下", "range_bound": "區間盤整",
              "high_volatility": "高波動", "mixed": "方向不明"}
_REL_ZH = {"high": "🟢 high", "medium": "🟡 medium", "low": "⚪ low"}


def _regime(r) -> str:
    return _REGIME_ZH.get(getattr(r, "label", ""), "—")


def _ledger_rows(items) -> list[dict]:
    return [{
        "ID": it.evidence_id, "幣": it.asset or "—", "可信度": _REL_ZH.get(it.reliability, it.reliability),
        "類型": it.source_type, "來源": it.source_name or "—", "事實": it.normalized_fact,
    } for it in items]


st.set_page_config(page_title="HOYA 加密市場分析 Agent", page_icon="🧾", layout="wide")
st.markdown(
    "<style>.block-container{padding-top:1.6rem;max-width:1160px}"
    "header[data-testid='stHeader']{background:transparent}</style>",
    unsafe_allow_html=True,
)

st.markdown("### 🧾 加密市場分析 Agent — 下需求")
with st.form("req"):
    c1, c2, c3, c4 = st.columns([1.8, 4, 1.1, 1.1])
    assets = c1.multiselect("幣種（1–2 個；選 2 個＝比較）", ASSETS, default=["BTC"], max_selections=2)
    question = c2.text_input("題目 / 問題", placeholder="例：BTC 過去兩週表現？／ ETH 與 BTC 相對強弱？")
    offline = c3.checkbox("離線模式", value=False, help="只用官方 CSV，不打網路/LLM")
    submitted = c4.form_submit_button("執行分析", use_container_width=True)

if not submitted:
    st.info("選 1 個幣種看單幣報告，或選 2 個做跨幣比較；輸入題目後按「執行分析」。")
    st.stop()
if not assets:
    st.warning("請至少選一個幣種。")
    st.stop()

# ── 單幣：沿用 P4 報告模板 ──────────────────────────────────────
if len(assets) == 1:
    asset = assets[0]
    with st.spinner(f"蒐集 {asset} 多源證據並產生報告中…"):
        bundle = collect_evidence(asset, offline=offline)
        values = build_values({
            "asset": bundle.asset, "as_of": bundle.as_of, "bars": bundle.bars,
            "regime": bundle.regime, "ledger": bundle.ledger,
            "notes": bundle.notes, "live_ok": bundle.live_ok, "question": question,
        })
        report_html = render(values, _TEMPLATE.read_text(encoding="utf-8"))
    if question:
        st.caption(f"題目：{question}　·　LLM：{bundle.provider}　·　"
                   f"證據 {len(bundle.ledger.items)} 筆／獨立群 {bundle.ledger.independence_group_count}")
    components.html(report_html, height=1600, scrolling=True)
    payload = build_evidence_payload(
        bundle.ledger, asset=asset, analysis_as_of=bundle.as_of,
        run_id=f"ui-{asset.lower()}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
        run_mode="rehearsal", llm_provider=bundle.provider)

# ── 雙幣：輕量跨幣比較 ──────────────────────────────────────────
else:
    a, b = assets
    with st.spinner(f"比較 {a} vs {b} …"):
        cb = collect_comparison(a, b, offline=offline)
        report_html = render_comparison(cb, _TEMPLATE.read_text(encoding="utf-8"))
    if question:
        st.caption(f"題目：{question}　·　{a} 市場狀態 {_regime(cb.regime_a)}／{b} {_regime(cb.regime_b)}"
                   f"　·　LLM：{cb.provider}　·　合併證據 {len(cb.ledger.items)} 筆")
    components.html(report_html, height=1600, scrolling=True)
    payload = build_evidence_payload(
        cb.ledger, asset=f"{a}-vs-{b}", analysis_as_of=cb.as_of,
        run_id=f"ui-cmp-{a.lower()}-{b.lower()}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
        run_mode="rehearsal", llm_provider=cb.provider)

st.download_button("⬇️ 下載 evidence.json", json.dumps(payload, ensure_ascii=False, indent=2),
                   file_name="evidence.json", mime="application/json")
