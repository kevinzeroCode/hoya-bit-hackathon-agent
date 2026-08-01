"""前端(Streamlit)：P2 資料/證據層互動介面。

    streamlit run app.py

使用者在此下需求(選幣種 + 輸入題目 + 執行)→ 背後跑 pipeline.collect_evidence()
→ 顯示統一證據帳本、市場狀態、信任計數,並可下載 evidence.json。

界線(誠實)：本頁呈現 P2 產出的「可回溯證據」與 deterministic 市場狀態；
**方向性結論與推理判斷由 P3 推理層產生**,此處標示為待接,不由 P2 編造。
正式產品 UI 由 P4 負責;本頁為 P2 層的互動檢視/demo。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from evidence.evidence_json import build_evidence_payload
from pipeline import collect_evidence

UTC = timezone.utc
ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"]
_REGIME_ZH = {"trending_up": "趨勢向上", "trending_down": "趨勢向下", "range_bound": "區間盤整",
              "high_volatility": "高波動", "mixed": "方向不明"}
_REL_ZH = {"high": "🟢 high", "medium": "🟡 medium", "low": "⚪ low"}

st.set_page_config(page_title="HOYA 加密市場分析 · 證據層", page_icon="🧾", layout="wide")
st.title("🧾 加密市場分析 Agent — 證據層")
st.caption("多源資訊的信任提煉：多源 → 可回溯證據 → 交 P3 推理。研究導向，非投資建議。")

# ── 使用者下需求 ────────────────────────────────────────────────
with st.form("req"):
    c1, c2, c3 = st.columns([1, 3, 1])
    asset = c1.selectbox("幣種", ASSETS, index=0)
    question = c2.text_input("題目 / 問題", placeholder="例：BTC 過去兩週表現與短期方向？")
    offline = c3.checkbox("離線(只用官方 CSV)", value=False)
    submitted = st.form_submit_button("執行分析", use_container_width=True)

if not submitted:
    st.info("選幣種、輸入題目，按「執行分析」。線上模式會抓多源即時資料 + LLM 語意抽取(需網路/金鑰)。")
    st.stop()

with st.spinner(f"蒐集 {asset} 多源證據中…"):
    bundle = collect_evidence(asset, offline=offline)

led = bundle.ledger
rel = {"high": 0, "medium": 0, "low": 0}
for it in led.items:
    rel[it.reliability] = rel.get(it.reliability, 0) + 1

# ── 題目回顯 + 界線揭露 ─────────────────────────────────────────
if question:
    st.markdown(f"**題目：** {question}")
st.warning("方向性結論與推理判斷 = **P3 推理層**產生（本頁不編造）。以下為 P2 的 deterministic 證據與市場狀態。", icon="⚠️")

# ── 摘要指標 ────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("市場狀態", _REGIME_ZH.get(getattr(bundle.regime, "label", ""), "—"))
m2.metric("證據筆數", f"{len(led.items)}", help=f"去重掉 {led.dropped_duplicates}")
m3.metric("獨立來源群", f"{led.independence_group_count}")
m4.metric("可信度組成", f"H{rel['high']} · M{rel['medium']} · L{rel['low']}")
st.caption(f"分析時點 {bundle.as_of} UTC｜LLM：{bundle.provider}｜"
           + "｜".join(bundle.source_lines))

# ── 統一證據帳本 ────────────────────────────────────────────────
st.subheader("統一證據帳本(可回溯)")
rows = [{
    "ID": it.evidence_id,
    "可信度": _REL_ZH.get(it.reliability, it.reliability),
    "類型": it.source_type,
    "來源": it.source_name or "—",
    "事實": it.normalized_fact,
    "時間": it.published_at.date().isoformat() if it.published_at else "—",
} for it in led.items]
st.dataframe(rows, use_container_width=True, hide_index=True, height=460)

# ── 下載 artifact ───────────────────────────────────────────────
payload = build_evidence_payload(
    led, asset=asset, analysis_as_of=bundle.as_of,
    run_id=f"ui-{asset.lower()}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
    run_mode="rehearsal", llm_provider=bundle.provider,
)
st.download_button("⬇️ 下載 evidence.json", json.dumps(payload, ensure_ascii=False, indent=2),
                   file_name="evidence.json", mime="application/json")

# ── 揭露 ────────────────────────────────────────────────────────
if bundle.notes:
    with st.expander(f"揭露(degradation) · {len(bundle.notes)} 則"):
        for n in bundle.notes:
            st.write("•", n)
