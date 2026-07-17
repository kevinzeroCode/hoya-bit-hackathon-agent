# HOYA Market Agent Requirements

## 1. Introduction

本文件將核准版產品規格轉為可由 Kiro 追蹤與驗收的需求。產品是在競賽現場接收指定題目與幣種後，於 15 分鐘內完成多源、可回溯、可誠實降級的繁體中文加密市場分析。

MVP 唯一承諾為 H2-Lite：`Planner -> Market Worker + Research Agent -> Evidence Processor -> Arbiter -> Renderer`。H3 Conditional Debate 僅保留預設關閉的 extension interface，不屬於兩天 MVP 承諾。

本文使用 EARS 語法；`THE SYSTEM SHALL` 表示可驗收的強制行為。

## 2. Requirements

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

### Requirement 3: 取得並計算可重現的市場資料

**User Story:** 身為市場分析使用者，我希望市場數值來自可重現工具與清楚標示的來源，以便驗證報告中的量化依據。

#### Acceptance Criteria

1. `WHEN` Market Worker 計算 OHLCV 指標，`THE SYSTEM SHALL` 使用 deterministic 程式碼，並把資料區間與計算參數記錄於 artifacts。
2. `THE SYSTEM SHALL` 將主辦方 Daily OHLCV CSV 視為共同歷史基準，且不得推定其上游為任何特定交易所。
3. `WHEN` 需要 2026-05-31 之後的 live 資料或現場 snapshot，`THE SYSTEM SHALL` 以 Binance public REST API 為 canonical live source，並以 CoinGecko 作為 live fallback。
4. `WHEN` 同一分析跨越 CSV 與 live API，`THE SYSTEM SHALL` 將 2026-06-01 標示為來源切換點，並在 Evidence 與報告揭露來源差異。
5. `WHEN` 首次執行 live-source rehearsal，`THE SYSTEM SHALL` 對 BTC、ETH、SOL、BNB、XRP 的 2026-05-01 至 2026-05-31 close 執行 CSV／Binance 重疊區間差異檢查，並將結果保留於 run config 或 steering；差異顯著時必須在報告揭露。
6. `WHEN` 存取 live API，`THE SYSTEM SHALL` 保存 endpoint、交易對、查詢參數、UTC 範圍與 fetched time。
7. `WHEN` 使用 Alternative.me Fear & Greed Index，`THE SYSTEM SHALL` 將其標示為全市場而非單一幣種指標，且不得單獨支撐單幣結論。

### Requirement 4: 完成多源取證並誠實揭露缺口

**User Story:** 身為競賽評審，我希望每次正常分析能結合不同類型與不同上游的資料，以便看見真正的多源驗證，而不是重複轉載堆疊。

#### Acceptance Criteria

1. `WHEN` 正常 live run 的來源可用，`THE SYSTEM SHALL` 以每個 run 至少三種 `source_type`、三個不同 `independence_group`，且至少一個第一手或官方來源為取證目標。
2. `THE SYSTEM SHALL` 將主辦方 CSV、Binance／CoinGecko 市場資料、CryptoPanic／新聞 RSS、官方公告及 Alternative.me context source 依其實際取得狀態記錄，不得把未取得來源算入來源數量。
3. `WHEN` 官方 Blog 或公告頻道無法取得，`THE SYSTEM SHALL` 以 best-effort 結束該查詢並在報告揭露缺口，而非阻塞整個 run。
4. `IF` 正常 run 未達三種 source types、三個獨立上游或第一手來源目標，`THE SYSTEM SHALL` 仍完成報告，並降低適當 confidence 或明確揭露資料不足。
5. `THE SYSTEM SHALL` 分開計算來源類型多樣性與上游來源獨立性；不同 `source_type` 不得自動視為不同 `independence_group`。

### Requirement 5: 建立可回溯 Evidence Ledger

**User Story:** 身為評審，我希望每項證據都有來源、時間、引用內容與關聯主張，以便從結論回溯原始依據並辨識重複來源。

#### Acceptance Criteria

1. `WHEN` Evidence Processor 接收一筆來源內容，`THE SYSTEM SHALL` 產生符合核准 `EvidenceItem` schema 的項目，包含 evidence ID、asset、source type/name/URL、published/fetched time、query or parameters、content reference、normalized fact、reliability、independence group、content hash 與 cache/stale 欄位。
2. `THE SYSTEM SHALL` 讓 EvidenceItem 保持無立場；支持、反對或中性立場只能記錄於 Claim-Evidence Link。
3. `WHEN` 正規化後的原始內容具有相同 SHA-256 `content_hash`，`THE SYSTEM SHALL` 將其視為精確重複內容，不實作近似相似度模型。
4. `WHEN` 可辨識原始發布者，`THE SYSTEM SHALL` 以原始發布者作為 `independence_group`；否則以來源 URL 的註冊網域歸群。
5. `THE SYSTEM SHALL` 依 always-included steering 的靜態 source-type／第一手來源規則指定 `high|medium|low` reliability，不使用 LLM 或動態模型評分可信度。
6. `THE SYSTEM SHALL` 禁止無法回溯的內容支撐關鍵結論，且禁止 LLM 自行產生市場數值。
7. `WHEN` Evidence List 匯出，`THE SYSTEM SHALL` 至少提供 source、fetched time、content reference 與 related claim 四個競賽欄位。

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
3. `THE SYSTEM SHALL` 使 Research Agent 為 bounded LLM agent，且所有元件僅交換固定 JSON schema，不允許元件間自由聊天或無限循環。
4. `WHEN` Market Worker 與 Research Agent 執行，`THE SYSTEM SHALL` 讓兩個分支並行，且任一分支 timeout 不得丟棄另一分支已完成的結果。
5. `WHEN` Evidence Processor 完成排序，`THE SYSTEM SHALL` 只將前 20 至 30 筆 Evidence 傳入 Arbiter。
6. `THE SYSTEM SHALL` 讓 Arbiter 以單次受限 LLM 呼叫產出符合 `AnalysisResult` schema 的結果，並用 `max_tokens` 限制輸出。
7. `THE SYSTEM SHALL` 讓 Renderer 以 deterministic 模板將 `AnalysisResult` 與 Evidence Ledger 轉為報告，不得呼叫 LLM 直接撰寫全文。

### Requirement 8: 遵守 15 分鐘 Deadline

**User Story:** 身為競賽評審，我希望系統在單次 15 分鐘時限內可靠交付，以便現場流程不被外部服務延遲拖垮。

#### Acceptance Criteria

1. `WHEN` 正式 run 開始，`THE SYSTEM SHALL` 以 900 秒為外部硬性 deadline，並以 12 分鐘內完成分析、13 分鐘前完成全部 artifacts 為內部 deadline。
2. `THE SYSTEM SHALL` 將題意解析與 plan、並行取證、Evidence 處理、Arbiter 與 render、驗證與 artifacts 的預算分別限制為 0.5、4、1.5、2.5、2 分鐘，另保留 1.5 分鐘內部緩衝。
3. `WHEN` run 到達第 12 分鐘，`THE SYSTEM SHALL` 取消所有非必要外部呼叫並優先完成驗證與 artifacts。
4. `WHEN` 剩餘時間不足，`THE SYSTEM SHALL` 依 H3、optional context adapter、反方訊號二次搜尋的順序跳過非核心工作。
5. `THE SYSTEM SHALL` 將單一 adapter call timeout 限制在 45 秒內，最多 retry 一次；retry 必須共用 stage deadline，不得增加總時限。
6. `WHEN` LLM 結構化輸出不符合 schema，`THE SYSTEM SHALL` 最多執行一次修復重試，且修復必須共用原 stage deadline。

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

1. `WHEN` run 開始，`THE SYSTEM SHALL` 立即寫入 `run_config.json`，內容包含 run config、模型、prompt/schema 版本與來源狀態。
2. `WHILE` run 執行，`THE SYSTEM SHALL` 以串流方式增量寫入 `execution_log.jsonl`。
3. `WHEN` 每個 tool 或 agent call 執行，`THE SYSTEM SHALL` 記錄開始、結束、狀態與摘要，並另記 stage 事件；prompt 只記版本引用，不記全文。
4. `WHEN` Evidence Ledger 完成，`THE SYSTEM SHALL` 立即寫入 `evidence.json`。
5. `WHEN` Renderer 完成，`THE SYSTEM SHALL` 寫入 `final_report.md`。
6. `THE SYSTEM SHALL` 固定使用 `final_report.md`、`evidence.json`、`execution_log.jsonl`、`run_config.json` 四個檔名，並保持 UI 與四項 artifacts 的 `run_id` 一致。
7. `THE SYSTEM SHALL` 將來源、參數、prompt/schema 版本與 deterministic 指標參數記錄到足以重建該次結果的程度。
8. `THE SYSTEM SHALL` 禁止 API keys、`.env` 內容、私有 credentials 或 prompt 全文進入 UI、logs、artifacts 與 repository。

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
3. `IF` 未來實作 H3，`THE SYSTEM SHALL` 只使用 Requirement 6 的 material conflict rule 觸發，不使用 LLM classifier。
4. `IF` 未來實作 H3，`THE SYSTEM SHALL` 最多執行一輪 Bull/Bear 分析、只引用既有 Evidence IDs，並受 feature flag、剩餘 deadline 與 token budget 約束。
5. `IF` H3 失敗或剩餘時間不足，`THE SYSTEM SHALL` 直接回到 Arbiter 並繼續 H2-Lite 流程。
6. `WHILE` H3 尚未通過 rehearsal 並留存紀錄，`THE SYSTEM SHALL` 在 UI、簡報與文件中將其標示為未實作的 extension architecture，不得宣稱 live run 已啟用。

### Requirement 15: 部署與競賽驗收

**User Story:** 身為四人開發團隊，我希望用最小 AWS 部署與固定測試矩陣驗證產品，以便在兩天內交付可開啟的 Demo 與可審查 repository。

#### Acceptance Criteria

1. `THE SYSTEM SHALL` 能以單一 Docker image 部署至 ECR 與單一 EC2，並以 docker compose 啟動；S3、CloudWatch 與 ECS 不列入 MVP 驗收。
2. `THE SYSTEM SHALL` 將 artifacts 儲存在本機檔案，並將 structured JSONL 同步輸出至 stdout。
3. `WHEN` 執行固定 fixture 測試矩陣，`THE SYSTEM SHALL` 覆蓋 BTC、ETH、SOL、BNB、XRP 各一題；保留雙幣契約時再覆蓋一題跨幣比較。
4. `WHEN` 執行 resilience 驗收，`THE SYSTEM SHALL` 覆蓋取證分支 timeout、外部來源全失效、schema error、Arbiter failure fallback 與 H3 flag 關閉情境。
5. `BEFORE` 競賽提交，`THE SYSTEM SHALL` 完成全部 fixture 測試與至少三次 live-source rehearsal，且每次 rehearsal 都在第 13 分鐘前產出四項 artifacts。
6. `BEFORE` repository 提交，`THE SYSTEM SHALL` 完成 secret scan，且 repository 應包含 source、config example、執行說明與 Kiro spec/steering/task history。

## 3. Scope Guard

- MVP：Requirements 1 至 13、Requirement 14 的預設關閉 stub 行為，以及 Requirement 15 的 core 部署與驗收。
- 非 MVP：H3 實際 Bull/Bear/Judge 流程、鏈上／宏觀／社群 adapters、S3、CloudWatch、ECS。
- H3 的條件式條款只約束未來擴充方式，不表示本次兩天開發承諾實作。
