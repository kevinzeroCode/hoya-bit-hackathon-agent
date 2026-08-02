# HOYA Market Agent — 架構與檔案地圖

> **③ of ④ — design-pipeline 第三份產出。**
> 上一份：[Tech-Stack-Plan.md](Tech-Stack-Plan.md)｜下一份：[Implementation-Plan.md](Implementation-Plan.md)

> **這份文件是衍生視圖，不是新的真相來源。**
> canonical tree 與 import 規則的規範性擁有者是 `.kiro/steering/structure.md`；元件職責的擁有者是
> `design.md §4`。本文把那兩者**變成檔案級**，並加上 `.kiro` 不記的一件事：**每個檔現在到底存不存在。**
> **若本文與 `.kiro/` 衝突，以 `.kiro/` 為準。**

> ⚠️ **這份文件會最快腐爛。** 它記的是**現況**。檔案落地、改責任、被合併時，
> 請當作那個檔的 definition-of-done 的一部分來更新它的 row。
> **狀態掃描時間：2026-08-02，commit `6f914dc`（`main`）。**

## 1. Context

本文回答兩個問題，對**每一個**檔案：**它做什麼**、**它跟誰互動**。
它是空間視圖——[Implementation-Plan.md](Implementation-Plan.md) 才是時間視圖（什麼時候建）。
新人 orientation 從這裡開始；④ 的每個 stage 的「元件」欄位都指回這裡的 row。

---

## 2. 依賴規則（先讀這一段）

依賴**只准向內**流。這不是風格偏好——它是
[Tech-Stack-Plan.md §6](Tech-Stack-Plan.md) 那條橫切鐵則的**物理強制手段**。

```text
                    streamlit_app.py
                          │ 只 import ApplicationService / presenter
                          ▼
              ui/presenter.py    application.py          ← 唯一的組裝根
                          │              │  建立並持有具體實作
                          │              ▼
                          │        orchestration/        ← pipeline 順序 / deadline / run state
                          │              │
                          │      ┌───────┼───────┬────────────┐
                          │      ▼       ▼       ▼            ▼
                          │   data/  evidence/ reasoning/ reporting/
                          │      │       │       │            │
                          └──────┴───────┴───────┴────────────┘
                                          │ 只透過 Protocol
                                          ▼
                                      ports.py
                                          ▲
                                          │ 實作
                                     adapters/          ← httpx / boto3 只在這裡
                                          
        所有模組 ─────────────────▶ models.py   （不 import 任何專案模組；圖的葉節點）
        所有模組 ─────────────────▶ clock.py    （UTC / monotonic 的唯一入口）
```

**層契約：**

- **`models.py`** 不 import 任何專案模組。任何 row 的「互動對象」若把它指向別的專案模組，就是 bug。
- **`clock.py`** 獨佔 UTC 與 monotonic 存取 → deadline 測試用 fixed clock，不真的 sleep。
- **`ports.py`** 只有 Protocol，🚫 無具體 I/O、無 `httpx`、無 `boto3`。
- **`config.py`** 可 import `models.py`；🚫 永不 import adapter 或 UI。
- **`application.py`** 是**唯一**知道具體 adapter 存在的檔（組裝根）。
- **`orchestration/`** 協調 stage 與失敗；🚫 不算指標、不指派 reliability、不 render Markdown。
- **`data/` `evidence/` `reporting/` 是 deterministic**，🚫 永不呼叫 Bedrock、🚫 永不 import `adapters/bedrock.py`。
- **只有 `adapters/*.py`** 可以 `import httpx` / `import boto3`。
- **`reasoning/`** 消費 `LLMClient` 與 evidence ID；🚫 **不寫任何 artifact**。
- **`ui/presenter.py`** 只造 display model；`streamlit_app.py` 🚫 不 import 具體 adapter 或 pipeline 內部。
- **`prompts/`、`HOYA_BIT_crypto_market_dataset/`、`tests/fixtures/` 是資料，不是程式碼** ——
  執行期載入；production code 🚫 不得 import fixtures。

---

## 3. 狀態圖例

| 記號 | 意義 |
|---|---|
| ✅ | **已在 `main` 上**，有測試且通過 |
| ✅⚠️ | **已在 `main` 上**，但為臨時/過渡性質，待後續替換或裁決 |
| ○ | **計畫中**，尚未寫；括號內為 ④ 的 stage 編號 |
| ⛔ | **明確不做 / 已裁決移除**——保留 row 當麵包屑，讓追舊參照的人不撲空 |

> **現況一句話：** `main` 上核心契約（`models.py` 40 類）、canonical runtime seams（`config/clock/ports`）、
> S2 vertical slice（`application/renderer/artifacts`）、data/evidence 全層、deadline-aware orchestration、
> 完整推理層、live composition root（`composition.py` + `adapters/live_sources.py`）與 Streamlit Bronze UI
> 均已落地；`_provisional_seams.py` 已退役。1235 passed / 0 failed（Python 3.12 離線實跑 2026-08-02），ruff clean。
> `src/calc/` 與 `src/skills/` 已納入 `main` 追蹤（獨立分析腳本與技能，非 agent pipeline 的一部分）。

---

## 4. 檔案地圖（分層）

### 4.1 根層契約與組裝（`src/hoya_agent/`）

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `__init__.py` | ✅ | 空的 package marker | — |
| `models.py` | ✅ | **全隊共用契約的唯一擁有者**（40 類，1603 行）：`AnalysisRequest`、`ResearchPlan`、`RunContext`、`MarketBar`、`MarketSnapshot`、`RawSourceRecord`、`EvidenceDraft`、`EvidenceItem`、`EvidenceLedger`、`ConflictIndicator`、`Claim`、`ClaimEvidenceLink`、`AnalysisResult`、`DegradationEvent`、`ExecutionEvent`、`RunConfigSnapshot`、`RunSummary`、`WorkerResult`、`TimeRange`、`MarketContext`＋R16 的 `TrustScorecard`/`MarketRegime`/`InvalidationCondition`；所有列舉（見 [Features.md §5.2](Features.md)）；全部 `extra="forbid"` | **不 import 任何專案模組**；被所有模組 import |
| `config.py` | ✅ | 環境變數解析一次 → typed `Settings`（155 行）；sanitized snapshot（optional key 只記布林值）；鎖定名稱 `BEDROCK_PRIMARY_MODEL_ID`/`BEDROCK_FALLBACK_MODEL_ID`/`CRYPTOPANIC_API_TOKEN` | `models.py`；被 `application.py`、adapter factory 讀 |
| `clock.py` | ✅ | 可注入的 UTC 與 `time.monotonic()` 入口（41 行）；`SystemClock` + `build_run_context` | `ports.Clock`；被 `orchestration/deadline.py`、`application.py` 用 |
| `ports.py` | ✅ | Protocol 邊界（137 行）：`Clock`、`LLMClient`、`SourceAdapter`、`MarketDataAdapter`、`ResearchSourceAdapter`、`ProgressSink`、`ArtifactStore`、`ToolRegistry`（`StaticToolRegistry`）、未來 persistence port | `models.py` 的型別；被 `adapters/*` 實作、被核心模組消費 |
| `application.py` | ✅ | **`ApplicationService` 入口**：驗證 request、凍結 `analysis_as_of`、造 `run_id`、建 run 目錄、寫首份 `run_config.json`、組裝 offline/research pipeline、叫 pipeline、回 `RunSummary`。**取消處理**：接到 `CancelledError` 後以現有狀態把四項 artifacts 標 `cancelled` 落盤，**再 re-raise**；該 finalize 路徑刻意全程無 await。**研究組裝（2026-08-01）**：`build_research_tool_registry()`（static registry，handler 解開 `SourceResult` → `list[RawSourceRecord]`，失敗拋 `SourceUnavailable`）、`build_research_pipeline()`、`ALLOWED_RESEARCH_HOSTS`（**呼叫前**就拒絕非 allowlist host）、`BASELINE_RESEARCH_OPERATIONS`／`OPTIONAL_CONTEXT_OPERATIONS`／`COUNTER_SIGNAL_OPERATIONS`（S4 跳過順序的來源清單就在這裡宣告）、`DeterministicPlanner`（無 LLM 時走預設計畫並揭露） | `config.Settings`、`clock`、`orchestration/pipeline.py`、`reporting/artifacts.py`、所有 `adapters/*`（唯一處）、`reasoning/{planner,research_agent,research_extractor}` |
| `composition.py` | ✅ | **Live pipeline composition root（2026-08-02 新增，取代已退役的 `_provisional_seams.py`）**：唯一可組裝 live concrete adapter 進 runnable pipeline 的另一處。`build_bedrock_llm()`、`build_live_pipeline()`（Binance daily klines ＋ Fear & Greed `extra_drafts` → `MappingArbiter`(包凍結 `Arbiter` + `reasoning/mapping.build_analysis_result`））。Planner/Research 在首波 live cut 關閉（fragile multi-stage layer，待 Arbiter 路徑證實後再加）。Arbiter 輸出 capped `max_tokens=3000` 以在 45s 單次呼叫限內完成 | `adapters/bedrock.py`、`adapters/live_sources.py`、`orchestration/pipeline.py`、`reasoning/{arbiter,mapping,schemas}`、`ports.Clock` |

### 4.2 `orchestration/` — 順序、時間、狀態

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `orchestration/__init__.py` | ✅ | package marker | — |
| `orchestration/pipeline.py` | ✅ | **`DeadlineAwarePipeline`**（stage 順序、`_fork_join()` 先取消再 await、`_apply_skip_order()` 依剩餘取證時間裁掉 `ResearchPlan` 的 optional 步驟、Arbiter 投影）＋ **`OrganizerCsvPipeline`**（CSV-only offline 路徑）；`to_contract_ledger()` 橋接 `evidence/types.py` 至 `models.py`。Evidence stage 先跑 `complete_extracted_drafts()` 再 merge 研究 draft。**`finalize_analysis()`（2026-08-01）**：Arbiter 之後的 deterministic pass——建 `ConflictIndicator` → 掛進 Ledger＋`material_conflict_detected` event → 套 `apply_confidence_caps()`（矛盾結論降為 `low`、整體不得 `high`）→ 最後才建 Trust Scorecard（其 `consistency` 要讀剛掛上的 indicator）；兩條 pipeline 都套用。optional／反方訊號的 operation 清單由組裝端宣告（`application.build_research_pipeline()`），預設空集合 | `deadline.py`、`run_state.py`、`data/market_worker.py`、`evidence/{processor,ledger,grounding,trust}.py`、`reasoning/{arbiter,research_extractor}.py`、`reporting/*`、`models.*` |
| `orchestration/deadline.py` | ✅ | `DeadlineManager` / `DeadlineManager.for_run()`：`Stage` 預算里程碑（planner/gather/evidence/reason/artifact，[Features.md §5.6](Features.md)）以「參考 720 秒窗口的比例」保存並依 request deadline 縮放；`deadline_for()`／`remaining()`／`budget_for()`／`budget_seconds()`；finalize 保留 `max(20%, min(60s, 半個 run))`；**固定跳過順序**（`OptionalWork`、`SKIP_ORDER`、`plan_optional_work()`、`skip_note()`）——成本由呼叫端給，不編造估值；🚫 retry/repair 不得延長 | `clock.Clock`、`models.RunContext`；被 `pipeline.py` 消費 |
| `orchestration/run_state.py` | ✅ | `RunStateMachine`：in-memory stage state（`pending\|running\|completed\|degraded\|failed\|cancelled`）、stage_start/stage_end 事件串流（含 `duration_ms`）、`stage_durations_ms()`；`stage_state_for(WorkerStatus)` 映射（`partial→degraded`）；`derive_terminal_state(states, run_cancelled=…)`——單一分支取消=degraded、run 取消=cancelled。**execution-log 的 stage 名稱由本檔持有，`deadline.Stage` 是另一組預算里程碑** | `models.ExecutionEvent/StageState/TerminalState/WorkerStatus`；被 `pipeline.py` 寫、經 `application.py` 的 `ProgressSink` 橋到 `ui/presenter.py` |

### 4.3 `data/` — deterministic 市場層（🚫 永不呼叫 LLM）

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `data/__init__.py` | ✅ | package marker | — |
| `data/types.py` | ✅ | `MarketBar` dataclass：日 K 結構型別 | 被 `market_series.py`、`indicators.py`、`market_worker.py` 用 |
| `data/market_series.py` | ✅ | 載入/驗證 UTC 日 K；**CSV↔Binance 來源切換點**（2026-06-01）的唯一擁有者；`bars_asof`、`merge_with_cutover`；剔除未完成日 K，另表示為 intraday snapshot；🚫 不 forward-fill | `adapters/organizer_csv.py`、`adapters/binance.py`（經 `ports.MarketDataAdapter`）；被 `market_worker.py` 用 |
| `data/indicators.py` | ✅ | **公式的唯一擁有者**：區間報酬、已實現波動、最大回撤、量能變化、rolling z-score、range position；純函數、golden fixture 覆蓋 | `pandas`；被 `market_worker.py`、`regime.py` 呼叫 |
| `data/market_worker.py` | ✅ | deterministic 分支組裝：跑 adapter → 算指標 → 每個指標轉成 high-reliability `EvidenceDraft`（帶參數與範圍）；回 `WorkerResult`；**🚫 沒有任何到 `LLMClient` 的 import 或呼叫路徑** | `market_series.py`、`indicators.py`、`regime.py`、`models.EvidenceDraft`；被 `pipeline.py` 呼叫 |
| `data/regime.py` | ✅ | **R16 Market Regime**：純 OHLCV 判 `trending_up\|trending_down\|range_bound\|high_volatility\|mixed`；門檻一律對該資產**自身** rolling 歷史；保留觸發指標值與門檻；缺 bar → `unavailable` | `indicators.py`；由 `market_worker.py` 發成 `EvidenceDraft` |
| `data/price_analysis.py` | ✅ | 跨幣比較分析：anomaly detection、attribution、comparison 純函數 | `indicators.py`、`types.py`；被 `market_worker.py` 用 |
| `data/text_clean.py` | ✅ | 來源文字正規化（空白、Unicode、長度截斷） | 被 `evidence/processor.py`、`reasoning/research_agent.py` 用 |
| `data/analogs.py` | ⛔ | 歷史類比基準率 | **不在 canonical tree**，且 `structure.md` 明文「不為單一 helper 新增檔案」。**裁決：併進 `data/indicators.py`**，除非另行修改 steering |

### 4.4 `adapters/` — 外部 I/O（唯一可 `import httpx` / `import boto3` 之處；保持扁平）

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `adapters/__init__.py` | ✅ | package marker | — |
| `adapters/bedrock.py` | ✅ | **LLM 邊界的唯一擁有者**（371 行）：`BedrockLLMClient.converse_structured()`；強制 tool call 取結構化輸出（`STRUCTURED_TOOL_NAME`）；`effective_timeout()` 對 `MAX_CALL_TIMEOUT_SECONDS=45.0` 與剩餘 stage 時間取小；`is_retryable_error()` 白名單；`build_repair_messages()` 做**一次** schema repair；備援模型；`drain_events()` 供 log | `boto3`、`config.Settings`；實作 `ports.LLMClient`；被 `reasoning/{planner,research_agent,arbiter}.py` 消費 |
| `adapters/organizer_csv.py` | ✅ | 讀 `HOYA_BIT_crypto_market_dataset/data/{ASSET}_daily_ohlcv.csv`；驗 `date,open,high,low,close,volume`、UTC 日界、正價、high/low 一致；來源名 `public_market_data`、group `organizer-public-market-data`；🚫 不推定上游交易所 | `models.MarketBar`；實作 `ports.MarketDataAdapter`；被 `data/market_series.py` 用 |
| `adapters/binance.py` | ✅ | Spot public REST `GET /api/v3/klines`（UTC 日 K）與 `GET /api/v3/ticker/24hr`（snapshot/quote volume）；固定 `{ASSET}USDT` 對照；只取 ≤ `analysis_as_of`；group `binance.com` | `httpx`；實作 `ports.MarketDataAdapter` |
| `adapters/cryptopanic.py` | ✅ | 依 currency 與 lookback 取新聞；保留原文 URL/發布者/標題/published time/`fetched_at`；`independence_group` 取**原始發布者網域**（不是 `cryptopanic.com`）；未取原頁則維持 `low`；缺 token → 停用 adapter 而非讓 run 失敗 | `httpx`、`config`；實作 `ports.ResearchSourceAdapter` |
| `adapters/rss.py` | ✅ | 新聞 RSS 解析 → `RawSourceRecord` | `httpx`；實作 `ports.ResearchSourceAdapter` |
| `adapters/alternative_me.py` | ✅ | `/fng/` 無金鑰；產出 `asset=null` 的**全市場** context；`source_type=social`、`reliability=low`、group `alternative.me`；stale 標記但不再降級 | `httpx` |
| `adapters/port_adapters.py` | ✅ | Port-conforming async wrappers：`CsvMarketAdapter`、`BinanceMarketAdapter`、`RssResearchAdapter`、`CryptoPanicResearchAdapter`、`FearGreedResearchAdapter`、`OfficialAnnouncementsResearchAdapter`（2026-08-01 補齊後三個——在那之前另外三個研究來源在真實 run 裡接不上）。`fetch(*, operation, context=None, **params)` 同時吃 `RunContext` 與 registry 傳的散裝 `assets`/`analysis_as_of`/`lookback_days`；`SourceStatus` 由 `_errors.py` 的 category token 正規化；`SourceUnavailable` 只由 registry handler 拋出，讓失敗變成揭露的來源缺口（空結果不拋） | `organizer_csv.py`、`binance.py`、`rss.py`、`cryptopanic.py`、`alternative_me.py`、`official.py`、`_errors.py`；實作 `ports.*Adapter` |
| `adapters/_errors.py` | ✅ | 正規化錯誤詞彙（2026-08-01 新增）：`classify_error()` → `timeout\|http_error\|malformed\|rejected`、`category_note()` 在 degradation note 後附 `[category=…]`、`category_of()` 在 port 邊界讀回。存在理由：adapter 不得跨 port 拋例外，但 note 本身無法讓 `SourceResult.status` 分辨 timeout 與 500 | 只依 `httpx`／標準庫；被四個研究 adapter 與 `port_adapters.py` 使用 |
| `adapters/_assets.py` | ✅ | 資產符號 ↔ provider 代碼對照（供 rss/cryptopanic 用） | 只被研究類 adapter 使用 |
| `adapters/official.py` | ✅ | 依資產查 checked-in 官方 blog/RSS allowlist（`OFFICIAL_FEEDS`，五幣皆有）；**best-effort**，無設定 feed → 揭露缺口而非錯誤；原始發布者 → `high` | `httpx`、`_assets.py`、`_errors.py`、`policies.py`；經 `OfficialAnnouncementsResearchAdapter` 進 pipeline |
| `adapters/live_sources.py` | ✅ | **Live source composition（2026-08-02 新增）**：把 async Binance／Fear & Greed fetcher 橋成 deterministic pipeline 注入的**同步** callable（`binance_bar_loader` → `load_bars(asset)`、`fear_greed_drafts` → `() -> (drafts, degradation)`）。用 worker thread 跑獨立 event loop（`asyncio.run` 不能 nest）。兩個來源皆免 key；Bedrock 是另一層。所有 `httpx` 止步於此，`orchestration/` 收到的只是 callable | `httpx`、`adapters/{binance,alternative_me}.py`、`data/types.py`、`evidence/drafts.py`；被 `composition.build_live_pipeline()` 與 `ui/streamlit_app.py` 消費 |
| `adapters/okx.py` | ⛔ | P2 寫的第二個交易所 adapter | **不在 canonical tree，且與「單一 baseline live market source」的核准決定衝突。已裁決不搬入 MVP。** |
| `adapters/coingecko.py` | ⛔ | CoinGecko live adapter | **steering 已定為 post-hackathon Future Work，MVP 不實作。🚫 不要從 P2 分支拉這個檔。** |


### 4.5 `evidence/` — deterministic 證據層（🚫 永不呼叫 LLM）

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `evidence/__init__.py` | ✅ | package marker | — |
| `evidence/drafts.py` | ✅ | **唯一的 draft 型別（2026-08-01 第五輪新增，取代 `evidence/types.py`）**：`PendingEvidence` = canonical `models.EvidenceDraft` ＋ provenance（`source_class` 供靜態 reliability、`original_publisher`／`provider_id` 供 independence group、`MetricValue` 帶 §16.4 需要的可驗證數值）＋ `pending()` 便利建構子。**draft 上刻意沒有 `reliability`／`independence_group`**——那是 processor 的職責，舊 provisional dataclass 把它放在 draft 上等於讓取資料的人自我宣告可信度 | `models.EvidenceDraft`、`policies.SourceClass`；被所有 producer 與 `processor.py` 使用 |
| `evidence/policies.py` | ✅ | **鐵則 5 的靜態表**（123 行）：`SourceClass` 列舉、`reliability_for()`、`news_reliability(original_page_fetched=)`、`registered_domain()`、`independence_group()`、`ConfidenceSignals` + `max_confidence()`；`ORGANIZER_GROUP` 常數 | 只依標準庫；被 `processor.py`、`trust.py`、`reasoning/arbiter.py` 消費 |
| `evidence/processor.py` | ✅ | **唯一的指派點**（`design.md §9`）：reliability ← `source_class` 靜態表、independence group ← §5 規則（原始發布者 → 註冊網域 → provider id）、`content_hash` ← 正規化事實（**精確**去重）、`ev_NNN` ← 排序後配發；直接輸出 canonical `models.EvidenceLedger` ＋ `metric_index`。支援 `existing=`／`existing_metrics=` 以便研究分支後到時合併並**以 content_hash 重新對應 metric**（否則量化 invalidation 門檻會指向錯的證據） | `drafts.py`、`policies.py`、`models.*`；被 `pipeline.to_contract_ledger()` 呼叫 |
| `evidence/evidence_json.py` | ⛔ **已刪除（2026-08-01 第五輪）** | P2 原型的第二個 evidence writer，schema（`evidence-ledger/p2-prototype-v1`）與 `evidence-contracts.md` §12 衝突，且全 `src/` 無人 import | dual-writer 問題結案：canonical writer 只有 `reporting/artifacts.py` |
| `evidence/ledger.py` | ✅ | 帳本服務（2026-08-01 接線；在那之前是**死碼**——全 `src/` 無人 import）：`build_conflict_indicators()`（evidence-contracts §9，claim 層、依 `claim_id` 排序、id list 排序，與 link 順序無關；`CONFLICT_RULE_VERSION` 隨 indicator 落盤）、`detect_material_conflict()`、`confidence_signals_for_claim()`（含 grounding gating）、`filter_by_*`／`distinct_*`／`has_first_hand_source`／`source_coverage_gaps`、`select_for_arbiter{,_dual}` | `evidence/types.py`、`policies.py`、`grounding.py`、`models.ConflictIndicator`；由 `orchestration/pipeline.py::finalize_analysis()` 呼叫 |
| `evidence/trust.py` | ○ (S9) | **R16 Trust Scorecard**：對每個 `conclusion` 由 ledger + links 純函數推導五面向（independence / diversity / reliability_mix / consistency / freshness）＋原始計數；ordinal `strong\|moderate\|weak\|unavailable`；必須與 confidence rubric 一致（<2 group 不得 `strong`；material conflict → consistency `weak`）；🚫 無網路、無 LLM、無檔案系統 | `models.EvidenceLedger`、`ClaimEvidenceLink`、`Claim`、`policies.py`；結果掛在 `AnalysisResult` 上供 renderer 用 |

### 4.6 `reasoning/` — bounded LLM 層（🚫 不寫任何 artifact）

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `reasoning/__init__.py` | ✅ | package marker | — |
| `reasoning/prompt_library.py` | ✅ | prompt 載入器（112 行）：解析 frontmatter → `Prompt`（含 `version_label`）；`load_prompt(stage)`、`cached_prompt(stage)`、`prompt_versions()`；預設目錄 `prompts/` | `prompts/*-v1.md`（**資料**）；被三個 reasoner 用；版本進 `run_config.json` |
| `reasoning/planner.py` | ✅ | Planner（180 行）：一次 bounded 呼叫產 `ResearchPlan`；`plan_violations()` 驗 bounded 步數（`MIN_PLANNED_STEPS`/`MAX_PLANNED_STEPS=8`）、時間範圍、允許操作；`default_plan_payload()` 供失敗時的 deterministic 預設（`DEFAULT_LOOKBACK_DAYS=14`）；🚫 不產市場結論 | `ports.LLMClient`（實體是 `adapters/bedrock.py`）、`prompt_library`；被 `pipeline.py` 呼叫 |
| `reasoning/research_agent.py` | ✅ | Research Agent（204 行）：對 `ToolRegistry` 給的有限操作做 bounded 執行；一次 bounded 抽取 → `EvidenceDraft[]`；`looks_like_injection()` 以 `INJECTION_MARKERS` 標記可疑內容並保留為**引用資料**；回 `ResearchOutcome`（`completed\|partial\|failed`）；🚫 不得自由迴圈、不得造 URL | `ports.LLMClient`、`ports.ResearchSourceAdapter`、`prompt_library`、`evidence/types` |
| `reasoning/arbiter.py` | ✅ | Arbiter（478 行）——**大部分是 deterministic 驗證**：`select_evidence()`（上限 `MAX_EVIDENCE_FOR_ARBITER=30`，先保 high reliability，再保 conflict pair，再以最大化 distinct independence group 填滿）、`build_evidence_payload()`（只送 ID + normalized fact）、`detect_cycle()`、`structural_violations()`、`apply_confidence_caps()`；一次生成 + 一次 repair + `_fallback()` | `ports.LLMClient`、`evidence/policies.py`、`evidence/types.py`、`prompt_library` |
| `reasoning/conflict_extension.py` | ✅ | **H3 停用樁**（64 行）：`DisabledConflictExtension.evaluate()` 回 `status="disabled"`、`route="arbiter"`、indicators 原樣；`UNIMPLEMENTED_LABEL` 供 UI 顯示；🚫 無網路、無 LLM 呼叫 | `models.EvidenceLedger`/`ConflictIndicator`；被 `pipeline.py` 呼叫；label 被 `ui/presenter.py` 顯示 |
| `reasoning/llm_client.py` | ⛔ | P2 的第二套 LLM Protocol（只有 `complete()`） | **已裁決刪除**——LLM 邊界統一用 `adapters/bedrock.py`。⚠️ 其 docstring 教人用不存在的 `AnthropicBedrockMantle`（正確名是 `AnthropicBedrock`），照抄會爆 |
| `reasoning/gpt_client.py`、`run_gpt_extract.py` | ⛔ | P2 的 OpenAI 路徑 | **已裁決刪除**——規格是 Bedrock-only |
| `reasoning/arbiter_output.py` | ✅ | **LLM 邊界 schema 與投影（2026-08-01 新增檔，未改凍結檔）。** `ArbiterOutput`／`ArbiterClaim`／`ArbiterLink`／`ArbiterMarketContext`／`ArbiterInvalidationCondition` ＝ `AnalysisResult` 減去凍結請求脈絡，時間範圍可為 null（凍結 `_fallback()` 就是這個形狀）；**全部用 `Literal` 字串而非列舉**——凍結的 `apply_confidence_caps()` 以 `str()` 比對，列舉會讓每次信心下修都弄壞 payload 並靜默退回 fallback。`ledger_view()`／`EvidenceView` 提供字串化 ledger 視圖（同 `ReasoningRequest` 慣例）；否則 `_reliability_rank()` 讀到 `"Reliability.high"`，`select_evidence()` 失去 high 優先序、`_fallback()` 挑不到任何 fact。`project_to_analysis_result()` 蓋回凍結脈絡、映射列舉、以證據窗口補時間範圍並收斂超出 cutoff 的範圍，並回傳需揭露的 notes | `models.py`（只讀）、`reasoning/arbiter.py`（只被呼叫）；由 `orchestration/pipeline.py::_run_arbiter()` 與 `application.build_research_pipeline()` 使用 |
| `reasoning/research_extractor.py` | ✅ | **2026-08-01 已搬進 `src/`（新增檔，未修改任何凍結檔）。** 提供 `ResearchAgent` 一直以注入方式索取、但 `src/` 從來沒有人提供的兩半：① `ResearchExtraction`／`ExtractedFact`（structured-output schema，`extra="forbid"`；一篇文章可回多筆 fact＋`relevant` 判定，這就是多事實抽取與 relevance filtering）；② `complete_extracted_drafts()` deterministic 補完——reliability 走靜態表（feed item 未取原頁 → `low`）、`independence_group` 走 `policies`、時間戳取自 record、引用不存在 record 的 fact 直接丟棄並揭露、每篇上限 3 筆、`content_reference` 為 ≤400 字的有界引述以供 grounding 比對。已完整的 draft（market worker／adapter 產出）原樣通過 | `evidence/policies.py`、`evidence/drafts.py`、`data/text_clean.py`、`models.Asset`；由 `orchestration/pipeline.py` 在 Evidence stage 呼叫；schema 由組裝端注入 `ResearchAgent` |
| `reasoning/schemas.py` | ✅ | **Canonical LLM I/O schemas（2026-08-02 新增檔，未改凍結檔）。** Planner／Research／Arbiter 透過 `converse_structured(schema=…)` 要求 Claude 回傳的 **lax provider-output** 形狀：`ArbiterGeneration`／`GenClaim`／`GenLink`／`GenInvalidation`、`PlanGeneration`／`GenStep`、`DraftBatch`／`GenDraft`／`GenSkipped`。刻意寬鬆（無 `run_id`、無嚴格 claim-graph 不變量）——模型自由產出後由 `mapping.py` 投影到嚴格凍結 `models.AnalysisResult`。全 `extra="forbid"` | `pydantic`、`models.*`（只參考形狀）；被 `reasoning/mapping.py` 與組裝端（`composition.py`／`application.build_research_pipeline()`）注入凍結 reasoner |
| `reasoning/mapping.py` | ✅ | **Lax → strict 投影（2026-08-02 新增檔，未改凍結檔）。** `build_analysis_result(generation, request, ledger)`：把 `ArbiterGeneration` 蓋上凍結請求脈絡（`run_id`／`question`／`assets`／`analysis_as_of`）、`str` → canonical 列舉、claim 缺 `assets` 預設為 run 的 assets、`time_range` 夾到 cutoff（不得超過 `analysis_as_of`）、缺失起訖以證據窗口／14 日 lookback 補齊。任何 `ValidationError`／`ValueError`／`TypeError` → 回 `None`（caller 走 deterministic insufficient-data fallback，永不崩 run）。`to_analysis_result()` 為吞錯版本 | `models.*`、`reasoning/schemas.py`；被 `composition.MappingArbiter` 與 `reasoning/arbiter_output.project_to_analysis_result()` 並存使用 |
| Bull / Bear / Judge | ⛔ | H3 的辯論角色 | **從未建立，MVP 也不得建立。** H3 只存在 `conflict_extension.py` 一個停用實作 |

### 4.7 `reporting/` — deterministic 交付層（🚫 永不呼叫 LLM）

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `reporting/__init__.py` | ✅ | package marker | — |
| `reporting/artifacts.py` | ✅ | **四個固定檔名的唯一擁有者**（S2）：`final_report.md`/`evidence.json`/`execution_log.jsonl`/`run_config.json`；「同目錄暫存檔 → flush → `os.replace`」原子寫入；run 開始開 append-only log；缺檔時在 stdout 與所有仍可寫的 artifact **指名確切檔名**；finalize 時補 terminal state 與 checksum | 實作 `ports.ArtifactStore`；被 `application.py`、`pipeline.py`、`evidence/processor.py` 的下游呼叫 |
| `reporting/renderer.py` | ✅ | 繁中 11 段 deterministic 模板（402 行，S2）；**只讀 `AnalysisResult` + `EvidenceLedger`**，🚫 不加帳本外的新事實；insufficient-data 的 deterministic fallback 報告；R16 三個呈現區塊（regime headline、per-conclusion scorecard、量化 invalidation）；最後呼叫 `lint.py` | `models.AnalysisResult`、`EvidenceLedger`、`lint.py` |
| `reporting/lint.py` | ○ (S3) | **禁語 lint（最後防線）**：純字串比對攔「建議買入／建議賣出／加倉／減倉／做多／做空／資產配置」等指示性投資用語；🚫 不依賴 `models.py`（所以可以先寫） | 被 `renderer.py` 在最後一步呼叫；lint 事件進 execution log |

| `reporting/html_renderer.py` | ✅ | P4 完整 HTML 報告：沿用 `7-html-report-template` editorial tokens；純函式、全動態值 escape、自包含離線，支援 dark／print／mobile，產生主要瀏覽器交付物 `final_report.html` | `models.AnalysisResult`、`EvidenceLedger`、`advice_lint.py`；由 `application.py` 呼叫 |

### 4.8 `ui/` 與入口

| 檔案 | 狀態 | 職責 | 互動對象 |
|---|---|---|---|
| `ui/__init__.py` | ✅ | package marker | — |
| `ui/presenter.py` | ✅ | domain → view model：stage 進度列、成功/失敗來源、degradation notes、terminal state、run-mode 標籤、**H3-未實作**狀態、recorded-fallback 警示、**trust funnel（G3）**（`trust_funnel()` 把 `evidence.json` 蒸餾成 source_type／independence_group 漏斗與 reliability mix，純函數、framework-free）。**只造 display model，🚫 無商業邏輯、🚫 不 import Streamlit** | `models.RunSummary`、`orchestration/run_state.py` 的 progress event、`reasoning/conflict_extension.UNIMPLEMENTED_LABEL` |
| `streamlit_app.py`（位於 `ui/streamlit_app.py`） | ✅ | 唯一 UI 入口：題目輸入、一至二幣選擇、run mode 選擇、run 中停用按鈕（確保一次提交＝一次呼叫）、`st.status` 串流真實 `ExecutionEvent` 進度、trust funnel、Report/Evidence/Log 三分頁、四項下載鈕、編輯主題。**self-bootstrap**：`sys.path.insert(0, src)` 讓 judge 無 editable install／PYTHONPATH 也能 `streamlit run`。只 import `ApplicationService`、`presenter` 與 `live_sources`/`OrganizerCsvPipeline`（組裝 offline pipeline），🚫 不 import 具體 LLM/Bedrock adapter 或 pipeline 內部 | `application.ApplicationService`、`ui/presenter.py`、`adapters/live_sources.py`、`orchestration/pipeline.OrganizerCsvPipeline` |


### 4.9 資料、prompt 與建置檔（**資料，不是程式碼**）

| 路徑 | 狀態 | 角色 |
|---|---|---|
| `pyproject.toml` | ✅ | Python 3.12、相依、pytest marker、src layout、editable install |
| `prompts/planner-v1.md` | ✅ | Planner prompt 本體；版本與 checksum 進 `run_config.json` |
| `prompts/research-extraction-v1.md` | ✅ | 研究抽取 prompt 本體 |
| `prompts/arbiter-v1.md` | ✅（S9 待改） | Arbiter prompt 本體；S9 要加「invalidation 門檻只能引用 deterministic Evidence」 |
| `HOYA_BIT_crypto_market_dataset/data/*.csv` | ✅ | 主辦方五幣 Daily OHLCV 基準（0 缺漏日、0 NaN、0 筆 OHLC 違反） |
| `tests/fixtures/` | ✅ | 不可變的 CSV/API/LLM 輸入與 vertical-slice pair。**production code 🚫 不得 import** |
| `Dockerfile`、`.dockerignore`、`compose.yaml` | ✅ | 單一 non-root image（`python:3.12-slim`，打包官方資料集、Streamlit healthcheck）；只開 Streamlit port；掛持久化 artifact volume。EC2 部署見 `docs/deploy-ec2.md` |
| `.env.example` | ✅ | 只有名稱佔位，🚫 無值 |
| `artifacts/{run_id}/` | ○（執行期產生） | 每 run 的四個檔；**已 gitignore** |

### 4.10 測試樹

| 路徑 | 狀態 | 內容 |
|---|---|---|
| `tests/conftest.py` | ✅ | 共用 fixture：path bootstrap、shared markers |
| `tests/fakes.py` | ✅ | `FixedClock`、`FakeLLM`、`FakeSourceAdapter`、in-memory artifact/persistence、static fake `ToolRegistry`、in-memory progress sink |
| `tests/unit/test_models.py` | ✅ | 40 contract models 驗證：field validation、extra=forbid、enum constraints |
| `tests/unit/test_config.py` | ✅ | Settings 解析、sanitized snapshot、missing keys |
| `tests/unit/test_runtime_seams.py` | ✅ | clock、ports、provisional seams 型別相容性 |
| `tests/unit/reporting/` | ✅ | `test_renderer.py`、`test_artifacts.py`：11 段報告驗證、atomic write、fallback report |
| `tests/unit/orchestration/test_evidence_mapping.py` | ✅ | `to_contract_ledger()` 橋接驗證 |
| `tests/unit/data_evidence/` | ✅ | 所有 adapter 與 indicator 的 unit tests（golden fixtures、boundary/NaN） |
| `tests/unit/reasoning/_stubs.py` | ✅ ⚠️ | reasoning 測試用的**臨時**型別替身。**`models.py` 已落地，待後續 swap 時刪除** |
| `tests/unit/reasoning/*` (5 檔) | ✅ | planner / research_agent / arbiter / conflict_extension / prompt_library |
| `tests/unit/evidence/test_policies.py` | ✅ | 靜態 reliability 表與 independence group |
| `tests/contract/test_bedrock_client.py` | ✅ | Bedrock Converse 形狀、逾時、repair、備援（**對 stub，不是真模型**） |
| `tests/integration/test_vertical_slice.py` | ✅ | S2 四項 artifact 端到端、deterministic fallback |
| `tests/integration/test_s1_seam_bridge.py` | ✅ | provisional seam ↔ real seam 欄位名一致性（swap 完成後刪除） |
| `tests/integration/test_organizer_csv_pipeline.py` | ✅ | `OrganizerCsvPipeline` 離線 BTC run 產出四項 artifacts |
| `tests/unit/` 其餘 | ○ | deadline、trust、regime 的額外邊界 |
| `tests/contract/` 其餘 | ○ | 各 adapter 的 `httpx.MockTransport` 契約 |
| `tests/acceptance/test_gold_assets.py` | ✅ | S10：兩個**不同**資產各一次**獨立**單幣 run、五幣請求 allowlist、baseline 來源缺失的誠實降級（🚫 不得合併成雙幣 run） |
| `tests/acceptance/test_artifact_contract.py` | ✅ | 四個固定檔名、全部可解析、四份共用一個 `run_id`、11 段、限制有揭露、deterministic rendering（`fetched_at` 正規化後比對） |
| `tests/acceptance/test_deadline_budget.py` | ✅ | fake-clock：第 12 分鐘停止分析、finalize 早於保留區、optional work 依固定順序放棄 |
| `tests/live/` | ○ | 真實 provider 與 Bedrock；需 `@pytest.mark.live` **且** `RUN_LIVE_TESTS=1` |

### 4.10b 交付與驗證腳本（`scripts/`、`.github/`）

不在 image 內（`.dockerignore` 排除 `scripts/`），是開發與交付時在 repo 根執行的工具。

| 路徑 | 狀態 | 說明 |
|---|---|---|
| `scripts/smoke_test.py` | ✅ | S11 部署 smoke：HTTP health/root ＋ 四項 artifact 解析與 `run_id` 一致。純標準庫。**必須用 `docker cp` ＋ `docker exec` 在容器內跑**——UI 把 artifacts 寫進容器內的 `tempfile.mkdtemp()`，host 端驗到的是 host 的碼 |
| `scripts/run_acceptance.py` | ✅ | S10 driver：兩資產各一次獨立單幣 run，離線（organizer CSV）或 `--live`。輸出即 `docs/rehearsals/run-log.md` 要的欄位 |
| `scripts/diagnose_bedrock.py` | ✅ | Bedrock 可用性診斷（3 次呼叫）。目前對 account `035741228337` 回 `ResourceNotFoundException`（帳號未送 Anthropic use case 表單） |
| `scripts/live_silver_run.py` | ✅ | S8 Silver 證據產生器（`--mode live` / `--mode fallback`） |
| `scripts/verify_s8_s9_s9b.py` | ✅ | S8/S9/S9B 離線 smoke（不需 pytest 或網路） |
| `scripts/analyze.py` | ✅ | `src/calc` / `src/skills` 平行工具的 CLI，非 agent pipeline |
| `.github/workflows/ci.yml` | ✅ | verify（Ruff ＋ 非 live 測試）／container（compose config ＋ build ＋ 容器內 smoke ＋ 非 root ＋ 無 `.env`）／secret-scan（gitleaks 掃 `git archive HEAD`）。🚫 不需要 AWS 憑證 |

### 4.11 不在 canonical agent tree、目前是平行工具/歷史路徑

| 路徑 | 狀態 | 說明 |
|---|---|---|
| `src/calc/` | ✅（平行工具） | **2026-08-02 起已納入 `main` 追蹤**：`indicators`、`percentile`、`cross_asset`、`analogs`、`data_quality`。是獨立的價格分析腳本工具集（對應 `src/PRICE-IMPLEMENTATION-NOTES.md` 的 A1–A10 分析產出），**非 agent pipeline 的一部分**——`hoya_agent/` 不 import 它。🚫 不要照它們寫進 agent 的 import |
| `src/skills/` | ✅（平行工具） | **2026-08-02 起已納入 `main` 追蹤**：`base`、`dataset`、`a1_regime`…`a9_verification`、`report`、`lint`、`html_report`。獨立的分析技能模組（CLI／報告產生器），**非 agent pipeline 的一部分**——`hoya_agent/` 不 import 它。有自己的 `tests/unit/skills/` |
| `p2-etl-mvp/` | ⛔ | P2 分支的平行目錄。**永遠不進 `main` 的 agent 樹**——B/C 各自 `git checkout origin/feat/p2-report-integration -- <自己那半>` 再 `git mv` 進 `src/hoya_agent/` |
| `docs/superpowers/*` | — | 設計已註明的**歷史紀錄**（已被 `.kiro/specs` 取代）。保留原文，🚫 不視為現行契約 |
| `docs/ai/SPEC_DIFF_PLAN.md`、`STAGED_DELIVERY_PROPOSAL.md` | — | `design.md` 曾誤引為不存在的檔（已修正指向 `tasks.md`）。檔案實際存在，但**不是現行契約** |


---

## 5. 主要流程（ASCII call trace）

### A. 啟動與組裝（`application.py` 是唯一整合者）

```text
streamlit_app.py  ─submit(question, assets, run_mode)─▶ ApplicationService.run(request, progress)
      │
      ▼
application.py
  ├─ Settings ← config.parse_env()                  # 只在這裡讀環境變數
  ├─ clock = SystemClock()                          # 或測試注入的 FixedClock
  ├─ validate(AnalysisRequest)  →  freeze analysis_as_of, mint run_id
  ├─ artifacts = LocalArtifactStore(ARTIFACT_ROOT/run_id)
  │     └─▶ write run_config.json          ★ 任何網路呼叫之前
  │     └─▶ open execution_log.jsonl (append)
  ├─ llm       = BedrockLLMClient(settings)         # 唯一建立具體 adapter 的地方
  ├─ market    = MarketWorker(OrganizerCsvAdapter, BinanceAdapter)
  ├─ research  = ResearchAgent(llm, [CryptoPanic, Rss, Official, AlternativeMe])
  ├─ deadline  = DeadlineManager(clock, request.deadline_seconds)
  └─▶ DeadlineAwarePipeline(...).execute()  ─▶ RunSummary
```

> **方向紀律：** 只有 `application.py` 認識 `BedrockLLMClient`、`BinanceAdapter` 這些**具體型別**。
> pipeline 與其下游全部只看到 `ports.py` 的 Protocol，所以整條線可以用 `tests/fakes.py` 離線跑完。

### B. 一次 official run 的主路徑（artifact-first）

```text
pipeline.execute()
 │
 ├─▶ Planner.run(request)                                   [LLM ①, deadline 30s]
 │      └─ 失敗 → default_plan_payload()                     # deterministic 兜底
 │
 ├─▶ asyncio.gather(return_exceptions=True)                  [deadline 270s]
 │      ├─ MarketWorker.execute(plan, ctx)                   ← 🚫 無 LLM
 │      │    ├─ organizer_csv.fetch_daily_bars()
 │      │    ├─ binance.fetch_daily_bars() / fetch_snapshot()
 │      │    ├─ market_series.merge()  → 記錄 2026-06-01 切換點
 │      │    ├─ indicators.*()  +  regime.classify()
 │      │    └─▶ WorkerResult(EvidenceDraft[], degradations)
 │      └─ ResearchAgent.execute(plan, ctx)
 │           ├─ ToolRegistry.plan_for("research")            ← 靜態 allowlist
 │           ├─ cryptopanic / rss / official / alternative_me .fetch()
 │           ├─ looks_like_injection(record) → 標記但仍只當引用資料
 │           └─ LLM 抽取 ② ─▶ WorkerResult(EvidenceDraft[])
 │      ※ 任一分支逾時 → 取消並 await 未完成 task，**保留另一分支的完成結果**
 │
 ├─▶ EvidenceProcessor.process(drafts)                       [deadline 360s] 🚫 無 LLM
 │      validate → normalize → content_hash 精確去重
 │      → independence_group → 靜態 reliability → ev_001…
 │      → detect_material_conflict → rank
 │      └─▶ EvidenceLedger + ConflictIndicator[]
 │           └─▶ artifacts.write("evidence.json")   ★★ 立刻落盤，不等 Arbiter
 │
 ├─▶ DisabledConflictExtension.evaluate(...)  → route="arbiter"   (MVP 永遠如此)
 │
 ├─▶ Arbiter.run(ledger, indicators)                         [LLM ③, deadline 510s]
 │      select_evidence(≤30)  →  build_evidence_payload()  # 只送 ID + normalized_fact
 │      → LLM 生成 → structural_violations() → detect_cycle() → apply_confidence_caps()
 │      → 失敗則 build_repair_messages() 重試 **一次**（共用同一 deadline）
 │      → 仍失敗 → _fallback()（由 ledger facts 組低信心結果）
 │      └─▶ AnalysisResult
 │
 └─▶ Renderer.render(result, ledger)                          🚫 無 LLM
        11 段模板 → trust scorecard 區塊 → 量化 invalidation 區塊
        → lint.check()  ★ 最後一道
        └─▶ artifacts.write("final_report.md")
             └─▶ artifacts.finalize()  → 更新 run_config.json（terminal state + checksum）
```

### C. 橫切關注點的活體路徑：一個數字怎麼保持可回溯

```text
Binance /api/v3/klines
   └─▶ binance.py  ─▶ SourceResult(params 去識別, fetched_at, data)   # provider 欄位止步於此
         └─▶ market_series.py  ─▶ MarketBar[]（只取 ≤ analysis_as_of 的完整日 K）
               └─▶ indicators.return_over(bars, n=14)  ─▶ 0.0731
                     └─▶ market_worker  ─▶ EvidenceDraft(
                            normalized_fact="BTC 14 日報酬為 7.31%（至 2026-07-16 UTC）",
                            content_reference="2026-07-02..2026-07-16 收盤序列",
                            query_or_parameters="symbol=BTCUSDT&interval=1d",
                            source_type=market, published_at=..., fetched_at=...)
                           └─▶ processor  ─▶ EvidenceItem(ev_007, reliability=high,
                                                independence_group="binance.com",
                                                content_hash=sha256(...))
                                 └─▶ evidence.json                     ★ 已落盤
                                 └─▶ arbiter payload: {"id":"ev_007","fact":"…7.31%…"}
                                       └─▶ Claim(cl_002, links=[cl_002←ev_007 supports])
                                             └─▶ renderer 印出 "7.31%（ev_007）"
```

> **這條鏈上沒有任何一步是 LLM 產生數字的。** LLM 只在最後兩步做「挑哪些 ID、怎麼串成論述」。
> 把 `adapters/` 之外的任何模組加上 `import boto3`，這條保證就破了——這正是
> [Tech-Stack-Plan.md §6.5](Tech-Stack-Plan.md) 第一條 CI lint 要擋的事。

### D. 降級路徑：Arbiter 兩次都失敗

```text
Arbiter.run()
  ├─ LLM 生成 → structural_violations() → ✗ 缺 evidence 參照
  ├─ build_repair_messages(errors, previous_json) → LLM 再一次（**同一個 deadline**）
  ├─ 仍 ✗
  └─▶ _fallback(ledger)
        └─ 由 validated facts 組 AnalysisResult(insufficient_data=true, confidence=low,
             degradation_notes=["Arbiter schema 驗證兩次失敗，改用 deterministic fallback"])
              └─▶ Renderer 照常跑 11 段（fallback 版）
                   └─▶ artifacts：四份仍然齊全
                        └─▶ RunSummary(terminal_state="degraded")
                             └─▶ ui/presenter → UI 顯示 fallback 橫幅
```

> **注意 `evidence.json` 在這條路徑上完全不受影響**——它在 Arbiter 之前就寫好了。
> 這就是「artifact-first」排序存在的理由。

### E. Run mode 與設定路徑

```text
UI 選 run_mode ─▶ AnalysisRequest.run_mode（驗證後**不可變**）
     │
     ├─▶ config.Settings + run_mode ─▶ adapter factory
     │        official  : 🚫 拒絕 fixture / recorded；只允許帶 source time+cache time+stale 的 cache
     │        rehearsal : 允許 deterministic fixtures 與自訂 analysis_as_of
     │        demo      : 先試 live；失敗才可用 recorded bundle（且必須標示原始取得時間）
     │
     ├─▶ run_config.json.run_mode          （每個 artifact 都帶）
     ├─▶ execution_log.jsonl 每一行的 run_mode
     └─▶ ui/presenter → 常駐模式標籤 + recorded-fallback 警示
```

### F. R16 創意層路徑（全 deterministic，掛在既有資料上）

```text
market_worker
  ├─▶ regime.classify(bars)  →  MarketRegime(label, metrics, thresholds)
  │      └─▶ EvidenceDraft(source_type=market, reliability=high)  ─▶ ev_012
  └─▶ 門檻值（近 N 日最高/最低收盤、rolling 量能均值）
         └─▶ EvidenceDraft(reliability=high)  ─▶ ev_007, ev_008 …

arbiter  ─▶ invalidation_conditions[{metric, operator, threshold, basis_evidence_id: ev_007}]
              ※ 數字來自 ev_007，🚫 LLM 不得自造

evidence/trust.py（純函數，跑在 Arbiter 之後）
  └─ (ledger, links, conclusion claims) ─▶ TrustScorecard[]（五面向 ordinal + 原始計數）
        ※ 與 confidence rubric 交叉檢查：<2 group 不得 strong；有 conflict → consistency=weak

renderer ─▶ ① regime headline ② per-conclusion scorecard ③ 量化 invalidation 區塊
             └─▶ lint.check()   ★ 仍然最後跑
```

---

## 6. 為什麼是這個形狀

- **可回溯性**：deterministic 模組（`data/`、`evidence/`、`reporting/`）與 LLM 模組（`reasoning/`）
  分屬不同 package，且前者**物理上無法** import `adapters/bedrock.py`。
  「LLM 不得補市場數值」因此不是一條靠自律遵守的規則，而是一條 import 就會被 CI 擋下的界線。
- **可測試性**：所有外部接觸點都在 `ports.py` 後面，所以整條 pipeline 可以用 `tests/fakes.py`
  離線跑完——這正是 Bronze（無網路、無 Bedrock、無 AWS 憑證仍產出四項 artifacts）之所以可能。
- **時限韌性**：`orchestration/` 獨佔時間與狀態，所以「第 12 分鐘取消一切外部呼叫」是一個地方的決定，
  不是散落在十個 adapter 裡的 if。artifact 寫入順序（config → log → evidence → report）
  讓每一次失敗都停在「已經交付了一部分」而不是「什麼都沒有」。
- **四人並行**：`models.py` + `ports.py` 是唯一的共用面；其餘四個 package 路徑互不重疊，
  所以四條分支可以同時 commit（見 [Implementation-Plan.md](Implementation-Plan.md) 的路徑佔用表）。
- **誠實性**：H3 只有一個停用實作、一個 `UNIMPLEMENTED_LABEL` 常數，
  所以「宣稱用了 Bull/Bear/Judge」在程式碼層面就沒有東西可以指。

---

## 7. 這份地圖目前指出的未決與已決事項

### 已決（保留 row 當麵包屑）

1. **`evidence/types.py` 的退場時機**：已決定**凍結並保留**直到所有 downstream consumers
   （`reasoning/*`、`data/*`、`orchestration/pipeline.py`）完成機械式 swap 遷移至 `models.py`。
   `pipeline.py` 的 `to_contract_ledger()` 是橋接層，確保兩套型別並存期間的正確轉換。

### 待裁決

1. **`data/analogs.py`** 不在 canonical tree。
   → 併進 `data/indicators.py`／`market_worker.py`，或修改 `structure.md`。二選一。
2. **`adapters/okx.py`** 不在 canonical tree，且與「單一 baseline live market source + 誠實降級」的
   核准決定衝突。→ 已預設不搬。
3. **`evidence/evidence_json.py` dual-writer 問題**：此檔使用非 canonical schema
   （`"schema": "evidence-ledger/p2-prototype-v1"`），其 payload 結構與 `evidence-contracts.md` §12
   衝突。`reporting/artifacts.py` 是 canonical `evidence.json` writer。兩個 writer 不得同時對
   同一個 graded 固定檔名寫入。→ 裁決：canonical pipeline 必須只使用 `reporting/artifacts.py`；
   `evidence_json.py` 僅供 P2 舊流程過渡，不進入正式 pipeline path。

（同樣的事項也記在 `docs/ACTIVE_WORK.md` 的「待 P1 裁決」。此處保留是為了讓檔案地圖自洽。）

---

**下一步 →** [Implementation-Plan.md](Implementation-Plan.md)：把這些檔案排進**可獨立驗證的建置階段**，
每個 stage 的「元件」欄位都會指回上面的 row。

## 2026-08-02 S8/S9/S9B + live/UI/calc-skills status addendum

S10 Gold local Exit acceptance is now tracked by `tests/acceptance/`, with the
offline runner in `scripts/run_acceptance.py` and evidence in
`docs/rehearsals/run-log.md`. These are verification-layer additions; production
pipeline boundaries are unchanged. S11 deployment remains separate.

The live composition root also owns deterministic Arbiter evidence-link repair
(`_GroundingRepairLLM`): only links justified by matching evidence atoms or a
supported upstream claim are added before the frozen reasoning gate.

`orchestration/{pipeline,deadline,run_state}.py` owns deadline-aware H2-Lite sequencing;
`evidence/trust.py` owns deterministic scorecards; `reporting/renderer.py` owns Trust/Regime
and the dual-only comparison section. `_provisional_seams.py` is **retired** — runtime imports
point at canonical `models.py`/`ports.py`. The **live composition root** is now
`src/hoya_agent/composition.py` (`build_live_pipeline`：Binance ＋ Fear & Greed → `MappingArbiter`
over凍結 Arbiter via `reasoning/mapping.py` + `reasoning/schemas.py`); `adapters/live_sources.py`
bridges async fetchers into the deterministic pipeline's sync hooks. **Streamlit Bronze UI** landed
in `src/hoya_agent/ui/{presenter,streamlit_app}.py` with live progress, trust funnel (G3), enforced
`reporting/advice_lint.py`, and self-bootstrap onto `sys.path`. Deterministic fact-grounding (G1,
`evidence/grounding.py`) is wired into the pipeline/confidence path; cross-source triangulation
helpers (G2, `evidence/triangulation.py`) exist but are **not wired into the run**. `src/calc/` and
`src/skills/` are tracked parallel tool packages (price-analysis scripts), not part of the agent
pipeline. Silver live Exit passed 2026-08-02 (`tests/live/test_live_silver_pipeline.py` 1 passed in
50.15s). Details: [S8-S9-S9B implementation](S8-S9-S9B-implementation.md) and
[EC2 deployment guide](deploy-ec2.md).
