---
inclusion: always
---

# Competition Rules and Evidence Guardrails

本檔案是所有 Kiro 任務都必須遵守的競賽護欄。與實作選擇衝突時，以核准 spec 與本檔案的範圍、誠實性及 deadline 規則為準。

## Fixed Competition Constraints

- 團隊：4 位 junior developer；開發時間：2 天。
- 支援資產：BTC、ETH、SOL、BNB、XRP。
- 現場才公布題目與指定幣種；不得依賴預寫答案。
- 正式 run 最多 15 分鐘，原則上只有一次執行機會。
- MVP 必須產出：Final Report、Evidence List、Execution Log、Source / Config。
- 固定 artifact 檔名：`final_report.md`、`evidence.json`、`execution_log.jsonl`、`run_config.json`。
- 報告語言：繁體中文。
- MVP 唯一承諾：H2-Lite。H3 是預設關閉、未實作的 extension interface。

## Deadline Policy

- 外部硬性 deadline：run 開始後 900 秒。
- 內部分析 deadline：第 12 分鐘；到點取消所有非必要外部呼叫。
- Artifact deadline：第 13 分鐘前完成四項檔案；最後 2 分鐘保留給現場抖動與交付確認。
- Stage 預算：plan 0.5 分鐘、並行取證 4 分鐘、Evidence 處理 1.5 分鐘、Arbiter + render 2.5 分鐘、驗證 + artifacts 2 分鐘、內部緩衝 1.5 分鐘。
- 單一 adapter timeout 不超過 45 秒，最多 retry 一次；LLM schema repair 最多一次。所有 retry 共用原 stage deadline。
- 時間不足時的固定跳過順序：H3 -> optional context adapter -> 反方訊號二次搜尋。
- 任何非核心工作都不得延遲四項 artifacts。

## Run Mode Policy

### `official`

- run 開始時將 `analysis_as_of` 凍結為當下 UTC，不接受使用者自訂。
- 禁止 fixture、預存答案與舊報告。
- 只可使用能揭露來源時間、cache time 與 stale 狀態的原始資料 cache。

### `rehearsal`

- 可使用 deterministic fixtures、自訂 `analysis_as_of` 與故障注入。
- 測試結果不得被描述為 official live result。

### `demo`

- 可展示已保存的完整 run。
- UI 與報告必須標示 recorded fallback、原始取得時間及 `run_mode=demo`，不得冒充現場新分析。

所有模式都必須在 UI、`run_config.json` 與報告中清楚可辨。

## Approved Data Policy

- 主辦方 Daily OHLCV CSV 是共同歷史基準；metadata 僅標示 `public_market_data`，不得推定其上游交易所。
- Binance public REST API 是 canonical live source。CoinGecko 雖為主辦方核准的公開來源，但列為 post-hackathon Future Work，MVP 不實作；baseline market source 失敗時只做誠實降級，不宣稱切換至第二個 live provider。
- CSV 與 live API 是不同來源。跨越兩者時標記 2026-06-01 來源切換點並揭露差異。
- 第一次 live-source rehearsal 應保存 BTC、ETH、SOL、BNB、XRP 在 2026-05-01 至 2026-05-31 的 CSV／Binance close 差異檢查結果。
- CryptoPanic 與新聞 RSS 用於新聞取證；幣種官方 Blog／公告頻道採 best-effort。
- Alternative.me Fear & Greed 是全市場 context，不是單幣指標，不得單獨支撐單幣結論。
- 鏈上、宏觀與額外社群 adapters 是 stretch，不得成為 MVP blocking dependency。
- 正常 live run 的取證目標是每個 run 至少三種 source types、三個 `independence_group`，其中至少一個第一手或官方來源。未達目標仍須產出報告並揭露缺口。

以下三項口徑尚待主辦方確認，但不得阻塞開工：

1. 15 分鐘是否包含題目輸入與評審檢視時間；實作一律從 run 開始計時。
2. 三個獨立上游來源暫採 per-run；主辦方 CSV 暫計一個 `independence_group`。
3. 第一手／官方來源暫指原始資料產生者，包括市場數據的交易所 API、專案官方公告與主辦方 CSV。

主辦方若給出不同正式解釋，更新 steering 與 requirements 後再修改行為，不得只改 prompt。

## Coin-Agnostic Source Policy（幣種無關通用作法）

幣種於現場才抽選，任一支援資產都可能被指定。為避免為特定幣過度設計、或現場抽到未涵蓋的幣而開天窗，一律採以下通用作法：

- **Pipeline 以 `{asset}` 為參數，五幣共用同一條路徑。** 禁止 per-coin 分支邏輯（`if asset == "BTC"`）、per-coin 特調參數或 per-coin 硬編路徑。
- **來源必須「用幣種符號即可統一查詢五幣」才進 MVP。** 例如：主辦 CSV（`{ASSET}_daily_ohlcv.csv`）、Binance klines（`{ASSET}USDT`）、CryptoPanic（依 currency 過濾）、Alternative.me（全市場 context）。
- **「每個幣需各自實作一套」的來源一律 best-effort 或延後，不得成為 MVP blocking dependency。** 典型為各鏈鏈上瀏覽器（Etherscan=ETH、Solscan=SOL、XRPL⋯各不同）與各專案官方 Blog；缺漏時誠實揭露，不阻塞 run。
- **若要納入鏈上／社群訊號，只採「單一多鏈／多幣聚合來源、以幣種符號查詢」者；禁止為五條鏈各寫一套 adapter。** 找不到幣種無關的聚合來源時，該訊號列為缺口揭露，不硬做。
- **驗證只需兩個不同幣各跑一次單幣即可證明流程幣種無關**（對齊 Gold）；不要求五幣完整矩陣或 per-coin calibration。
  雙幣比較另有自己的驗證（Requirement 17 的單一雙幣 run），不得以那兩次單幣 run 代替，也不得反過來用雙幣 run 代替 Gold 的幣種無關證明。
- **報告與 Evidence 一律標明實際 `asset` 與 `time_range`**，不得把某一幣的取證條件假設套用到其他幣。

一句話原則：**「用符號就能查五幣」的來源才進 MVP；「每個幣要各寫一套」的一律 best-effort 或跳過。**

## Evidence Integrity Rules

- 市場數值只能來自 deterministic tool output；LLM 不得補值、猜值或改寫為新數值。
- 每筆 Evidence 必須保存來源名稱與 URL、published/fetched time、查詢參數或範圍、引用／指標內容、normalized fact、reliability、`independence_group`、`content_hash` 及 cache/stale 狀態。
- EvidenceItem 本身無立場；`supports|opposes|neutral` 只存在 Claim-Evidence Link。
- 無 Evidence ID 或無法回溯的內容不得支撐關鍵結論。
- `content_hash` 只做精確去重；不得在 MVP 加入內容相似度模型。
- `independence_group` 優先使用原始發布者；無法辨識時使用來源 URL 的註冊網域。
- 轉載同一原始內容不得被計為多個獨立來源。
- source type 多樣性與 upstream independence 必須分開計算。

## Static Reliability Table

只使用下表，不建立動態可信度模型：

| Reliability | 適用來源 |
|---|---|
| `high` | 交易所 API 的市場數據、主辦方 CSV、專案官方公告等原始資料產生者 |
| `medium` | 具名新聞媒體的原始報導 |
| `low` | 聚合轉載、社群內容、全市場情緒指標 |

不得僅因 LLM 認為來源「看起來可信」而升級 reliability。若聚合頁面只指向原始報導，聚合內容本身仍按聚合來源處理；只有實際取得並引用原始發布頁面時，才能依原始來源分類。

## Claim and Conflict Rules

- Claim 必須分成 `fact|inference|conclusion`，並包含適用 `assets` 與 `time_range`。
- fact 不引用其他 Claim；inference 以 `based_on_claim_ids` 引用 fact；conclusion 引用 inference 或 fact。
- 每個 conclusion 都要有 supporting evidence；否則標示 insufficient data。
- Material conflict 的唯一判定：同一 Claim 同時存在 supports 與 opposes links，雙方 reliability 皆至少 medium，且來自不同 `independence_group`。
- Material conflict 必須保留雙方 Evidence 並降低 confidence，不得讓單一敘事覆蓋反方證據。
- Confidence rubric：
  - `high`：至少兩個不同 `independence_group` 支持、沒有 reliability 至少 medium 的反對證據，且關鍵數值全由 deterministic tools 產生。
  - `medium`：僅單一獨立來源支持，或有 low reliability 反對訊號，或關鍵證據時效偏舊。
  - `low`：存在 material conflict、僅二手來源支撐，或資料缺口實質影響判讀。
- 沒找到可信反方訊號時，列出已查詢來源並揭露此限制，不得假造反方。

## Cross-Asset Rules

- 內部 `assets` 契約支援一至兩個資產；UI 預設單幣，第二幣只在使用者明確加選時進入 `assets`。
- 不同幣種的 base-asset `volume` 單位不同，禁止直接跨幣比較。
- 跨幣只能使用可比較尺度，例如報酬、波動、相對變化、各自 rolling z-score／百分位，或同一 provider、同一期間的 quote volume。
- 跨幣 Claim 必須明記 `assets` 與 `time_range`。
- 每個來源的 quote asset、時間範圍與來源切換都要揭露，禁止把不同口徑描述為同質資料。
- **雙幣比較是已承諾能力（Requirement 17），不是 Future Work。** 以單一 run 完成：一個 `run_id`、
  一個凍結 `analysis_as_of`、一份 Ledger、四項固定 artifacts；禁止為比較另開第二個 run 或第五項 artifact。
- 雙幣 run 必須讓兩個資產各自都有 Evidence 進入 Arbiter payload，禁止單一資產或單一 source type
  佔滿 30 筆上限。`asset=null` 的全市場項目不計入任一資產配額。
- 任一資產缺少 baseline 市場證據時，比較標為 `unavailable` 並揭露缺口；
  🚫 不得以單幣結果冒稱比較結果。
- 比較結論不得成為相對買賣建議（例如「A 優於 B 所以換倉」）；Renderer 禁語 lint 仍最後把關。

## Architecture and H3 Honesty Rules

- H2-Lite 固定流程：Planner -> Market Worker 與 Research Agent 並行 -> Evidence Processor -> 單次受限 Arbiter -> deterministic Renderer。
- Market Worker 不使用 LLM；Renderer 不使用 LLM。
- Arbiter 只接收排序後前 20 至 30 筆 Evidence，輸出固定 `AnalysisResult` schema，並受 `max_tokens` 與 stage deadline 約束。
- 元件只交換固定 JSON schema，不允許自由聊天、無限反思或無限循環。
- H3 flag 預設 false；MVP stub 永遠回傳 no material conflict。
- 未來若實作 H3，只能以 material-conflict rule 觸發、最多一輪、只引用既有 Evidence IDs，失敗或時間不足立即回到 Arbiter。
- 未完成並保存 rehearsal 紀錄前，簡報、UI 與文件必須標示 H3 為未實作 extension，不得宣稱 live 啟用。

## Report Safety Rules

- 報告由 deterministic Renderer 依 `AnalysisResult` 與 Evidence Ledger 產生，不允許 LLM 直接生成最終全文。
- 報告必須包含直接回答、時間範圍、facts、支持證據、反方／矛盾證據、inferences、conclusion、confidence rationale、limitations、invalidation conditions 與 watch items。
- 禁止明確買入、賣出、加倉、減倉、資產配置、下單或個人化投資建議；Renderer 必須執行字串 lint。
- 禁止把 `high|medium|low` confidence 描述成未校準的精確預測機率。
- 資料不足時直接說明目前無法可靠判定並列出所需資料。

## Artifact and Secret Rules

- `run_config.json` 在 run 開始時增量落盤。
- `execution_log.jsonl` 全程串流，記錄每個 tool/agent call 的開始、結束、狀態、摘要及 stage 事件。
- Prompt 只記版本 ID，不記全文。
- `evidence.json` 在 Ledger 完成時落盤；`final_report.md` 最後產出。
- Arbiter 失敗時，Renderer 必須用 Ledger facts 與資料不足聲明產生 deterministic fallback report，四項 artifacts 仍需齊全。
- `.env`、API keys、AWS credentials、CryptoPanic token 與任何 secrets 不得進入 UI、logs、artifacts、錄影或 Git repository。
- 提交前必須執行 secret scan。

## MVP Exclusions

除非 H2-Lite 全部 core 驗收已通過且仍有時間，禁止把下列項目排入必要任務：

- H3 Bull/Bear/Judge 實作。
- 鏈上、宏觀、額外社群 adapters。
- S3、CloudWatch、ECS。
- 近似去重、動態 reliability、自由 Agent loop、自建 token/tool-call 計數器。
- 任何會延遲 vertical slice、fallback、四項 artifacts 或 EC2 Demo 的 UI polish。
