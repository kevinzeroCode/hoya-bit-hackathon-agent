---
inclusion: always
---

# Product Steering

## Product Mission

HOYA Market Agent 是競賽導向的 Evidence-first 加密市場分析 prototype。它在現場接收未知問題與指定資產後，將分散來源整理為可追溯 Evidence Ledger，再以清楚分層的「事實 -> 推論 -> 結論」回答問題。

產品價值不是預測價格或堆疊 Agent 數量，而是在 15 分鐘限制內交付一份可驗證、可解釋、知道自己資料缺口的分析。

## Primary Users

- 競賽評審：需要快速確認多源取證、推理、矛盾處理、AWS 應用與完整 artifacts 是否真的運作。
- 加密市場資訊使用者：需要快速理解市場狀況、主要證據、反方訊號、信心、限制及後續觀察點。

## Core Product Promise

輸入自然語言問題與 BTC、ETH、SOL、BNB、XRP 中一至兩個資產後，產品應：

1. 依共同 UTC 時間基準取得並正規化證據。
2. 以 deterministic 工具計算所有市場數值。
3. 讓每個重要結論能回溯到 Evidence IDs 與來源。
4. 同時呈現支持與反對訊號，不隱藏 material conflict。
5. 在資料或服務失敗時產生誠實的 partial result，而不是編造答案。
6. 在第 13 分鐘前產出固定四項 artifacts，保留現場緩衝。

## MVP Product Shape

- 唯一承諾架構：H2-Lite bounded workflow。
- 預設使用流程：Planner -> Market Worker 與 Research Agent 並行 -> Evidence Processor -> Arbiter -> deterministic Renderer。
- Market Worker 不是 LLM agent；它是 deterministic Python 工具鏈。
- H3 Conditional Debate 只是預設關閉的 extension interface。未完成 rehearsal 並留下紀錄前，不得宣稱已實作或 live 啟用。
- UI 是實際可操作的 Streamlit 分析介面，不建立行銷 landing page。

## Product Priorities

依下列順序做取捨：

1. Evidence 可回溯與四項 artifacts 完整。
2. 15 分鐘內可預期完成與故障降級。
3. 繁體中文報告的可讀性與推理透明度。
4. 多源與 bounded specialists 的真實展示價值。
5. UI polish 與非核心擴充。

功能與穩定性衝突時，優先完成 H2-Lite、fallback、artifacts 與 Demo；H3、額外 adapters、S3、CloudWatch、ECS 必須讓位。

## Success Criteria

- 五個支援資產均能完成 fixture 端到端流程。
- 正常 run 以三種 source types、三個獨立上游及一個第一手／官方來源為目標。
- 所有 conclusion 可回溯至 Evidence，或明確標示 insufficient data。
- 單一取證分支、外部來源或 Arbiter 失敗時仍有降級報告與四項 artifacts。
- UI 能顯示 stage、來源成功／失敗、run mode、降級狀態及 artifacts。
- official、rehearsal、demo 三種模式不會被混淆。

## Report and UX Voice

- 所有使用者可見報告與核心 UI 文案使用繁體中文。
- 先直接回答題目，再提供市場範圍、證據、反方訊號、推論、結論、信心、限制與 invalidation conditions。
- 語氣必須審慎、具體、可驗證。資料不足就明說「目前無法可靠判定」。
- confidence 只使用 `high|medium|low` 與理由，不包裝成未校準的精確機率。
- recorded fallback、cache、stale、intraday snapshot、來源切換及 partial result 必須在使用者可見處誠實標示。
- 不提供買賣、加減倉、資產配置、下單或個人化投資建議。

## Product Non-Goals

- 自動交易、下單或個人化投資顧問。
- 宣稱可準確預測短期價格。
- 自由循環的 Agent swarm 或多輪辯論。
- LLM 自行產生市場數值。
- 訓練或微調大型模型。
- 五條鏈的完整鏈上 indexer。
- 帳號、付款與一般 SaaS 權限系統。
- 近似內容相似度模型、動態 reliability 模型、per-agent token/tool-call 自建計數器。
- 以額外來源數量或視覺效果犧牲穩定性與可回溯性。

## Scope Control

任何新需求在加入前都要回答：

1. 是否直接提高主題切合度、技術可行性或完成度？
2. 是否會危及第 13 分鐘 artifacts deadline？
3. 是否已有核准 schema、fallback 與可驗收測試？
4. 是否屬於已列為 stretch 或非目標的範圍？

若答案顯示會擴大兩天 MVP，維持未實作並記入未來工作，不得默默加入承諾。
