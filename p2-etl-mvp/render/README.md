# P2 → 報告本地整合（presenter 原型）

把 **P2 的真實 pipeline 輸出**灌進 **P4 的 Task-7 報告模板**，本地產出填好數字的報告。
這是 **presenter 原型，不是 shared contract**——不修改任何 models／pipeline stage，
符合 `docs/rehearsals/ui-report-template.md`「UI 只吃 presenter 輸出」的規則。

## 用法
```bash
python render_report.py BTC          # 或 ETH/SOL/BNB/XRP
# 產出：render/out/hoya-report-<ASSET>.html（用瀏覽器開）
```
離線也能跑（只填市場層）；有網路則補 OKX／新聞／社群／情緒；設 `OPENAI_API_KEY` 可再加 LLM。

## 檔案
- `render_report.py`（在 repo 根的 p2-etl-mvp/）— 跑 P2 pipeline → 填模板 → 輸出 HTML
- `render/report_template.html` — P4 模板本地副本（源自分支 `task/7-html-report-template`）
- `render/out/` — 產出（generated）

## 哪些是真的（P2）、哪些標「待 P3」
| 報告區塊 | 來源 |
|---|---|
| 市場圖表（收盤＋7日均線） | ✅ deterministic（近 14 日真收盤） |
| Market Regime／Confidence 上限 | ✅ `classify_regime` ＋ `max_confidence` |
| Evidence Ledger 表 | ✅ 真列（id／來源／fetched_at／content_reference／可信度） |
| 信任評分（獨立性／多樣性／可信度組成／時效性） | ✅ 真計數 |
| Coverage／Source Diversity | ✅ 真 |
| 方向性結論／推理鏈／正反立場／一致性 | ⏳ **標「待 P3 推理層」，不假造** |
| Run badge | REHEARSAL（真資料，非 official） |

> 界線：P2 只填 deterministic／可回溯的部分；需要「判斷」的欄位誠實留給 P3。
> 正式整合時，presenter 應改吃 P1 的 ApplicationService 輸出，而非直接 import adapters。
