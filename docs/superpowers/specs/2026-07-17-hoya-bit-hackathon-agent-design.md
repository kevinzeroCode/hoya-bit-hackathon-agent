# HOYA BIT 加密市場分析 AI Agent - Approved Spec

> 狀態：核准版 v1.0（2026-07-17）。經外部 CLI 架構與範圍審查（第 21 節）與團隊決策後核准實作。Draft 審查與修訂紀錄保留於第 21、23 節。
>
> 日期：2026-07-17
>
> 架構定案：H2-Lite（Planner → Market Worker + Research Agent → Evidence Processor → Arbiter → Renderer）。H3 為 extension interface，預設關閉、非 MVP。

## 1. 專案摘要

本專案要在兩天內完成一個競賽導向的加密市場分析 AI Agent prototype。系統在比賽現場接收隨機題目與指定幣種後，必須在 15 分鐘內整合多源資料，產出可解釋、可回溯且明確說明不確定性的市場分析。內部目標是在第 12 分鐘完成分析，第 13 分鐘前完成 artifacts，保留至少 2 分鐘現場緩衝。

目標不是預測價格、提供買賣建議、摘要單篇新聞或展示複雜 Agent 數量，而是用穩定的 Evidence-first 流程回答指定問題，並交付完整證據鏈與執行紀錄。

## 2. 已確認背景

### 2.1 競賽條件

- 幣種池：BTC、ETH、SOL、BNB、XRP。
- 現場才公布指定題目與幣種。
- 正式執行最多 15 分鐘，原則上只有一次執行機會。
- 題型可能包含多源整合、假設驗證，以及文件範例中的跨幣比較。
- 主辦方提供五個幣種 2021-06-01 至 2026-05-31 的 Daily OHLCV CSV。
- 新聞、公告、鏈上、社群、總體經濟等資料由參賽者自行取得。

### 2.2 必要交付物

1. Final Report
2. Evidence List
3. Execution Log
4. Source / Config

決賽另需提案簡報、AWS 架構圖、Live Demo 或完整錄影，以及 GitHub repository。

### 2.3 評分優先順序

| 項目 | 權重 | 本專案對策 |
|---|---:|---|
| 主題切合度 | 30% | 多源、證據回溯、矛盾處理、信心與限制 |
| 技術可行性 | 25% | bounded workflow、deadline、降級、完整 artifacts |
| 商業應用性 | 20% | 將分散資訊轉為可快速閱讀且可採信的分析 |
| 創意度 | 15% | Evidence Ledger、claim-level 立場對應與矛盾處理 |
| 完成度 | 10% | 穩定 Demo、四項交付物、清楚 UI |
| AWS Kiro 加分 | +10% | 使用 Kiro Spec、Steering 與 Tasks 進行開發 |

### 2.4 口徑與預設解讀

以下解讀為開工預設，不因等待主辦方回覆而阻塞 Day 1；其中標注項目另列入第 20 節「待主辦方確認」。

- 「三個獨立上游來源」採 **per-run** 口徑；主辦方 CSV 計為一個 `independence_group`。（待主辦方確認口徑）
- 「第一手或官方來源」定義為**原始資料產生者**：市場數據之於交易所 API、公告之於專案官方頻道、主辦方 CSV 之於共同基準資料。（此定義是否被評審接受，待主辦方確認）
- `assets` 輸入與題目文字提及的幣種不一致時，以 `assets` 欄位為準，Planner 記錄 warning 並寫入 Execution Log。
- 15 分鐘計時邊界（是否含輸入題目與評審檢視 artifacts）待主辦方確認；內部一律以 run 開始起算並以第 13 分鐘完成 artifacts 為目標。
- 主辦方 CSV 的 metadata 僅標示 `public_market_data`，**不得推定其上游為任何特定交易所**；live API 與 CSV 之間視為來源切換並依 10.1 節處理。

## 3. 團隊與時程

- 團隊：4 位具資工背景的 junior developer。
- 開發時間：2 天。
- 可處理 Python、前端，以及依 AI 指示完成 ECR、EC2 等 AWS 部署。
- 策略：先完成最薄的端到端 vertical slice，再平行補強；第二天下半場凍結功能。

## 4. 產品目標

### 4.1 核心使用者

- 競賽評審：需要快速確認系統是否真的完成多源分析、推理與證據回溯。
- 加密市場使用者：需要在大量雜訊中快速理解目前狀況、主要依據、反方訊號及限制。

### 4.2 核心價值

輸入一個未知題目與指定資產後，系統將不同來源的事實整理成 Evidence Ledger，建立 claim-level 對應，再產出「事實 -> 推論 -> 結論」清楚分層的報告。

### 4.3 成功定義

- 任一幣種可在第 13 分鐘前完成端到端分析與 artifacts。
- 關鍵結論皆可追溯至 Evidence List。
- 資料不足、來源失效或訊號矛盾時，系統會降級並明確揭露，不會編造答案。
- 某個取證分支失敗不會造成整次執行失敗。
- Demo 能清楚呈現執行進度、證據、推理與最終 artifacts。
- 正式執行不會把 fixture、預存答案或舊報告冒充為本次分析。

## 5. 範圍

### 5.1 MVP 必做

- 接收自然語言題目與指定幣種。
- 解析題型、分析時間範圍及需要的證據類型。
- 計算主辦方 OHLCV 的可重現市場指標（deterministic 程式碼 + 參數記錄於 artifacts）。
- 正常情況取得至少三種 source types、三個獨立上游來源，其中至少一個為第一手或官方來源（口徑見 2.4）。
- 將來源正規化、去重並存入 Evidence Ledger。
- 區分支持、反對與中性證據。
- 產出分層 claims、信心、限制及可能推翻結論的條件。
- 輸出 Final Report、Evidence List、Execution Log、Config snapshot（固定檔名見 9.8）。
- 具備 timeout、retry、partial result 與 fallback（含 LLM 失敗時的 deterministic fallback report）。
- 提供簡潔的 web UI 與部署版本。
- 明確記錄 `analysis_as_of`、UTC 截點、資料新鮮度與完整／未完整 K 線狀態。

### 5.2 相容但非主展示流程

- UI 預設只選一個幣種。
- 內部輸入採 `assets: string[]`，允許 1 至 2 個幣種，以低成本涵蓋文件中的比較題型。
- 若最終確認正式題目只會有單一幣種，雙幣只保留資料契約相容性，不另做複雜 UI。

### 5.3 非目標

- 自動交易或下單。
- 明確買進、賣出或資產配置建議。
- 宣稱可準確預測短期價格。
- 訓練大型深度學習模型或微調 LLM。
- 實作可無限對話或自由循環的 Agent swarm。
- 為五條鏈各自建立完整鏈上 indexer。
- 建立一般消費產品所需的帳號、付款與權限系統。
- 近似重複偵測與內容相似度模型（去重僅做 `content_hash` 精確比對與 `independence_group` 網域歸群）。
- 動態可信度模型（reliability 僅使用 7.5 節靜態規則表）。
- Per-agent token 與 tool-call 次數的硬性計數 enforcement（僅使用 wall-clock timeout 與 LLM `max_tokens` 參數）。

### 5.4 Stretch（非兩天承諾）

- H3 Conditional Debate 實作（MVP 僅保留 extension interface，見 8.3）。
- 鏈上、宏觀、社群 context adapters。
- S3 artifact storage、CloudWatch logs、ECS 部署。

## 6. 輸入與輸出

### 6.1 Analysis Request

```json
{
  "question": "分析 BTC 過去兩週的市場狀況與主要風險",
  "assets": ["BTC"],
  "requested_at": "2026-07-17T06:00:00Z",
  "analysis_as_of": "2026-07-17T06:00:00Z",
  "deadline_seconds": 900,
  "run_mode": "official|rehearsal|demo",
  "enable_conditional_debate": false
}
```

- `analysis_as_of` 是所有市場、新聞與事件查詢的共同時間基準。**official mode 下由系統於 run 開始時凍結為當下 UTC 時間，不接受使用者自訂**；`rehearsal` 與 `demo` 模式可自訂以重現測試。
- Daily OHLCV 只可使用該時間點以前已完成的 UTC K 線；未完成的當日資料必須標示為 intraday snapshot，不得和完整日 K 混用。
- `enable_conditional_debate` 預設 `false`（H3 為 extension，見 8.3）。

### 6.2 Final Report 最低內容

1. 對指定問題的直接回答
2. 市場狀況與適用時間範圍
3. 已確認事實
4. 主要支持證據
5. 主要反方或矛盾證據
6. 從事實推導出的推論
7. 最終結論
8. 信心水準與原因
9. 已知限制與資料缺口
10. 可能推翻結論的條件
11. 後續觀察重點

- **報告語言：繁體中文。**
- 報告由 deterministic renderer 依 `AnalysisResult`（7.4 節）產出，不由 LLM 直接生成全文。
- 報告不得把 confidence 包裝成精確預測機率，除非該數值具有可驗證的校準方法。

## 7. Evidence 與 Claim 資料契約

### 7.1 Evidence Item

```json
{
  "evidence_id": "ev_001",
  "asset": "BTC",
  "source_type": "official|market|news|onchain|social|macro",
  "source_name": "source name",
  "source_url": "https://example.com/source",
  "published_at": "2026-07-17T04:00:00Z",
  "fetched_at": "2026-07-17T06:01:00Z",
  "query_or_parameters": "query, endpoint parameters, or CSV range",
  "content_reference": "short quotation, metric, range, or source summary",
  "normalized_fact": "A factual statement supported by the source",
  "reliability": "high|medium|low",
  "independence_group": "original publisher or upstream source id",
  "content_hash": "sha256 of normalized source content",
  "is_cached": false,
  "cache_time": null,
  "is_stale": false
}
```

`EvidenceItem` 描述來源與事實，不自行帶有支持或反對立場；同一份 Evidence 對不同 Claim 可能具有不同立場。`is_cached`、`cache_time`、`is_stale` 支援 10.3 節 official mode 的 cache 揭露要求。

### 7.2 Claim

```json
{
  "claim_id": "cl_002",
  "claim_type": "fact|inference|conclusion",
  "assets": ["BTC"],
  "time_range": { "start": "2026-07-03", "end": "2026-07-17" },
  "text": "Claim text",
  "based_on_claim_ids": ["cl_001"],
  "confidence": "high|medium|low",
  "limitations": ["The social source sample is limited"],
  "invalidation_conditions": ["A confirmed official announcement contradicts this claim"]
}
```

- `assets` 與 `time_range` 標明 claim 的適用幣種與時間範圍，支援跨幣比較題與 6.2 第 2 項。
- `based_on_claim_ids` 使分層可機器回溯：`fact` 不引用其他 claim；`inference` 引用其依據的 `fact`；`conclusion` 引用其依據的 `inference` 或 `fact`。

### 7.3 Claim-Evidence Link

```json
{
  "claim_id": "cl_001",
  "evidence_id": "ev_001",
  "stance": "supports|opposes|neutral",
  "reason": "How this evidence affects this specific claim"
}
```

競賽格式固定匯出：

```json
{
  "source": "source_name and source_url",
  "fetched_at": "2026-07-17T06:01:00Z",
  "content_reference": "quoted text, metric, or query range",
  "related_claim": "claim_id and claim text"
}
```

### 7.4 AnalysisResult

Arbiter 的單次受限 LLM 呼叫輸出（9.7 節），是 Renderer 的唯一分析輸入：

```json
{
  "run_id": "run_20260717_0001",
  "question": "原始題目",
  "assets": ["BTC"],
  "analysis_as_of": "2026-07-17T06:00:00Z",
  "direct_answer": "對指定問題的直接回答",
  "market_context": {
    "summary": "市場狀況摘要",
    "time_range": { "start": "2026-07-03", "end": "2026-07-17" }
  },
  "claims": ["<Claim>（含 fact/inference/conclusion 全部分層）"],
  "claim_evidence_links": ["<Claim-Evidence Link>"],
  "confidence": "high|medium|low",
  "confidence_rationale": "依 7.5 節 rubric 說明",
  "limitations": ["已知限制與資料缺口"],
  "invalidation_conditions": ["可能推翻結論的條件"],
  "watch_items": ["後續觀察重點"],
  "insufficient_data": false,
  "degradation_notes": ["Research Agent timeout，新聞類證據不可用"]
}
```

### 7.5 Evidence 規則

- LLM 不得自行產生市場數值；數值必須來自 deterministic tool output。
- 相同原始內容的轉載必須歸為同一 `independence_group`。
- `independence_group` 預設規則：以原始發布者為準；無法辨識原始發布者時，以來源 URL 的註冊網域歸群。
- Reliability 使用**靜態規則表**判定：依 source type 與是否第一手來源對照（例：交易所 API 市場數據、主辦方 CSV、專案官方公告 = high；具名新聞媒體原始報導 = medium；聚合轉載、社群內容、全市場情緒指標 = low）。規則表寫入 steering，不做動態可信度模型。
- 無法回溯的內容不得支撐關鍵結論。
- 每個 conclusion 必須具有 supporting evidence 或明確標示資料不足。
- 來源多樣性與來源獨立性分開計算；不同 source type 不代表不同上游來源。
- **Material conflict 數值化定義**：同一 claim 同時存在 `stance=supports` 與 `stance=opposes` 的 links，且雙方 evidence 的 reliability 皆 ≥ medium 並來自不同 `independence_group`。此定義同時是 H3 extension 的觸發介面（8.3 節）。
- **Confidence rubric**（Arbiter 判定 claim 與整體 confidence 的成文規則）：
  - `high`：至少兩個不同 `independence_group` 的支持證據、無 reliability ≥ medium 的反對證據、關鍵數值皆來自 deterministic tool output。
  - `medium`：僅單一獨立來源支持，或存在 reliability = low 的反對訊號，或關鍵證據時效偏舊。
  - `low`：存在 material conflict、僅二手來源支撐，或資料缺口實質影響判讀。

## 8. 架構

### 8.1 H1 - Agentized Pipeline（未採用）

```text
Question Parser -> Deterministic Data Tools -> Evidence Ledger -> Single Writer
```

審查結論：H2-Lite 能以可控成本取得並行取證與 multi-agent 展示價值，故不採 H1。

### 8.2 H2-Lite - 已核准 Core 架構

```text
Planner
  -> Market Worker (deterministic) --\
  -> Research Agent -----------------> Evidence Processor -> Arbiter -> Renderer
```

約束：

- **Market Worker 為確定性 Python 工具鏈，不使用 LLM**；Research Agent 為 bounded LLM agent。兩者並行執行。
- 每個元件僅能輸出固定 JSON schema；元件之間不自由聊天。
- 單一 Arbiter 以**單次受限 LLM 呼叫**產出 `AnalysisResult`：輸入為排序後前 20–30 筆 evidence，輸出受 `max_tokens` 上限約束；負責衝突判定說明、claim-evidence mapping 與信心說明。
- **Renderer 為 deterministic 模板引擎**，將 `AnalysisResult` 與 Evidence Ledger 轉為 `final_report.md`，不呼叫 LLM。
- 任一取證分支 timeout 時保留其他結果並繼續產生降級報告。

### 8.3 H3 - Conditional Debate（Extension interface，預設關閉、非 MVP）

```text
H2-Lite Evidence Ledger
  -> Conflict Detector (MVP: stub，永遠回傳 no material conflict)
     -> no material conflict: Arbiter
     -> material conflict: Bull Agent + Bear Agent -> Judge
  -> Renderer
```

約束：

- MVP 僅保留 Conflict Detector 介面與 feature flag；**預設實作為 stub，永遠回傳 no material conflict**，等同 H3 關閉。
- 若未來實作，觸發規則採 7.5 節 material conflict 數值化定義（rule-based，不使用 LLM classifier）。
- 最多一輪 Bull/Bear 分析，不允許自由辯論循環。
- 必須共用既有 Evidence IDs，不得在辯論階段捏造新證據。
- 受 feature flag、剩餘 deadline 與 token budget 控制；H3 失敗或時間不足時直接回到 Arbiter。
- **簡報誠實條款**：H3 只能以 extension architecture 呈現並明確標註未實作；只有在真的完成 H3 rehearsal 並留存紀錄後，才可展示對應錄影，且必須標示為 rehearsal。

### 8.4 定案

**H2-Lite 為唯一兩天承諾，已核准實作。H3 不列入承諾**；僅當 Day 2 上午前 H2-Lite 通過全部 core 驗收，才評估是否實作並啟用，且不影響 core 穩定性。

## 9. 元件責任

### 9.1 Deadline-aware Orchestrator

- 建立 run ID 與 execution context。
- 控制階段 deadline、並行任務、retry 與 cancellation；stage 級 wall-clock 凌駕 per-call 限制。
- 保存每次 tool/agent call 的開始、結束、狀態與摘要。
- 根據剩餘時間依第 11 節跳過順序放棄非必要階段。

### 9.2 Planner

- 解析題目、幣種、時間範圍與題型。
- `assets` 輸入與題目文字衝突時以 `assets` 為準並記錄 warning（2.4 節）。
- 產生有限且可執行的 research plan。
- 不直接下市場結論。

### 9.3 Market Worker

- 確定性 Python 工具鏈，**不使用 LLM**。
- 使用主辦方 OHLCV 與 Binance live API（10.1 節）。
- 計算報酬、波動、成交量、drawdown、相對強弱等指標；以 golden fixtures 驗證。
- 輸出帶查詢範圍與精確數值的 Evidence Items。

### 9.4 Research Agent

- 搜尋近期新聞、官方公告及專案更新。
- 優先第一手來源，辨認轉載與重複事件。
- 分離事件事實與作者觀點。
- 依題目按需呼叫 context adapter（MVP 僅 Fear & Greed），不強制取得全部類型。

### 9.5 Optional Context Adapters

- Context adapter 是 Research Agent 可呼叫的工具，不是獨立 Agent。
- MVP 僅接入 alternative.me Fear & Greed Index：屬全市場指標，Evidence 與報告必須標示其適用範圍為全市場而非單一幣種，並遵守該來源的標示要求。
- 鏈上、宏觀、社群 adapter 列 stretch；找不到足夠資料時回傳明確 gap，不得補寫推測。

### 9.6 Evidence Processor

- Schema validation、`content_hash` 精確去重、`independence_group` 歸群與時效檢查。
- 建立 Evidence Ledger。
- 依 7.5 節 material conflict 定義計算透明的 rule-based conflict indicators。

### 9.7 Arbiter

- 以**單次受限 LLM 呼叫**產出 `AnalysisResult`（7.4 節）。
- 輸入為依 reliability 與時效排序後的前 20–30 筆 evidence；輸出受 `max_tokens` 上限約束。
- 依 Evidence Ledger 建立 Facts、Inferences、Conclusions（以 `based_on_claim_ids` 分層回溯）。
- 處理支持與反對證據；依 7.5 節 rubric 產生 confidence、limitations 與 invalidation conditions。
- 不得引用 Ledger 外的事實。
- Schema 驗證失敗時一次修復重試；仍失敗則觸發 9.8 節 deterministic fallback report。

### 9.8 Renderer 與 Artifact Builder

- **Renderer**：deterministic 模板引擎，將 `AnalysisResult` 與 Ledger 轉為繁體中文 `final_report.md`（涵蓋 6.2 節 11 項）。Arbiter 失敗時，以 Ledger 中的 facts 加上資料不足聲明，用同一模板產出 fallback report。
- **Artifact Builder 增量落盤**：
  - `run_config.json`：run 開始時寫入（run config、模型、prompt/schema 版本、來源狀態）。
  - `execution_log.jsonl`：全程串流寫入。
  - `evidence.json`：Evidence Ledger 完成當下寫入。
  - `final_report.md`：最後產出。
- **固定檔名**：`final_report.md`、`evidence.json`、`execution_log.jsonl`、`run_config.json`。
- **Execution Log 粒度**：每次 tool/agent call 的開始、結束、狀態與摘要，加上 stage 事件；prompt 僅記版本引用，不記全文。

### 9.9 Web UI

- Streamlit，同進程呼叫 application service（14 節）。
- 輸入題目與幣種。
- 顯示階段進度、已取得的來源類型與降級狀態。
- 顯示 Final Report、Evidence、Execution Log。
- 提供 artifacts 檢視或下載能力。
- 明確顯示 run_mode；不提供交易或下單操作。

## 10. 資料來源（已定案）

### 10.1 Core

- **主辦方 Daily OHLCV CSV**：共同歷史基準。metadata 僅標示 `public_market_data`，不推定其上游交易所。
- **Canonical live source：Binance public REST API**（免驗證公開市場 API，提供 UTC klines 與 quote asset volume）。用來補齊 2026-05-31 以後的缺口及提供現場 snapshot。
  - CSV 與 live API 之間視為**來源切換**，切換點 2026-06-01 必須在 Evidence 與報告中標記。
  - 首次 live-source rehearsal 時，以 2026-05-01～2026-05-31 重疊區間對五幣 close 進行差異檢查，結果記錄於 run_config／steering，作為兩來源基差的校準證據；差異顯著時在報告中揭露。
- **Fallback live source：CoinGecko**（無 key；另提供 USD quote volume，可用於跨幣量比較）。
- **新聞：CryptoPanic**（免費 API token 需登入註冊，**Day 1 前完成**）；輔以新聞 RSS 來源作為不同 `independence_group` 的交叉印證。
- **官方公告**：幣種官方 Blog／公告頻道，best-effort；取不到時揭露缺口。
- **Context source：alternative.me /fng/**（Fear & Greed Index，見 9.5 節標示要求）。

系統必須保存 live API 的 endpoint、交易對、參數、UTC 範圍與 fetched time，並清楚揭露 CSV 與 live API 的來源差異。

不同幣種的 `volume` 是各自 base asset 單位，不得直接跨幣比較。跨幣比較應使用報酬、波動、相對變化、各自 rolling z-score，或 live API 提供的 quote volume。此規則寫入 Kiro steering。

### 10.2 Stretch

- 跨五幣種一致可用的鏈上聚合來源（目前無穩定一致的免費來源，缺少時誠實揭露）。
- 社群熱度或情緒來源。
- 宏觀事件日曆（如 FRED）。

MVP 不要求每次同時取得所有來源類型。正常 live run 的目標是至少三種 source types、三個 `independence_group`，其中至少一個為第一手或官方來源（口徑見 2.4）；未達目標時仍須完成報告並明確揭露缺口。

### 10.3 Run Modes 與 Cache

- `official`：禁止 fixture、預存答案與舊報告；只允許帶來源時間、cache time 與 stale 狀態的原始資料 cache（對應 7.1 節 `is_cached`／`cache_time`／`is_stale`）。
- `rehearsal`：允許 deterministic fixtures，用於重現測試與故障注入。
- `demo`：可展示事先保存的完整 run，但 UI 與報告必須明確標示為 recorded fallback，不得冒充現場新分析。

## 11. 15 分鐘執行預算

| 階段 | 預算 |
|---|---:|
| 題意解析與 research plan | 0.5 分鐘 |
| Market Worker + Research Agent 並行取證 | 4 分鐘 |
| 正規化、去重、可信度與衝突判定 | 1.5 分鐘 |
| Arbiter 單次呼叫與 render | 2.5 分鐘 |
| 驗證與 artifacts | 2 分鐘 |
| 內部緩衝（H3 預設關閉，原辯論時段歸還為緩衝） | 1.5 分鐘 |

內部分析預算合計最多 12 分鐘。第 12 分鐘取消所有非必要外部呼叫，第 13 分鐘前完成 artifacts，最後 2 分鐘保留給現場抖動與交付確認。

- 單一 adapter call timeout 不超過 45 秒、最多 retry 一次；單一 LLM 結構修復最多一次；修復重試共用該階段 deadline，不額外加時。
- **跳過順序**（剩餘時間不足時依序放棄）：H3（若啟用）→ optional context adapter → 反方訊號二次搜尋。
- **Artifacts 增量落盤時點**：`run_config.json` 於 run 開始、`execution_log.jsonl` 全程串流、`evidence.json` 於 Ledger 完成、`final_report.md` 最後產出。任何階段失敗時已落盤的 artifacts 不受影響。
- Arbiter 輸入 evidence 截斷至排序後前 20–30 筆，輸出受 `max_tokens` 上限約束。

## 12. 降級與錯誤處理

| 狀況 | 系統行為 |
|---|---|
| 單一 API timeout | 記錄錯誤，使用其他來源繼續 |
| 取證分支（Market Worker 或 Research Agent）失敗 | 將該類資料標示 unavailable，產生降級報告 |
| 找不到第一手來源 | 使用次級來源但降低 reliability，明確揭露 |
| 訊號互相矛盾 | 保留雙方 Evidence，降低 confidence；記錄 conflict indicator |
| 資料不足 | 回答目前無法可靠判定，列出需要的新資料 |
| LLM 輸出不符合 schema | 一次修復重試；仍失敗則跳過該元件 |
| Arbiter／報告 LLM 失敗 | 一次修復重試後，Renderer 以 Ledger facts 加資料不足聲明產出 deterministic fallback report，四項 artifacts 仍齊全 |
| 剩餘時間不足 | 依第 11 節跳過順序放棄非核心階段，優先完成四項 artifacts |

## 13. Agent 硬護欄

- 所有元件使用固定輸入與輸出 schema。
- 來源、取得時間與引用片段為 Evidence 必填資料。
- 每個元件受 wall-clock timeout 約束；LLM 呼叫以 `max_tokens` 參數限制輸出。不另建 token 或 tool-call 計數器。
- 不得產生買賣指令或個人化投資建議（Renderer 加簡單字串 lint 作最後防線）。
- 不得在沒有 Evidence ID 的情況下加入關鍵事實。
- 不得無限反思、自由循環或進行多輪辯論。
- Prompt 與 schema 必須版本化並寫入 `run_config.json`。

## 14. 技術選型（已定案）

- 語言與核心：Python 3.12、Pydantic v2、httpx、pandas。
- Orchestration：plain `asyncio`（拓撲為單一 fork-join，deadline 語意直接由 `asyncio.wait_for`／`gather` 控制）。
- LLM：Amazon Bedrock，經 Converse API 以薄 `LLMClient` 介面封裝。Model ID 走設定檔可配置，primary 與 fallback 兩組；**Day 1 前於目標 region 以實際帳號驗證可用性**（模型可用性受區域與帳號存取影響）。
- API 層：不另建 FastAPI；Streamlit 同進程直接呼叫 application service。
- UI：Streamlit（進度以輪詢 run-state 呈現，artifacts 以下載元件提供）。
- Artifact storage：本機檔案；S3 列 stretch。
- Deployment：單一 Docker image → ECR → EC2（docker compose）；ECS 列 stretch。
- Logs：structured JSONL + stdout；CloudWatch 列 stretch。

選型原則依序為：兩天可完成、15 分鐘穩定、可觀察、可 Demo，最後才是框架新穎度。

## 15. Kiro 開發流程

1. 本核准版 spec 作為 Kiro Feature Spec 的輸入。
2. **Day 1 第一件事**：在 Kiro 建立 Feature Spec 並立即 commit，保留 history 作為採用 Kiro 的加分證據：
   - `.kiro/specs/hoya-market-agent/requirements.md`
   - `.kiro/specs/hoya-market-agent/design.md`
   - `.kiro/specs/hoya-market-agent/tasks.md`
3. 建立 `.kiro/steering/`，固定競賽規則、schema、reliability 靜態表、volume 跨幣比較禁令、非目標、測試及 coding conventions。
4. 人工審查 requirements、design、tasks，刪除兩天內不必要功能。
5. 先執行端到端 vertical slice 任務，不直接 Run All Tasks。
6. Vertical slice 通過後，再由四人依責任邊界平行執行。
7. 保留 Kiro spec 與 task history，作為採用 Kiro 的交付證據。

## 16. 四人分工

### P1 - Integration / Orchestrator

- 共用 schemas、run state、deadline、降級策略與跳過順序。
- Application service 與端到端整合。
- 管理 shared branch、API contracts 與 integration gate。

### P2 - Data / Evidence

- Market Worker 的 OHLCV feature tools 與 Binance／CoinGecko adapters。
- 新聞、公告及 Fear & Greed adapters。
- Evidence normalization、deduplication 與 Ledger；重疊區間差異檢查工具。

### P3 - Reasoning / Report

- Planner、Arbiter 的 prompts 與 schemas（含 `AnalysisResult`）。
- Claim-evidence mapping、confidence rubric 落地、limitations。
- Renderer 模板、fallback report 與固定評測題；H3 extension 介面 stub。

### P4 - Frontend / AWS / Demo

- Streamlit UI 與 progress view。
- Docker、ECR、EC2 與 logs；Bedrock model 存取驗證。
- Demo script、錄影、AWS 架構圖與簡報素材（含 H3 簡報誠實條款的落實）。

所有人都需為自己的元件提供可用的 fixture 或 stub，不得等外部 API 全部完成才開始整合。

## 17. 兩天時程

### Day 1 上午

- **第一件事**：建立並 commit `.kiro/specs/hoya-market-agent/` 與 `.kiro/steering/`。
- 註冊 CryptoPanic API token；於目標 region 驗證 Bedrock primary／fallback model 存取。
- 全員確認 final schemas、API contracts、repository structure。
- 使用 fixture 跑通最薄 vertical slice：request -> one market source -> Evidence -> AnalysisResult -> render -> artifacts。

### Day 1 下午

- 四人依責任邊界平行補齊。
- 傍晚前完成第一次完整整合。
- H2-Lite core 必須能在本機執行。

### Day 2 上午

- 測試五個幣種與數種題型。
- 首次 live-source rehearsal 時執行 Binance／CSV 重疊區間差異檢查並記錄（10.1 節）。
- 測試 timeout、來源失效、schema error、Arbiter 失敗 fallback 與 partial result。
- H2-Lite 通過全部 core 驗收後，才評估是否實作 H3。

### Day 2 下午

- 功能凍結。
- 部署、錄影、簡報與 AWS 架構圖。
- 使用 15 分鐘倒數進行多次演練，驗證第 13 分鐘前完成 artifacts。
- 保存至少一組完整 artifacts 作為 recorded fallback demo，並明確標示 `run_mode=demo` 與原始取得時間。

## 18. 驗收標準

### 18.1 End-to-end

- 固定測試矩陣包含 BTC、ETH、SOL、BNB、XRP 各一題；若保留雙幣契約，再加入一題跨幣比較。
- 至少完成全部 fixture 測試與三次 live-source rehearsal；每次都在第 13 分鐘前產出全部四項 artifacts。
- `run_config.json` 於 run 開始即存在；UI 與 artifact 中的 run ID 一致。

### 18.2 Evidence quality

- 100% `claim_type=conclusion` 的 claims 具有 Claim-Evidence Links，或明確的 insufficient-data 標示。
- `conclusion` 與 `inference` 可經由 `based_on_claim_ids` 回溯至 `fact` 層。
- Evidence List 每筆包含競賽要求的四個最低欄位。
- 報告中的市場數值皆來自 tool output。
- 重複轉載不會被計為多個獨立來源；`independence_group` 依 7.5 節預設規則歸群。
- OHLCV 指標以固定 golden fixtures 驗證數值與 UTC 範圍。
- Binance／CSV 重疊區間差異檢查已執行且結果留存。
- 正常 fixture 驗收包含至少三種 source types、三個 `independence_group` 與一個第一手來源。

### 18.3 Reasoning quality

- 報告明確區分 fact、inference、conclusion。
- 報告包含至少一個反方訊號；若未找到，必須列出已查詢來源及未找到可信反方訊號的限制。
- 報告包含 confidence（依 7.5 節 rubric）、limitations 與 invalidation conditions。
- Agent 不提供明確買賣建議；Renderer 字串 lint 通過。

### 18.4 Resilience

- 模擬一個取證分支 timeout，系統仍會完成降級報告。
- 模擬外部來源全部失效，系統仍會輸出 OHLCV 分析、錯誤紀錄及資料不足說明。
- 模擬 Arbiter LLM 失敗，系統輸出 deterministic fallback report，四項 artifacts 齊全。
- H3 flag 關閉（預設）時不影響 H2-Lite core；stub 介面回傳 no-conflict。

### 18.5 Demo readiness

- 評審可在 UI 看見目前階段、成功來源、失敗來源及剩餘流程。
- Final Report、Evidence List、Execution Log 可在 Demo 中直接檢視。
- 私有 API keys 不會出現在 UI、logs、artifacts 或錄影中。
- UI 明確顯示 `official`、`rehearsal`、`demo` 模式，recorded fallback 不會被誤認為 live run。
- 簡報中 H3 標示為 extension architecture、未實作（除非已完成 rehearsal 並留存紀錄）。

### 18.6 Submission readiness

- 提案簡報包含解題方向、AI 技術、資料應用與 AWS 架構圖。
- Live Demo URL 可開啟，完整錄影可播放且不洩漏 secrets。
- GitHub repository 包含 source、config example、執行說明與 Kiro spec/steering 證據（含 commit history）。
- 四項 artifacts 檔名固定：`final_report.md`、`evidence.json`、`execution_log.jsonl`、`run_config.json`，且可重建。
- 提交前執行 secret scan，確認 `.env`、API keys 與私有 credentials 未進入 repository。

## 19. 主要風險

| 風險 | 影響 | 緩解 |
|---|---|---|
| 兩天內整合過多資料 API | 高 | Core 來源已收斂定案（10.1），adapter 可替換，使用 fixture |
| Multi-agent 延遲與不穩定 | 高 | bounded 元件、並行、deadline、H3 預設關閉 |
| Bedrock 模型在目標 region／帳號不可用或被 throttle | 高 | Day 1 前驗證 primary／fallback model ID；設定檔可切換；retry 受 stage deadline 約束 |
| Arbiter 長 context 呼叫延遲或失敗 | 高 | Evidence 截斷 20–30 筆、max_tokens 上限、deterministic fallback report、artifacts 增量落盤 |
| 不同鏈的鏈上資料差異 | 高 | 鏈上資料列 stretch，缺少時誠實揭露 |
| LLM 幻覺或錯誤引用 | 高 | Evidence-only generation、schema validation、claim coverage check、deterministic renderer |
| Demo 當下 API 失效 | 高 | official mode 產生 partial result；recorded fallback 只在 demo mode 顯示並揭露時間 |
| 團隊同時修改共用程式 | 中 | P1 管理 contracts，先切目錄與 ownership，再平行開發 |
| 過度追求漂亮 UI | 中 | 先通過 artifacts 與 15 分鐘驗收，再做視覺 polish |
| Kiro 加分證據流失 | 中 | Day 1 第一件事建立並 commit `.kiro/`，保留 task history |

## 20. 決策紀錄

以下決策已於 2026-07-17 全部關閉：

| # | 決策 | 結論 |
|---|---|---|
| 1 | H2-Lite 或 H2-Lite + H3 | H2-Lite 為唯一承諾；H3 為 extension interface，預設關閉、非 MVP |
| 2 | Orchestration | plain `asyncio` |
| 3 | LLM provider | Amazon Bedrock（Converse API；model ID 可配置，primary/fallback 預先驗證） |
| 4 | Core 外部資料來源 | Binance public API（canonical，無 key）、CoinGecko（fallback，無 key）、CryptoPanic（需免費 token）、alternative.me /fng/（無 key） |
| 5 | UI | Streamlit，同進程呼叫 application service |
| 6 | 部署 | 單一 Docker image → ECR → EC2 docker compose；ECS/S3/CloudWatch 列 stretch |
| 7 | H3 conflict trigger | rule-based（7.5 節 material conflict 數值化定義），不使用 LLM classifier |

其他已定案事項：報告語言繁體中文、固定檔名（9.8）、`analysis_as_of` official mode 系統凍結（6.1）、reliability 靜態規則表（7.5）、confidence rubric（7.5）、Evidence 截斷 20–30 筆（11）、跳過順序（11）、artifacts 增量落盤（11）、Execution Log 粒度（9.8）。

### 待主辦方確認（不阻塞開工，預設解讀見 2.4）

1. 15 分鐘計時邊界是否含輸入題目與評審檢視 artifacts。
2. 「三個獨立上游來源」的計數口徑（per-run 或 per-conclusion）；主辦方 CSV 是否計入。
3. 「第一手或官方來源」的定義（交易所 API 市場數據是否符合）。

## 21. 外部審查紀錄

第 21 節原為「給審查 CLI 的問題」共 10 題，已於 2026-07-17 完成外部 CLI 逐項審查並經團隊回覆修正後採納。審查產出的四點修正（不推定 CSV 來源、H3 簡報誠實條款、單次 Arbiter 呼叫 + deterministic renderer、Market Worker 更名）與決策關閉清單已全數併入本核准版。原始問題保留如下供追溯：

1. H2-Lite core + optional H3 是否能在四位 junior、兩天內合理完成？
2. 哪些元件明顯 over-engineered，應從 MVP 刪除？
3. 在 15 分鐘單次執行限制下，最大 latency 與 failure risks 是什麼？
4. plain asyncio、LangGraph、AWS Strands Agents 三者何者最符合此範圍，原因為何？
5. 對五個幣種而言，哪些公開資料來源最容易穩定且一致地使用？
6. Evidence 與 Claim schema 是否足以支持可回溯、去重與矛盾處理？
7. 有哪些需求仍有兩種以上合理解讀，必須在實作前釐清？
8. 若只能保留一個 Multi-agent 亮點，應保留 bounded specialists 還是 conditional debate？
9. 請提出最小可行的 Python、LLM、UI 與 AWS 技術組合。
10. 請指出會讓作品偏離競賽主題或評分標準的設計。

## 22. 文件依據

- `(HOYA BIT) 命題文件 - 2026 雲湧智生：臺灣生成式 AI 應用黑客松競賽.pdf`，第 1 至 5 頁。
- `HOYA BIT -黑客松企業數據工作坊簡報.pdf`，命題說明與評分相關投影片 13 至 20。
- `HOYA_BIT_crypto_market_dataset/README.md`。
- `HOYA_BIT_crypto_market_dataset/dataset_metadata.json`。
- Kiro Feature Specs 官方文件：<https://kiro.dev/docs/specs/feature-specs/tech-design-first/>。
- Binance Spot REST API：<https://developers.binance.com/en/docs/products/spot/rest-api>；Market endpoints：<https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market>。
- AWS Bedrock APIs：<https://docs.aws.amazon.com/bedrock/latest/userguide/apis.html>；模型可用性：<https://docs.aws.amazon.com/bedrock/latest/userguide/models.html>。
- CryptoPanic API：<https://cryptopanic.com/developers/api/keys>。
- Alternative.me Fear & Greed Index API：<https://alternative.me/crypto/fear-and-greed-index/>。

## 23. Changelog

### v1.0（2026-07-17）— Draft 轉核准版

- 狀態由 Draft 改為核准版；第 20 節七項決策全部關閉並記錄。
- 架構定案：Market Specialist 更名 **Market Worker**（確定性工具，非 LLM agent）；新增 **Renderer**（deterministic 模板引擎）；Arbiter 改為單次受限呼叫產出新增之 `AnalysisResult` schema（7.4）。
- H3 降為 extension interface：預設關閉、stub 回傳 no-conflict、新增簡報誠實條款。
- Schema 擴充：Claim 增加 `assets`、`time_range`、`based_on_claim_ids`；EvidenceItem 增加 `is_cached`、`cache_time`、`is_stale`；新增 `independence_group` 預設規則、material conflict 數值化定義與 confidence rubric（7.5）。
- 資料來源定案：Binance canonical（不推定主辦 CSV 來源；來源切換標記 + 重疊區間差異檢查）、CoinGecko fallback、CryptoPanic、alternative.me /fng/；鏈上／宏觀列 stretch。
- 範圍刪減：近似重複偵測、動態 reliability、token/tool-call 硬計數列入非目標；S3/CloudWatch/ECS 列 stretch。
- 執行預算：H3 時段歸還為 1.5 分鐘內部緩衝；新增跳過順序、Evidence 截斷 20–30 筆、artifacts 增量落盤時點。
- 降級：新增 Arbiter LLM 失敗 → deterministic fallback report。
- 新增口徑與預設解讀（2.4）與「待主辦方確認」清單（20）。
- 其他定案：報告語言繁體中文、四項 artifacts 固定檔名、`analysis_as_of` official mode 系統凍結、Execution Log 粒度、Kiro Day 1 第一件事與 commit 證據要求。
