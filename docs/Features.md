# HOYA Market Agent — 功能規格（能力目錄）

> **① of ④ — design-pipeline 第一份產出，也是這一組文件的入口。**
> 下一份：[Tech-Stack-Plan.md](Tech-Stack-Plan.md)
>
> 閱讀順序：① Features → ② [Tech-Stack-Plan](Tech-Stack-Plan.md) → ③ [Architecture-FileMap](Architecture-FileMap.md)
> → ④ [Implementation-Plan](Implementation-Plan.md)（無法 headless 驗證的人工檢查清單在其 §3.2）。
> 「誰正在做什麼、哪些路徑已凍結」不屬本組，見 [`docs/ACTIVE_WORK.md`](ACTIVE_WORK.md)。

> **這份文件是衍生視圖，不是新的真相來源。**
> 規範性權威仍是 `.kiro/specs/hoya-market-agent/`（requirements / design / tasks）與 `.kiro/steering/`
> （尤其 `evidence-contracts.md`）。本文只把散落在那些文件裡的**能力面**收攏成一份可勾選的目錄，
> 供 ②–④ 引用。**若本文與 `.kiro/` 衝突，以 `.kiro/` 為準**，並回報以便修正本文。

HOYA Market Agent 是一個**競賽導向、Evidence-first 的加密市場分析 agent**：在競賽現場接收臨時公布的
自然語言題目與指定幣種（BTC / ETH / SOL / BNB / XRP 之一至二），在 **15 分鐘硬性時限**內整合多源資料，
產出一份**可回溯、會誠實揭露自身資料缺口**的繁體中文分析報告，外加三份可審查的交付物。
產品定位不是預測價格，而是「在時限內交付一份知道自己哪裡不知道的分析」。

參照對象不是某個競品，而是**主辦方的命題文件**與既有的 H2-Lite 核准設計；本文的能力面即從那兩者反推。

---

## 0. 這是什麼、不是什麼

- **這是能力目錄（reference catalog）**：列出這個產品「做得到什麼」的完整面，供下游文件指名引用。
- **這裡不決定技術選型**，也不決定「兩天內做到哪一層」——前者屬 ②，後者屬 ④ 的 Bronze / Silver / Gold 分階。
  本文只在必要處以「MVP 未實作」標記既成事實（那是 `.kiro` 已核准的決定，不是本文新增的裁決）。
- **這裡不重新定義任何欄位值**。§5 的契約詞彙表是 `evidence-contracts.md` 的**引用視圖**，
  用途是讓 ③④ 有一個穩定的地方可以指。欄位語意有疑問時看 `evidence-contracts.md`。

### 資料來源（本文的每一條都可回溯到這裡）

| 來源 | 提供了什麼 |
|---|---|
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 1–16 的 EARS 驗收條件、Staged Acceptance D1–D8 |
| `.kiro/specs/hoya-market-agent/design.md` | H2-Lite 執行流程、deadline 里程碑、失敗降級表、§19 創意層 |
| `.kiro/steering/evidence-contracts.md` | Evidence / Claim / Link / Result / Artifact 的**規範性**欄位與不變量 |
| `.kiro/steering/competition-rules.md` | 競賽護欄、Coin-Agnostic Source Policy、靜態 reliability 表 |
| `.kiro/steering/product.md` | 產品承諾、優先序、報告語氣、非目標 |
| `.kiro/steering/tech.md`、`structure.md`、`testing.md` | 鎖定技術棧、模組邊界、測試分層 |
| `docs/system-design.md`、`docs/ACTIVE_WORK.md` | FR/NFR 概觀、目前實作進度與四人分工現況 |
| `(HOYA BIT) 命題文件 …docx`、`HOYA_BIT_crypto_market_dataset/README.md` | 命題硬性要求、主辦方五幣 Daily OHLCV 基準資料 |

> **圖例：** ⭐ = 招牌能力（產品之所以是這個產品的部分）｜🚫 = 明確排除（`.kiro` 已核准為
> 非 MVP / post-hackathon Future Work，列在此處是為了讓下游文件知道「不要做」）。

---

HOYA Market Agent 有**四項主要功能**：**取證（Evidence Acquisition）**、
**推理與裁決（Bounded Reasoning）**、**交付與揭露（Delivery & Disclosure）**、
**信任提煉（Trust Distillation，創意加值層）**，
外加一項在明確加選第二幣時啟動的 **雙幣比較（Dual-Asset Comparison，§4.5）**。

---

## 1. 取證 ⭐

把「多個來源」變成「一份無立場、可回溯、去重過、標好可信度與獨立性的證據帳本」。

**建立分析請求**
- 接受一段自然語言題目（視為 untrusted input，長度上限由設定決定）。
- 接受一至二個支援資產；內部契約為 `assets: string[]`，UI 預設單幣，第二幣須明確加選（§4.5）。
- 每個 run 產生唯一 `run_id`，並保留原始題目、`assets`、`requested_at`、`deadline_seconds`、`run_mode`、H3 flag。
- 題目文字提到的幣與 `assets` 不一致時，**以 `assets` 為準**並在 execution log 記 warning。
- run 開始時把 `analysis_as_of` **凍結**；`official` 模式一律凍結為當下 UTC 且不接受使用者自訂。

**市場資料取得（deterministic，⭐ 不呼叫 LLM）**
- 讀取主辦方 Daily OHLCV CSV（`{ASSET}_daily_ohlcv.csv`）作為共同歷史基準。
- 以 Binance public REST（`/api/v3/klines`）取 UTC 日 K 作為 designated baseline live market source。
- 以 Binance `/api/v3/ticker/24hr` 取最新 snapshot 與 quote volume。
- 只採 `analysis_as_of` 之前**已完成**的 UTC 日 K；當日未完成資料另標為 intraday snapshot，不與完整日 K 混用。
- CSV 與 live API 跨接時，標示 **2026-06-01 來源切換點**並在 Evidence 與報告揭露來源差異。
- 保留 endpoint、交易對、查詢參數、UTC 範圍與 `fetched_at`，使計算可重建。
- baseline live market source 失敗時產生誠實 partial/degraded，**不得宣稱切換到第二個 live provider**。

**市場指標計算（deterministic ⭐）**
- 區間報酬 `close_t / close_(t-n) - 1`。
- 已實現波動度（宣告 return 頻率與 window；若年化須標示年化因子）。
- 回撤 `close_t / cumulative_max_close_t - 1`；最大回撤取 window 內最小值。
- 量能變化與 rolling volume z-score（**只與該幣自身歷史比較**）。
- 區間位置（range position）與相對變化。
- 缺 bar 時輸出 unavailable，**不 forward-fill** 造出可算的假指標。

**研究資料取得**
- CryptoPanic 新聞（依 currency 過濾；需 `CRYPTOPANIC_API_TOKEN`，缺 token 則停用該 adapter 而非讓 run 失敗）。
- 新聞 RSS feed。
- 幣種官方 Blog / 公告頻道（best-effort；取不到就揭露缺口，不阻塞 run）。
- Alternative.me Fear & Greed（**全市場** context，`asset=null`，不得單獨支撐單幣結論）。
- 一次 bounded LLM 抽取，把取回的來源紀錄轉成 `EvidenceDraft`；**只能引用該紀錄的欄位，不得虛構文章內容**。
- 每個 stage 的可用操作來自 static `ToolRegistry` allowlist；**LLM 與外部內容都不得擴張 allowlist**。
- 取回的外部內容一律視為 **untrusted data**：其中的指令、prompt、政策式文字只能當引用資料保存，
  不得改寫系統政策、deadline、token 上限、工具/網域 allowlist 或 artifact 契約。

**Evidence 處理（deterministic ⭐）**
- 驗證 draft schema；沒有可解析來源參照的事實直接拒收。
- 正規化 URL、時間戳、空白、資產名與 source type。
- 以 SHA-256 `content_hash` 做**精確**去重（🚫 不做語意/近似相似度分群）。
- 依「原始發布者 → 來源 URL 註冊網域 → 設定的 provider ID」順序指定 `independence_group`。
- 依**靜態表**指定 `high|medium|low` reliability（🚫 LLM 不得指派或升級）。
- 記錄 cache / stale metadata；缺 published time 時如實留白並揭露，**不得捏造時間**。
- 配發 run-local 穩定 ID（`ev_001`、`ev_002`…）。
- 依 reliability、直接性、時效與來源多樣性排序，只把前 20–30 筆送進 Arbiter。
- deterministic 偵測 material conflict 並產出 `ConflictIndicator`。
- **source type 多樣性與 upstream 獨立性分開計算**；不同 `source_type` 不自動等於不同 `independence_group`。
- 正常 live run 的取證目標：≥3 種 `source_type`、≥3 個 `independence_group`、≥1 個第一手/官方來源；
  未達標**仍完成報告**，但降低 confidence 或明確揭露資料不足。

---

## 2. 推理與裁決 ⭐

在固定 schema 與固定次數的 LLM 呼叫內，把證據變成分層、可回溯、保留反方的主張。

**Planner（1 次 bounded LLM 呼叫）**
- 只依題目與可用能力產出 `ResearchPlan`（bounded 研究步驟、時間範圍、需要的 Evidence 類型）。
- 🚫 不產出市場結論、不選擇任意 provider / tool / host / URL。
- Planner 失敗時改用「依 `assets` 與預設 lookback」的 deterministic 預設 plan。

**Claim 分層**
- 三種 `ClaimType`：`fact` → `inference` → `conclusion`。
- `fact` 的 `based_on_claim_ids` 為空，且至少要有一條非 neutral 的 Evidence Link。
- `inference` 經 `based_on_claim_ids` 回溯 fact；`conclusion` 回溯 inference 或 fact。
- 依賴關係必須在同一份 result 內解析且構成 **DAG（不得循環）**。
- 每個 Claim 帶 `assets`、`time_range`、`confidence`、`limitations`、`invalidation_conditions`。
- 🚫 Claim 不得包含買賣或部位大小指令。

**Claim-Evidence Link ⭐**
- 立場（`supports|opposes|neutral`）**只存在於 Link**；`EvidenceItem` 本身永遠無立場。
- 同一筆 Evidence 可以支持某個 claim、同時反對另一個 claim。
- `neutral` 提供脈絡，但**不能**滿足 conclusion 的證據覆蓋要求。

**Material conflict 與 confidence ⭐**
- material conflict 的唯一判定：同一 claim 同時有 supports 與 opposes、雙方 reliability ≥ medium、
  且至少一對來自**不同** `independence_group`。
- 成立時**保留雙方 Evidence**並把該結論 confidence 壓到 `low`；整體 confidence 不得為 `high`。
- confidence 僅 `high|medium|low` + 理由（`confidence_rationale`）；🚫 禁止未校準的精確機率。
- 每個 conclusion 必須有 supporting evidence，否則明確標 `insufficient_data=true`（整體 confidence 隨之為 `low`）。
- 找不到可信反方訊號時，**列出已查詢的來源**並把「未找到反方」列為限制，🚫 不得假造反方。

**Arbiter（1 次 bounded LLM 呼叫）**
- 輸入為排序後上限 30 筆 Evidence 的 ID 與 normalized fact，🚫 不餵無界原始網頁。
- 輸出必須通過 `AnalysisResult` schema 驗證、所有 evidence/claim 參照可解析、claim graph 無環、confidence 符合上限。
- 驗證失敗時最多 **1 次** schema repair，且共用同一個 stage deadline。
- repair 仍失敗 → deterministic fallback：由 ledger facts 組出低信心結果並列出所有缺失能力。
- 🚫 未通過驗證的原始 LLM 輸出**永不**進入 Renderer 或 artifacts。

**H3 Conditional Debate（明確未實作）**
- `enable_conditional_debate` 預設 `false`；即使傳 `true` 也記為 disabled/ignored 並直接 route 到 Arbiter。
- MVP 唯一實作是 `DisabledConflictExtension`：不做網路呼叫、不做 LLM 呼叫、原樣回傳 indicators。
- UI、簡報與文件都必須標示 H3 為**未實作**，🚫 不得宣稱 live run 用過 Bull / Bear / Judge。
- 🚫 MVP 不建立 Bull / Bear / Judge 的檔案、prompt、task 或測試路徑。

---

## 3. 交付與揭露 ⭐

在時限內把結果變成四份固定檔名的可審查交付物，並讓「這次 run 有多可信」本身也是可見的。

**四項固定 artifacts ⭐**
- `run_config.json` — run 一開始就寫。
- `execution_log.jsonl` — 全程串流增量追加。
- `evidence.json` — Ledger 一完成立刻寫（**不等 Arbiter**，這樣 Arbiter 失敗也不會抹掉可追溯性）。
- `final_report.md` — 最後寫。
- 四份共用同一個 `run_id`，並與 UI 顯示的一致。
- 一律以「同目錄暫存檔 → flush → `os.replace`」原子寫入，避免露出半寫入的 JSON / Markdown。
- partial / degraded run 只要目錄可寫仍須產出**全部四份**，並記錄限制、缺失能力與 terminal state。
- 某份寫不出來時，在 stdout 與所有仍可寫的 log/config artifact 中**指名確切的缺檔檔名**與寫入失敗原因。
- 🚫 PDF / HTML 不是 MVP 必要 artifact。

**繁體中文報告（deterministic Renderer ⭐）**
- 報告由**模板**從 `AnalysisResult` + Ledger 產生；🚫 不讓 LLM 直接寫全文，🚫 不讓 LLM 事後改寫。
- 固定 11 個段落：直接回答／市場狀況與時間範圍／已確認事實／主要支持證據／主要反方或矛盾證據／
  推論／結論／信心與原因／限制與資料缺口／invalidation conditions／後續觀察重點。
  **雙幣 run 另加第 12 個段落「跨幣比較」**（見 §4.5 與 Requirement 17）；單幣 run 不得出現該段落。
- 明確區分 fact / inference / conclusion；所有市場數值都能對應到 deterministic tool output 與 Evidence ID。
- 至少呈現一個反方訊號；沒有就列出查詢過的來源與該限制。
- 🚫 禁止「買入／賣出／加倉／減倉／做多／做空／資產配置」等指示性投資用語 —
  **deterministic 字串 lint 是最後一道防線**，且永遠最後執行。
- 降級時在報告中呈現 degradation notes，🚫 不得把 partial result 描述成完整分析。

**執行紀錄與可重現性**
- 每個 tool / agent call 記 stage、tool、起訖、timing、status、degradation、failure info 與摘要。
- 另記 progress event，讓 UI 不必靠「經過多久」猜狀態。
- **prompt 只記版本與 checksum，🚫 不記全文**；🚫 不記 chain-of-thought、authorization、secrets。
- `run_config.json` 記 schema/prompt/policy 版本、sanitized request、模式、deadline、模型 ID、
  optional key 的**存在布林值（非值）**、fallback/cache/stale 狀態、terminal status 與 artifact checksum。

**誠實性機制 ⭐**
- 三種 run mode（`official|rehearsal|demo`）在 UI、log 與 `run_config.json` 都清楚可辨，且 run 開始後不可變。
- `official` 🚫 禁 fixture、預存答案、舊報告；只允許帶來源時間/cache time/stale 狀態的原始資料 cache。
- `rehearsal` 可用 deterministic fixtures、自訂 `analysis_as_of`、做故障注入，但必須明顯標示。
- `demo` 先試 live，失敗才可用 recorded bundle，且必須顯示 recorded fallback 橫幅與原始取得時間。
- 🚫 fixture run 不得標成 live official；🚫 fallback-only run 不得標成 Silver success。

**Deadline 治理 ⭐**
- 900 秒外部硬限；第 12 分鐘停止分析、第 13 分鐘前四項 artifacts 齊全。
- 以 `time.monotonic()` 算 budget；UTC 只用於落盤時間戳。
- 單次外部呼叫 ≤45 秒、最多 retry 1 次，且 retry 與 schema repair **共用**原 stage deadline，不增加總時限。
- 時間不足時固定跳過順序：**H3 → optional context adapter → 反方訊號二次搜尋**。
- 任一 stage 都必須有 deadline，到期不得無限等待；terminal state 為 `completed|degraded|failed|cancelled`。

**Streamlit 操作介面**
- 首頁就是可操作的分析介面，🚫 不做行銷 landing page。
- 題目輸入 + 一至二幣選擇（限五幣）+ 可見的 run mode 選擇器。
- run 進行中停用 run 按鈕，確保「一次提交 = 一次 application service 呼叫」。
- 六列固定進度：Planner / Market Worker / Research Agent / Evidence Processor / Arbiter / Renderer。
- 顯示成功來源、失敗來源與降級狀態。
- Report / Evidence / Execution Log 三個結果分頁 + 四項 artifacts 下載鈕。
- partial / fallback / cached / stale / rehearsal / recorded-demo 各有常駐標記。
- 🚫 不提供任何交易或下單操作。

---

## 4. 信任提煉（Creativity Layer，Requirement 16）⭐

三個元件，全部 **deterministic、coin-agnostic、可誠實降級、不阻塞核心**。這一層只是把既有嚴謹度
「顯影」出來，🚫 永遠不會變成第二個真相來源。

**Trust Scorecard（每個 conclusion 一張）**
- 由 Ledger + Links 純函數推導五個面向：`source_independence`、`source_diversity`、
  `reliability_mix`、`consistency`、`freshness`。
- 每個面向給固定 ordinal 等級 + **支撐該等級的原始計數**（如 distinct independence groups 數）。
- 必須與該 conclusion 的 `high|medium|low` confidence **一致**：<2 個 independence group 不得標 `strong`；
  存在 material conflict 時 consistency 不得高於 `weak`。
- 🚫 不輸出未校準的精確百分比，🚫 不用單一合成分數冒充精確度。
- 只為 `conclusion` 產生；`fact` / `inference` 不產。

**Market Regime（每個資產一個標籤）**
- 純 OHLCV deterministic 判定，取自固定列舉；由 **Market Worker** 產出。
- **Coin-agnostic**：門檻一律拿該資產**自己的 rolling 歷史**（百分位 / z-score）比，
  🚫 不用跨幣絕對值。
- 打包成 reliability=`high`、source_type=`market` 的 `EvidenceItem`，並保留觸發標籤的指標值與門檻參數，
  讓報告標題也能回溯到 Evidence ID。🚫 LLM 不得指派或改寫標籤。
- 缺 bar 時輸出 `unavailable` 並揭露缺口，🚫 不 forward-fill。

**量化 invalidation 門檻**
- Market Worker 額外產出門檻類 Evidence（近 N 日最高/最低收盤、rolling 量能均值…），
  同樣是 high-reliability `EvidenceItem`。
- `invalidation_conditions` 盡量帶 `metric` / `operator` / `threshold` / `basis_evidence_id`；
  **數值只能引用 deterministic Evidence，🚫 LLM 不得自造**。
- 無法量化時才退回純文字定性條件（仍為合法）。

**這一層的共同規則**
- 🚫 不呼叫 LLM、🚫 不新增外部來源、🚫 不新增阻塞相依。
- 任何面向/標籤/門檻算不出來就標 `unavailable` 並揭露原因，🚫 不編造。
- 🚫 不得產生任何投資建議；Renderer 的禁語 lint 仍在最後把關。
- 🚫 不得延遲四項 artifacts、Bronze 或 Silver。

---

## 4.5 雙幣比較（Requirement 17）⭐

當使用者明確加選第二個幣種時，系統要真的回答「這兩個幣相比如何」，而不是把兩份單幣分析並排。
**這是承諾能力**（命題題型明確包含跨幣比較），排在 Silver 之後、Feature Freeze 之前，
且不得延遲 Gold、部署、彩排或提交。

**單一 run 完成**
- 一個 `run_id`、一個凍結 `analysis_as_of`、一份 Evidence Ledger、一份 `AnalysisResult`、四項固定 artifacts。
- 🚫 不為比較另開第二個 run、🚫 不新增第五項 artifact、🚫 不做跨 run 的 evidence 參照。
- 理由：比較只有在兩個資產的證據進入同一個 Arbiter payload 時才存在；而且 Evidence ID 是 run-local、
  `analysis_as_of` 各 run 各自凍結、artifact 檔名固定四個——拆兩個 run 會同時破壞這三條。

**只用可比較尺度**（Requirement 13）
- 區間報酬差、以各自百分位表達的波動比較、相對強弱比值與其自身歷史百分位、
  同一 provider 同一期間的 quote volume。
- 🚫 **永遠不比較不同幣的 base-asset `volume`。** 無可比較口徑時標 `unavailable`。

**證據配額**
- 兩個資產各自都必須有 Evidence 進入 Arbiter payload；
  🚫 單一資產或單一 source type 不得佔滿 30 筆上限。
- `asset=null` 的全市場項目（如 Fear & Greed）不計入任一資產配額。

**呈現與降級**
- 報告加一個「跨幣比較」段落：兩個資產、共同 `time_range`、所用尺度、比較結果、每個數字的 Evidence ID，
  以及任何來源或期間口徑差異。單幣 run 不得出現此段落。
- Market Regime 維持每資產一個標籤，🚫 不合併。
- 任一資產缺 baseline 市場證據 → 比較標 `unavailable`、揭露缺口、
  仍完成可得資產的單幣分析與四項 artifacts；🚫 不以單幣結果冒稱比較。
- 🚫 比較不得成為相對買賣建議；禁語 lint 仍最後把關。
- Freeze 前未完成 → UI 停用第二幣加選、只收單幣、誠實揭露未交付；🚫 不交付半完成路徑。

---

## 5. 契約詞彙（權威參考表）

這一節是本 doc set 的**指名點**：③④ 需要提到列舉值、檔名或預算時，一律指回這裡，不各自重列。
**欄位語意的規範性擁有者是 `.kiro/steering/evidence-contracts.md`**；下表是它的引用視圖。

### 5.1 輸入契約（`AnalysisRequest` 情境）

| 欄位 | 允許值 / 規則 |
|---|---|
| `question` | 自然語言字串，長度上限由設定決定；視為 untrusted input |
| `assets` | 1–2 個**唯一**支援資產 |
| `requested_at` | ISO 8601 UTC，`Z` 結尾 |
| `analysis_as_of` | run 開始即凍結；`official` 一律當下 UTC 且不可自訂 |
| `deadline_seconds` | 正式 run 為 `900` |
| `run_mode` | `official` \| `rehearsal` \| `demo` |
| `enable_conditional_debate` | 預設 `false`；傳 `true` 也記為 disabled/ignored |

### 5.2 列舉（跨 Python / JSON / prompt / fixture / test **完全同名**）

| 列舉 | 值 |
|---|---|
| `Asset` | `BTC` \| `ETH` \| `SOL` \| `BNB` \| `XRP` |
| `RunMode` | `official` \| `rehearsal` \| `demo` |
| `SourceType` | `official` \| `market` \| `news` \| `onchain` \| `social` \| `macro` |
| `Reliability` | `high` \| `medium` \| `low` |
| `Stance`（**只在 Link 上**） | `supports` \| `opposes` \| `neutral` |
| `ClaimType` | `fact` \| `inference` \| `conclusion` |
| Stage state | `pending` \| `running` \| `completed` \| `degraded` \| `failed` \| `cancelled` |
| Terminal run state | `completed` \| `degraded` \| `failed` \| `cancelled` |
| `WorkerResult.status` | `completed` \| `partial` \| `failed` |
| `TrustLevel`（R16） | `strong` \| `moderate` \| `weak` \| `unavailable` |
| `RegimeLabel`（R16） | `trending_up` \| `trending_down` \| `range_bound` \| `high_volatility` \| `mixed` |
| `InvalidationOperator`（R16） | `lt` \| `lte` \| `gt` \| `gte` |

ID 格式：`ev_001`、`cl_001`、`run_YYYYMMDD_HHMMSS_<suffix>`。所有持久化時間戳為 ISO 8601 UTC + `Z`。
所有跨模組 payload 使用 `extra="forbid"`；文字欄位 strip 後不得為空。

### 5.3 靜態 reliability 表（🚫 LLM 不得調整）

| Reliability | 適用來源 |
|---|---|
| `high` | 主辦方 OHLCV 基準、原生交易所 API 市場數據、已驗證的專案官方公告/feed、輸入皆為 high-reliability evidence 的 deterministic 計算 |
| `medium` | 具名新聞媒體的**原始報導頁**（有 URL 與時間戳） |
| `low` | 只取到聚合/轉載紀錄（未取原頁）、Alternative.me Fear & Greed、社群主張、缺作者/缺時間的摘要、無法查證的二手評論 |

- 轉載未取到原頁一律 `low`，即使它指名了上游發布者。
- 佐證影響的是 **claim confidence**，不是 Evidence 的來源 reliability。
- stale 只是 metadata：可經 deterministic policy 壓 claim confidence，但 Alternative.me 已是 `low`，不再往下降。

### 5.4 confidence rubric 與 deterministic 上限

| 等級 | 條件 |
|---|---|
| `high` | ≥2 個獨立 group 的 high/medium 支持；無 material conflict；無關鍵缺源；市場類主張有可重現的 deterministic 量測 |
| `medium` | 證據相關但只有單一強獨立 group、部分支持為 low reliability、樣本有限，或缺非關鍵來源 |
| `low` | 證據不足、存在 material conflict、關鍵資料 stale/不可得，或證據不直接回答該主張 |

deterministic 上限（硬性）：`insufficient_data=true` → 整體 `low`；conclusion 有 material conflict → 該 conclusion `low`
且整體不得 `high`；支持的 independence group <2 → 該 claim 不得 `high`；只有 `low` 證據 → 該 claim `low`；
唯一的當期證據是 stale cache → 當期狀態主張為 `low`。

### 5.5 四項固定 artifacts（檔名不可改）

| 檔名 | 何時寫 | 關鍵內容 |
|---|---|---|
| `run_config.json` | run 開始，finalize 時更新 | schema/prompt/policy 版本、sanitized request、不可變 cutoff、模式、deadline 與實際 stage 時長、模型 ID、optional key 存在布林值、fallback/cache/stale 狀態、terminal status、artifact checksum |
| `execution_log.jsonl` | 全程串流 | 每行一物件：`schema_version, timestamp, run_id, run_mode, stage, event_type, status, duration_ms, provider_or_model, parameters(sanitized), attempt, input_count, output_count, error_category, message` |
| `evidence.json` | Ledger 完成即寫 | `schema_version, run_id, analysis_as_of, run_mode, items[], conflict_indicators[], degradation_events[]`；items 依 `evidence_id` 排序 |
| `final_report.md` | 最後寫 | 繁中 11 段、deterministic 模板、禁語 lint 通過 |

`EvidenceItem` 至少含（命題硬性要求）：`source`、`fetched_at`、`content_reference`、`related_claim`，
外加 `reliability`、`independence_group`、`content_hash` 與 cache/stale metadata。

### 5.6 Deadline 預算（900 秒 run；來自 `design.md §6.1`）

| 里程碑 | 絕對位置 | 到點行為 |
|---|---:|---|
| Planner 完成 | 30 s | 改用 deterministic 預設 plan |
| 並行取證完成 | 270 s | 取消未完成的 adapter/抽取 task，保留已完成結果 |
| Evidence Processor 完成 | 360 s | 驗證並落盤所有可用 evidence |
| Arbiter + render 完成 | 510 s | 需要時走 deterministic fallback |
| Artifact 驗證目標 | 630 s | 進入保留區，不再加 optional 工作 |
| **分析硬停** | 720 s（第 12 分） | 取消所有剩餘外部 / LLM 呼叫 |
| **Artifact 硬停** | 780 s（第 13 分） | 目錄可寫則四份齊全；否則於 stdout 指名缺檔與 terminal state |
| 競賽 deadline | 900 s | 保留給 UI / 評審檢視 |

deadline 較短時，`DeadlineManager` 依比例縮放各 stage，並保留最後 20%（可能時至少 60 秒）給 deterministic finalize。
🚫 retry 與 schema repair 都不得延長 request deadline。

### 5.7 環境變數名稱（鎖定；`run_config.json` 只記存在與否）

**必要：** `AWS_REGION`、`BEDROCK_PRIMARY_MODEL_ID`、`ARTIFACT_ROOT`
**選用：** `BEDROCK_FALLBACK_MODEL_ID`、`CRYPTOPANIC_API_TOKEN`、`HTTP_CONNECT_TIMEOUT_SECONDS`、
`HTTP_READ_TIMEOUT_SECONDS`、`MAX_EVIDENCE_FOR_ARBITER`（硬上限 30）、`ALLOW_RECORDED_DEMO_FALLBACK`、`LOG_LEVEL`

---

## 6. 系統與基礎設施面

- **執行形態**：單一 Python process；Streamlit 與 application service 同 process，bounded `asyncio` 並行。
- **設定**：環境變數在 `config.py` 解析一次，傳入 typed `Settings`；`.env` 僅本機、不進 Git；
  `.env.example` 只放名稱佔位。
- **時間注入**：UTC 與 monotonic 都經由可注入的 clock，讓 deadline 測試不需真的 sleep。
- **artifact 儲存**：本機檔案系統 `artifacts/{run_id}/`；structured JSONL 同步輸出到 stdout。
- **可觀測性**：stdout + 每 run 的 JSONL；🚫 S3、CloudWatch 非 MVP。
- **部署**：單一 non-root Docker image → ECR（immutable tag）→ 單台 EC2 → `docker compose`；
  Bedrock 權限走 EC2 instance role，🚫 不把長效 AWS key 烘進 image / compose / artifact / 截圖。
- **健康檢查**：container healthcheck 打 Streamlit health endpoint；只開 demo 所需的那一個 port。
- **測試分層**：`tests/unit|contract|integration|acceptance|live|fixtures`；預設 `pytest` **絕不**碰外網，
  live test 需同時 `@pytest.mark.live` 與 `RUN_LIVE_TESTS=1`。
- **秘密管理**：提交前跑 secret scan；🚫 API key / AWS 憑證 / CryptoPanic token / prompt 全文
  不得進 UI、log、artifact、repo、錄影或截圖。
- **並行度**：單台 EC2 同時只接受一個 active run；🚫 MVP 不承諾 production auth、HA 或高並行。

---

## 7. 外部相依面（Portability Note）

以下是**必須放在 port / adapter 抽象之後**的外部世界接觸點。這份清單就是 ② 決定分層邊界、
③ 畫依賴方向、④ §3.2 決定「哪些只能人工測」的種子。

| 外部面 | 抽象邊界 | 為什麼要抽象 |
|---|---|---|
| HTTP 供應商（Binance、CryptoPanic、RSS、官方 blog、Alternative.me） | `MarketDataAdapter` / `ResearchSourceAdapter`（`SourceResult` 信封） | provider 欄位名與錯誤 payload **止步於 adapter**；核心只收 validated domain model |
| Amazon Bedrock | `LLMClient`（Converse + 結構化輸出） | 讓 Planner/Research/Arbiter 可用 fake LLM 完整測試，且逾時 clamp 與 repair 政策集中一處 |
| 主辦方 CSV 檔案 | `organizer_csv` adapter | 檔案 I/O 與 schema 驗證不外洩到 `data/` |
| 本機檔案系統（artifacts） | `ArtifactStore` protocol | 原子寫入與缺檔揭露集中一處；未來換儲存不動核心 |
| 系統時間（UTC + monotonic） | `Clock` | deadline 測試用 fixed clock / fake sleeper，不真的等 45 秒 |
| Streamlit runtime | `ProgressSink` + `ui/presenter.py` | 商業邏輯不進 UI callback；UI 不 import 具體 adapter 或 pipeline 內部 |
| 靜態工具允許清單 | `ToolRegistry` | 🚫 無 runtime plugin discovery、無遠端 registry、外部內容不得變更 allowlist |

**這條線以上的一切都與外部世界無關**：models、config、indicators、Evidence policy 與 processor、
claim 驗證、renderer、lint、trust scorecard、regime 判定——全部是可離線、可 headless 測試的純邏輯。
這正是 Bronze（完全離線跑完四項 artifacts）之所以可能的原因。

> **這些 seam 是 typed same-process 邊界，不是基礎設施服務。**
> 🚫 沒有 database、queue、broker、Job API、獨立 service/worker fleet、polling、SSE、WebSocket、
> DLQ、scheduler、authentication service、水平擴展。

---

## 8. 明確排除（`.kiro` 已核准，列此供下游知道「不要做」）

**Post-hackathon Future Work：** Platinum、CoinGecko live adapter、五幣完整驗證/校準矩陣、
額外 provider、PDF/HTML、額外視覺化、H3 實際 Bull/Bear/Judge 流程。

> ⚠️ **雙幣比較已於 2026-08-01 移出本清單。** 它現在是承諾能力（Requirement 17，見 §4.5），
> 排在 Silver 之後、Feature Freeze 之前。

**非 MVP 基礎設施：** database、queue、broker、Job API、獨立 service/worker fleet、polling、SSE、
WebSocket、DLQ、scheduler、authentication service、水平擴展、S3、CloudWatch、ECS。

**禁止引入的框架：** LangGraph、AWS Strands Agents、FastAPI、Celery、Redis、message broker、向量 DB、
其他 orchestration 框架（要改必須先改核准設計）。

**禁止的做法：** 近似/語意去重、動態 reliability 模型、自由 agent loop、自建 token/tool-call 計數器、
per-coin 分支邏輯（`if asset == "BTC"`）、跨幣直接比較 base-asset volume。

---

**下一步 →** [Tech-Stack-Plan.md](Tech-Stack-Plan.md)：消費本文的 §7 外部相依面來決定 port 層的厚度，
並消費 §1–§4 的能力面來挑一個「降低風險而非追求功能數」的第一個里程碑。
