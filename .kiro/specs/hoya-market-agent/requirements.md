# HOYA Market Agent Requirements

## 1. Introduction

本文件將核准版產品規格轉為可由 Kiro 追蹤與驗收的需求。產品是在競賽現場接收指定題目與幣種後，於 15 分鐘內完成多源、可回溯、可誠實降級的繁體中文加密市場分析。

MVP 唯一承諾為 H2-Lite：`Planner -> Market Worker + Research Agent -> Evidence Processor -> Arbiter -> Renderer`。H3 Conditional Debate 僅保留預設關閉的 extension interface，不屬於兩天 MVP 承諾。

本文使用 EARS 語法；`THE SYSTEM SHALL` 表示可驗收的強制行為。

## 2. Requirements

### Staged Acceptance — Approved D1–D8

This section defines layer-level gates. Requirements 1–15 define the detailed behavioral acceptance criteria; overlapping wording is a traceability mapping, and the more specific Requirement controls without weakening the applicable stage gate.

1. `WHEN` Bronze acceptance is evaluated, `THE SYSTEM SHALL` complete an entirely offline single-asset run from deterministic request, Evidence, and `AnalysisResult` fixtures through Streamlit and the deterministic Renderer, produce the four fixed artifacts, require no live HTTP, Bedrock, AWS credentials, or network access, and label the run honestly as `rehearsal` or `demo` rather than `official`.
2. `WHEN` Silver acceptance is evaluated, `THE SYSTEM SHALL` complete one single-asset end-to-end run using the Organizer CSV, one designated baseline live market source, one designated baseline research source, normalized and validated Evidence, at least one successful schema-valid Bedrock result, the deterministic Renderer, and all four fixed artifacts.
3. `THE SYSTEM SHALL` successfully complete a separate deterministic fallback test for Silver; a `fallback-only` execution does not satisfy the Silver success gate, and any Bedrock or external-source failure must produce honestly labelled partial or degraded output when useful Evidence remains.
4. `THE SYSTEM SHALL` treat additional Silver sources as optional and non-blocking, without an exactly-one maximum; failure of an optional source shall not fail Silver.
5. `WHEN` Gold acceptance is evaluated, `THE SYSTEM SHALL` validate two different assets as separate single-asset runs, exercise required source and Bedrock degradation paths, meet Docker build/runtime and ECR/EC2 deployment acceptance, and complete one timed rehearsal of the full judged flow. Dual-asset comparison and additional asset runs are optional and non-blocking.

`Gold local Exit` means the pre-deployment local gate at which Silver has passed and the two required single-asset Gold runs, required degradation checks, and deterministic artifact checks have passed locally. Docker/ECR/EC2 deployment and the complete timed judged-flow rehearsal remain Gold delivery requirements that may be completed after Feature Freeze under item 7.

6. `THE SYSTEM SHALL` treat Platinum as post-hackathon Future Work only and outside the formal two-day MVP Acceptance; Platinum work shall not be implemented during the formal two-day delivery period or block Gold, Demo, deployment, rehearsal, or submission.
7. `WHEN` Gold local Exit occurs or Day 2 midday arrives, whichever occurs first, `THE SYSTEM SHALL` begin Feature Freeze. After Feature Freeze, only bug fixes, reliability fixes, deployment, rehearsal, documentation, rollback preparation, and submission verification are allowed; new features, providers, artifact formats, PDF/HTML, extra visualization, the complete five-coin matrix, and Platinum capabilities are prohibited.

### Requirement 1: 建立分析請求

**User Story:** 身為競賽評審，我希望輸入臨時公布的問題與指定幣種，以便系統能針對現場題目建立一次可追蹤的分析執行。

#### Acceptance Criteria

1. `WHEN` 使用者提交自然語言問題與一至兩個支援資產，`THE SYSTEM SHALL` 建立唯一 `run_id` 並保留原始問題、`assets`、`requested_at`、`deadline_seconds`、`run_mode` 與 H3 feature flag。
2. `THE SYSTEM SHALL` 將支援資產限制為 BTC、ETH、SOL、BNB、XRP，且內部資料契約使用 `assets: string[]` 接受一至兩個資產。
3. `WHEN` 題目文字提及的幣種與 `assets` 不一致，`THE SYSTEM SHALL` 以 `assets` 為準，並在 Execution Log 記錄 warning。
4. `WHEN` UI 建立一般單幣分析，`THE SYSTEM SHALL` 預設只選擇一個幣種；雙幣能力只需保留契約與比較題相容性。

### Requirement 2: 維持時間基準與 Run Mode 誠實性

**User Story:** 身為評審，我希望能辨識分析使用的時間基準與資料模式，以便確認現場結果沒有混入未揭露的 fixture 或舊報告。

#### Acceptance Criteria

1. `WHEN` `run_mode=official` 的 run 開始，`THE SYSTEM SHALL` 將 `analysis_as_of` 凍結為當下 UTC，且不接受使用者自訂該值。
2. `WHILE` `run_mode=official`，`THE SYSTEM SHALL` 禁止 fixture、預存答案與舊報告，只允許具來源時間、`cache_time` 與 `is_stale` 狀態的原始資料 cache。
3. `WHILE` `run_mode=rehearsal`，`THE SYSTEM SHALL` 允許 deterministic fixtures、故障注入及自訂 `analysis_as_of`，以重現測試情境。
4. `WHILE` `run_mode=demo`，`THE SYSTEM SHALL` 允許展示已保存的完整 run，但 UI 與報告必須明確標示 recorded fallback 及原始取得時間。
5. `WHEN` 任何 run 被顯示或匯出，`THE SYSTEM SHALL` 在 UI 與 artifacts 中明確記錄其 `run_mode`。
6. `WHEN` 使用 Daily OHLCV，`THE SYSTEM SHALL` 只將 `analysis_as_of` 以前完成的 UTC 日 K 視為完整 K 線；當日未完成資料必須標示為 intraday snapshot，且不得與完整日 K 混用。
7. `THE SYSTEM SHALL` 將 `official` 限於使用正式核准來源與執行條件的 live run，將 `rehearsal` 用於完整演練並明確標示，並將 `demo` 用於 fixture、recorded 或受控 fallback 展示且明確標示其資料模式。
8. `THE SYSTEM SHALL NOT` 將 fixture run 標示為 live official run、將 fallback-only run 標示為 Silver success，或隱藏 stale、missing、mock 或 degraded Evidence。

### Requirement 3: 取得並計算可重現的市場資料

**User Story:** 身為市場分析使用者，我希望市場數值來自可重現工具與清楚標示的來源，以便驗證報告中的量化依據。

#### Acceptance Criteria

1. `WHEN` Market Worker 計算 OHLCV 指標，`THE SYSTEM SHALL` 使用 deterministic 程式碼，並把資料區間與計算參數記錄於 artifacts。
2. `THE SYSTEM SHALL` 將主辦方 Daily OHLCV CSV 視為共同歷史基準，且不得推定其上游為任何特定交易所。
3. `WHEN` 需要 2026-05-31 之後的 live 資料或現場 snapshot，`THE SYSTEM SHALL` 以 Binance public REST API 作為 Silver 與 Gold 的 designated baseline live market source。
4. `WHEN` 同一分析跨越 CSV 與 live API，`THE SYSTEM SHALL` 將 2026-06-01 標示為來源切換點，並在 Evidence 與報告揭露來源差異。
5. `WHEN` baseline live market source 失敗，`THE SYSTEM SHALL` 產生 honest partial completion 或 deterministic degradation，不得宣稱已切換至第二個 live market provider。
6. `WHEN` the system accesses a live API, `THE SYSTEM SHALL` retain the endpoint, trading pair, query parameters, UTC range, and `fetched_at`.
7. `WHEN` 使用 Alternative.me Fear & Greed Index，`THE SYSTEM SHALL` 將其標示為全市場而非單一幣種指標，且不得單獨支撐單幣結論。
8. `THE SYSTEM SHALL` 透過 typed `SourceAdapter` compatibility seam 存取 market 與 research sources；MVP implementation 必須保持 local 或 in-memory，且不要求動態 provider discovery 或獨立服務。

CoinGecko live adapter、完整 five-asset validation matrix，以及 BTC、ETH、SOL、BNB、XRP 的完整 calibration 明確延後為 post-hackathon Future Work。Requirement 1 的 five-asset allowlist 僅表示輸入相容性，不表示五個資產均已完成 Gold 驗證。

### Requirement 4: 完成多源取證並誠實揭露缺口

**User Story:** 身為競賽評審，我希望每次正常分析能結合不同類型與不同上游的資料，以便看見真正的多源驗證，而不是重複轉載堆疊。

#### Acceptance Criteria

1. `WHEN` 正常 live run 的來源可用，`THE SYSTEM SHALL` 以每個 run 至少三種 `source_type`、三個不同 `independence_group`，且至少一個第一手或官方來源為取證目標。
2. `THE SYSTEM SHALL` 將主辦方 CSV、designated baseline market data、designated baseline research data、官方公告及 Alternative.me context source 依其實際取得狀態記錄，不得把未取得或僅列為 Future Work 的來源算入來源數量。
3. `WHEN` 官方 Blog 或公告頻道無法取得，`THE SYSTEM SHALL` 以 best-effort 結束該查詢並在報告揭露缺口，而非阻塞整個 run。
4. `IF` 正常 run 未達三種 source types、三個獨立上游或第一手來源目標，`THE SYSTEM SHALL` 仍完成報告，並降低適當 confidence 或明確揭露資料不足。
5. `THE SYSTEM SHALL` 分開計算來源類型多樣性與上游來源獨立性；不同 `source_type` 不得自動視為不同 `independence_group`。
6. `WHEN` Silver acceptance is evaluated, `THE SYSTEM SHALL` 使用一個 designated baseline research source；額外 research sources 為 optional、non-blocking，且其失敗不得使 Silver 失敗。三種 source types、三個 independence groups 與第一手來源仍是可揭露的取證目標，不是 Silver Exit Gate。
7. `THE SYSTEM SHALL` 僅從 static tool allowlist 選擇工具，且 research domain、URL host 與 URL 必須符合核准 allowlist；LLM 與 optional provider 均不得自行選擇任意 provider、operation 或擴張 allowlist。
8. `THE SYSTEM SHALL` 將 retrieved external content 視為 `untrusted data`；網頁或研究內容中的指令不得改寫 system policy，亦不得選擇未核准 tool、domain、host 或 URL。
9. `WHEN` 外部內容被取回，`THE SYSTEM SHALL` 先完成 normalization 與 schema validation，並在形成 Evidence 後才能透過 Claim-Evidence Link 支撐或反對 Claim；MVP 不要求額外 sandbox service 或 production security infrastructure。

### Requirement 5: 建立可回溯 Evidence Ledger

**User Story:** 身為評審，我希望每項證據都有來源、時間、引用內容與關聯主張，以便從結論回溯原始依據並辨識重複來源。

#### Acceptance Criteria

1. `WHEN` Evidence Processor 接收一筆來源內容，`THE SYSTEM SHALL` 產生符合核准 `EvidenceItem` schema 的項目，包含 Evidence ID、asset、source/provider、source type/name、source URL 或 stable source reference、`fetched_at`、published/source time when available、query or parameters、content reference、normalized fact、reliability、independence group、content hash，以及 applicable cache/stale metadata。
2. `THE SYSTEM SHALL` 讓 EvidenceItem 保持無立場；支持、反對或中性立場只能記錄於 Claim-Evidence Link。
3. `WHEN` 正規化後的原始內容具有相同 SHA-256 `content_hash`，`THE SYSTEM SHALL` 將其視為精確重複內容，不實作近似相似度模型。
4. `WHEN` 可辨識原始發布者，`THE SYSTEM SHALL` 以原始發布者作為 `independence_group`；否則以來源 URL 的註冊網域歸群。
5. `THE SYSTEM SHALL` 依 always-included steering 的靜態 source-type／第一手來源規則指定 `high|medium|low` reliability，不使用 LLM 或動態模型評分可信度。
6. `THE SYSTEM SHALL` 禁止無法回溯的內容支撐關鍵結論，且禁止 LLM 自行產生市場數值。
7. `WHEN` the Evidence List is exported, `THE SYSTEM SHALL` provide at least source, `fetched_at`, content reference, and related claim.
8. `THE SYSTEM SHALL` record an Evidence item's relationship to a Claim only through the Claim-Evidence Link `supports|opposes|neutral` stance, retain linked claim IDs, and preserve the immutable run-level `analysis_as_of`.
9. `WHEN` published/source time 缺少、freshness 不明或過舊、或 Evidence 標記 stale，`THE SYSTEM SHALL` 在 limitations 或 degradation notes 中明確揭露，且不得虛構任何時間資訊。

### Requirement 6: 建立分層 Claim、衝突與信心判定

**User Story:** 身為市場分析使用者，我希望報告能區分事實、推論與結論，並保留反方證據，以便理解結論如何形成以及何時可能不成立。

#### Acceptance Criteria

1. `THE SYSTEM SHALL` 使用 `fact|inference|conclusion` 三種 Claim，且每筆 Claim 包含 `assets`、`time_range`、`confidence`、limitations 與 invalidation conditions。
2. `THE SYSTEM SHALL` 讓 fact 不引用其他 claim、inference 透過 `based_on_claim_ids` 引用 fact、conclusion 透過 `based_on_claim_ids` 引用 inference 或 fact。
3. `WHEN` Evidence 影響特定 Claim，`THE SYSTEM SHALL` 建立含 `supports|opposes|neutral` stance 與 reason 的 Claim-Evidence Link。
4. `THE SYSTEM SHALL` 使每個 conclusion 具有 supporting evidence；若無足夠 supporting evidence，則必須明確設定 insufficient-data 狀態。
5. `WHEN` 同一 claim 同時有 supports 與 opposes links，且雙方 evidence reliability 皆至少為 medium 並來自不同 `independence_group`，`THE SYSTEM SHALL` 將其判定為 material conflict、保留雙方 Evidence 並降低 confidence。
6. `WHEN` Claim 至少有兩個不同 `independence_group` 的支持證據、沒有 reliability 至少 medium 的反對證據，且關鍵數值皆來自 deterministic tool output，`THE SYSTEM SHALL` 允許將 confidence 判為 high。
7. `WHEN` Claim 僅有單一獨立來源、存在 low reliability 反對訊號或關鍵證據時效偏舊，`THE SYSTEM SHALL` 將 confidence 判為不高於 medium。
8. `WHEN` Claim 存在 material conflict、僅由二手來源支撐或資料缺口實質影響判讀，`THE SYSTEM SHALL` 將 confidence 判為 low。
9. `WHEN` 未找到可信反方訊號，`THE SYSTEM SHALL` 列出已查詢來源，並把未找到可信反方訊號列為限制。

### Requirement 7: 執行受限 H2-Lite 工作流

**User Story:** 身為開發團隊，我希望 Agent 工作流具有固定邊界與明確輸出，以便在兩天內完成並在現場穩定執行。

#### Acceptance Criteria

1. `WHEN` run 開始，`THE SYSTEM SHALL` 依序執行 Planner、並行的 Market Worker 與 Research Agent、Evidence Processor、Arbiter、Renderer。
2. `THE SYSTEM SHALL` 使 Market Worker 僅執行 deterministic Python 工具，不呼叫 LLM。
3. `THE SYSTEM SHALL` 使 Research Agent 為 bounded LLM agent，且所有元件僅交換固定 JSON schema，不允許元件間自由聊天或無限循環；same-process orchestration 必須使用 bounded `asyncio`。
4. `WHEN` Market Worker 與 Research Agent 執行，`THE SYSTEM SHALL` 讓兩個分支並行，且任一分支 timeout 不得丟棄另一分支已完成的結果。
5. `WHEN` Evidence Processor 完成排序，`THE SYSTEM SHALL` 只將前 20 至 30 筆 Evidence 傳入 Arbiter。
6. `THE SYSTEM SHALL` 讓 Arbiter 以單次受限 LLM 呼叫產出 typed、schema-validated `AnalysisResult`，且每個 LLM operation 都使用 operation-specific `max_tokens`。
7. `THE SYSTEM SHALL` 讓 Renderer 以 deterministic 模板將 `AnalysisResult` 與 Evidence Ledger 轉為報告，不得呼叫 LLM 直接撰寫全文。
8. `THE SYSTEM SHALL` 以 static-allowlisted `ToolRegistry` compatibility seam 提供每個 stage 的 finite、allowlisted tool plan；stage deadline 是硬性執行控制，MVP 不建立獨立 token accounting、quota database、tool-budget service 或 usage dashboard。
9. `WHEN` Bedrock structured output 未通過 schema validation，`THE SYSTEM SHALL` 禁止 raw unvalidated LLM output 進入 Renderer 或 artifacts，最多執行 Requirement 8 核准的一次 repair attempt；repair 後仍失敗時必須進入 deterministic fallback。
10. `WHEN` Silver success is evaluated, `THE SYSTEM SHALL` 至少保留一次使用 baseline live market 與 research paths 的 schema-valid Bedrock result，並分別保留成功的 deterministic fallback 測試結果；fallback-only execution 不符合 Silver success gate，且 fallback 不得偽裝成成功的 live AI run。
11. `THE SYSTEM SHALL` 分離 Amazon Bedrock reasoning 與 deterministic rendering，且不得因本 Requirement 推定 Bedrock access、model、IAM 或 region 已驗證通過。

### Requirement 8: 遵守 15 分鐘 Deadline

**User Story:** 身為競賽評審，我希望系統在單次 15 分鐘時限內可靠交付，以便現場流程不被外部服務延遲拖垮。

#### Acceptance Criteria

1. `WHEN` 正式 run 開始，`THE SYSTEM SHALL` 以 900 秒為外部硬性 deadline，並以 12 分鐘內完成分析、13 分鐘前完成全部 artifacts 為內部 deadline。
2. `THE SYSTEM SHALL` 將題意解析與 plan、並行取證、Evidence 處理、Arbiter 與 render、驗證與 artifacts 的預算分別限制為 0.5、4、1.5、2.5、2 分鐘，另保留 1.5 分鐘內部緩衝。
3. `WHEN` run 到達第 12 分鐘，`THE SYSTEM SHALL` 取消所有非必要外部呼叫並優先完成驗證與 artifacts。
4. `WHEN` 剩餘時間不足，`THE SYSTEM SHALL` 依 H3、optional context adapter、反方訊號二次搜尋的順序跳過非核心工作。
5. `THE SYSTEM SHALL` 將單一 adapter call timeout 限制在 45 秒內，最多 retry 一次；retry 必須共用 stage deadline，不得增加總時限。
6. `WHEN` LLM 結構化輸出不符合 schema，`THE SYSTEM SHALL` 最多執行一次修復重試，且修復必須共用原 stage deadline。
7. `THE SYSTEM SHALL` 為每個 run 保存明確 internal run state 與每個 stage 的 pending、running、completed、degraded 或 failed status；每個外部或 reasoning stage 必須具有 deadline 或 timeout，且到期後不得無限等待。
8. `WHEN` run 結束，`THE SYSTEM SHALL` 以 `completed|degraded|failed|cancelled` 表示 terminal state；`cancelled` 僅保留 cancellation-compatible seam，不要求 cancellation UI、remote Job API 或 durable workflow。
9. `IF` stage timeout 或 deadline 使部分工作無法完成，`THE SYSTEM SHALL` 保留已完成結果、記錄降級原因並允許 partial completion。

### Requirement 9: 在失敗時產生誠實的降級結果

**User Story:** 身為評審，我希望部分資料源或 LLM 失敗時系統仍能交付可檢視結果，以便確認 prototype 具備實際可行性。

#### Acceptance Criteria

1. `IF` 單一 API timeout 或失敗，`THE SYSTEM SHALL` 記錄錯誤並使用其他可用來源繼續。
2. `IF` Market Worker 或 Research Agent 任一分支失敗，`THE SYSTEM SHALL` 將該類資料標示 unavailable，保留另一分支結果並產生降級報告。
3. `IF` 找不到第一手來源，`THE SYSTEM SHALL` 使用可追溯的次級來源、依規則降低 reliability 並揭露缺口。
4. `IF` 所有外部來源失效但主辦方 OHLCV 可用，`THE SYSTEM SHALL` 輸出 OHLCV 分析、錯誤紀錄與資料不足說明。
5. `IF` Arbiter 經一次 schema 修復仍失敗，`THE SYSTEM SHALL` 由 Renderer 以 Ledger facts 與資料不足聲明產出 deterministic fallback report，且四項 artifacts 仍須齊全。
6. `IF` 現有 Evidence 無法可靠回答問題，`THE SYSTEM SHALL` 明確回答目前無法可靠判定，並列出需要的新資料，不得編造結論。

### Requirement 10: 增量產生固定 Artifacts 與可重現紀錄

**User Story:** 身為競賽評審，我希望取得固定格式的報告、證據、執行紀錄與設定，以便重建系統如何得到結果。

#### Acceptance Criteria

1. `WHEN` run 開始，`THE SYSTEM SHALL` 立即寫入 `run_config.json`，內容包含 `run_id`、run mode、assets、immutable `analysis_as_of`、模型、prompt/schema 版本與 allowlisted provider/config summary。
2. `WHILE` run 執行，`THE SYSTEM SHALL` 以串流方式增量寫入 `execution_log.jsonl`。
3. `WHEN` 每個 tool 或 agent call 執行，`THE SYSTEM SHALL` 在 Execution Log 記錄 stage、tool、開始、結束、timing、status、degradation、failure information 與摘要，並另記 progress event；prompt 只記版本引用，不記全文。
4. `WHEN` Evidence Ledger 完成，`THE SYSTEM SHALL` 立即寫入 `evidence.json`。
5. `WHEN` Renderer 完成，`THE SYSTEM SHALL` 寫入 `final_report.md`。
6. `THE SYSTEM SHALL` 固定使用 `final_report.md`、`evidence.json`、`execution_log.jsonl`、`run_config.json` 四個檔名，並保持 UI 與四項 artifacts 的 `run_id` 一致。
7. `THE SYSTEM SHALL` 將來源、參數、prompt/schema 版本與 deterministic 指標參數記錄到足以重建該次結果的程度。
8. `THE SYSTEM SHALL` 禁止 API keys、`.env` 內容、私有 credentials 或 prompt 全文進入 UI、logs、artifacts 與 repository。
9. `IF` a run is partial or degraded and the local artifact directory remains writable, `THE SYSTEM SHALL` produce all four fixed artifacts and clearly record limitations, missing capabilities, and terminal state. `IF` an artifact cannot be written, `THE SYSTEM SHALL` identify the exact missing filename and write failure in stdout and every remaining writable log or configuration artifact. PDF and HTML SHALL NOT be required MVP artifacts.
10. `THE SYSTEM SHALL` 以 typed Artifact Store protocol 寫入 deterministic local artifact directory，並只保留 future persistence port 供未來 run summaries 與 artifact references 使用；MVP 不要求 persistent implementation。

### Requirement 11: 產出可解釋且不構成投資建議的報告

**User Story:** 身為加密市場使用者，我希望快速讀懂直接答案、依據、反方訊號與限制，同時不被誤導為交易指令。

#### Acceptance Criteria

1. `WHEN` 產生 Final Report，`THE SYSTEM SHALL` 使用繁體中文並包含：直接回答、市場狀況與時間範圍、已確認事實、主要支持證據、主要反方或矛盾證據、推論、結論、信心與原因、限制與資料缺口、invalidation conditions、後續觀察重點。
2. `THE SYSTEM SHALL` 在報告中明確區分 fact、inference 與 conclusion，且所有市場數值都可對應 deterministic tool output。
3. `THE SYSTEM SHALL` 使用 `high|medium|low` 與理由表達 confidence，不得將其包裝成未經可驗證校準的精確機率。
4. `THE SYSTEM SHALL` 禁止明確買入、賣出、加倉、減倉、資產配置或個人化投資建議，Renderer 必須以字串 lint 作最後防線。
5. `WHEN` run 發生降級，`THE SYSTEM SHALL` 在報告中呈現 degradation notes，不得把 partial result 描述為完整分析。

### Requirement 12: 提供可 Demo 的 Streamlit UI

**User Story:** 身為競賽評審，我希望在單一介面觀察分析進度並檢視交付物，以便快速判斷系統是否真的執行完整流程。

#### Acceptance Criteria

1. `THE SYSTEM SHALL` 提供 Streamlit UI，讓使用者輸入問題與幣種，並由同一 process 呼叫 application service。
2. `WHILE` run 執行，`THE SYSTEM SHALL` 顯示目前 stage、成功來源、失敗來源與降級狀態。
3. `WHEN` artifacts 可用，`THE SYSTEM SHALL` 在 UI 顯示 Final Report、Evidence 與 Execution Log，並提供四項 artifacts 的檢視或下載能力。
4. `THE SYSTEM SHALL` 在 UI 清楚顯示 `official|rehearsal|demo`，且 recorded fallback 不得被誤認為 live run。
5. `THE SYSTEM SHALL` 不提供交易或下單操作。
6. `THE SYSTEM SHALL` 透過 typed progress sink 或 progress contract 接收 same-process `ApplicationService` 的 in-process progress events；MVP 使用同一 Python process 與 in-memory state，不要求 remote progress transport。

### Requirement 13: 安全處理跨幣比較

**User Story:** 身為評審，我希望跨幣比較使用可比較的量化尺度，以便避免把不同幣種的 base-asset 成交量直接比較而得到錯誤結論。

#### Acceptance Criteria

1. `WHEN` 請求包含兩個資產，`THE SYSTEM SHALL` 讓相關 Claim 的 `assets` 與 `time_range` 明確標示比較適用範圍。
2. `THE SYSTEM SHALL` 禁止直接比較不同幣種以各自 base asset 計量的 `volume`。
3. `WHEN` 執行跨幣比較，`THE SYSTEM SHALL` 使用報酬、波動、相對變化、各自 rolling z-score，或 live API 的 quote volume 等可比較尺度。
4. `WHEN` 跨幣資料來自不同來源或時間截點，`THE SYSTEM SHALL` 在 Evidence 與報告揭露來源與時間範圍，不得暗示為同質資料。

### Requirement 14: 保留但不誇大 H3 Extension

**User Story:** 身為競賽評審，我希望能分辨已完成的 H2-Lite 與未承諾的辯論擴充，以便依真實完成度評分。

#### Acceptance Criteria

1. `THE SYSTEM SHALL` 將 `enable_conditional_debate` 預設為 `false`，且 MVP Conflict Detector stub 永遠回傳 no material conflict。
2. `WHEN` H3 flag 關閉或 stub 執行，`THE SYSTEM SHALL` 保持 H2-Lite core 行為與 artifacts 不受影響。
3. `THE SYSTEM SHALL` keep H3 Conditional Debate implementation outside Bronze, Silver, Gold, every Feature Freeze exception, and the formal two-day delivery period.
4. `WHILE` only the disabled H3 extension interface exists, `THE SYSTEM SHALL` label H3 as unimplemented in the UI, presentation, and documentation and shall not claim that a live run used Bull, Bear, or Judge.

**Post-hackathon Future Work note — non-normative for MVP Acceptance:** A separately approved H3 implementation is intended to use Requirement 6's deterministic material-conflict rule, at most one Bull/Bear round, existing Evidence IDs, the feature flag, and bounded deadline/token controls. On failure or insufficient time, the intended route returns to Arbiter.

### Requirement 15: 部署與競賽驗收

**User Story:** 身為四人開發團隊，我希望用最小 AWS 部署與固定測試矩陣驗證產品，以便在兩天內交付可開啟的 Demo 與可審查 repository。

#### Acceptance Criteria

1. `THE SYSTEM SHALL` 能以單一 Docker image 部署至 ECR 與單一 EC2，並以 docker compose 啟動；S3、CloudWatch 與 ECS 不列入 MVP 驗收。
2. `THE SYSTEM SHALL` 將 artifacts 儲存在本機檔案，並將 structured JSONL 同步輸出至 stdout。
3. `WHEN` 執行 Gold 資產驗收，`THE SYSTEM SHALL` 以 two different assets 各自完成一個 independent single-asset run；額外資產為 optional、non-blocking，且 dual-asset comparison 不屬於 Gold 必要條件。
4. `WHEN` 執行 resilience 驗收，`THE SYSTEM SHALL` 覆蓋取證分支 timeout、外部來源全失效、schema error、Arbiter failure fallback 與 H3 flag 關閉情境。
5. `BEFORE` 競賽提交，`THE SYSTEM SHALL` 完成 Bronze fixture gate 與一次完整、計時、模擬評審流程的 Gold rehearsal，並在第 13 分鐘前產出四項 artifacts；額外 rehearsals 為 optional，且不得延遲 deployment、submission 或 Feature Freeze。
6. `BEFORE` repository 提交，`THE SYSTEM SHALL` 完成 secret scan，且 repository 應包含 source、config example、執行說明與 Kiro spec/steering/task history。
7. `WHEN` Gold local Exit 發生或 Day 2 midday 到達，取較早者，`THE SYSTEM SHALL` 觸發 Feature Freeze，並依 Staged Acceptance 第 7 項限制後續工作。

## 3. Scope Guard

- MVP：Bronze、Silver 與 Gold 的 Staged Acceptance、Requirements 1 至 13、Requirement 14 的預設關閉 stub 行為，以及 Requirement 15 的 core 部署與驗收。
- Compatibility seams：typed `SourceAdapter`、static-allowlisted `ToolRegistry`、Artifact Store protocol、progress sink/contract、future persistence port，以及 same-process async `ApplicationService` boundary。MVP implementations 使用 local filesystem、in-memory state、同一 Python process 與 bounded `asyncio`；這些是 typed boundaries，不是完整 infrastructure requirements。
- Post-hackathon Future Work：Platinum、CoinGecko live adapter、完整 five-asset validation matrix 與 calibration、額外 provider integration、PDF/HTML、額外 visualization、dual-asset comparison，以及 H3 實際 Bull/Bear/Judge 流程。
- 非 MVP Production Infrastructure：Database、Queue、broker、Job API、independent service/worker fleet、polling、SSE、WebSocket、DLQ、scheduler、authentication service、horizontal scaling、S3、CloudWatch 與 ECS。任何 Bronze、Silver 或 Gold Acceptance Criteria 均不得要求這些項目。
- H3 與其他 Future Work 條款只約束未來擴充方式，不表示本次兩天開發承諾實作，也不表示任何功能或驗證已完成。
