# P2 · 資料 / 證據側(Data / Evidence)

HOYA 加密市場分析 AI Agent 的**資料側**原型:把多個來源的原始資料 → 正規化 →
產出**可回溯、標好可信度**的證據,再合併成一份**統一證據帳本**交給 P3(Arbiter)。

> 定位:本模組**只負責「取得 + 清洗 + 證據化 + 去重排序」**。判斷（立場、結論）交給 P3。
> **不做**:LLM 推理判斷(P3)、報告產生(P1)、UI(P4)。市場數值**完全 deterministic、不碰 LLM**;
> LLM 只用於**新聞語意抽取**（結構化、無立場、不編數字），且可換 provider。

> 📄 **交付／整合報告（給隊友看）**:https://claude.ai/code/artifact/a93c4643-eae4-4e50-96b0-6c9da7c30a2e

---

## 快速開始

```bash
python -m pip install -e ".[dev]"      # 或 pip install httpx pytest pandas
python -m pytest -q                     # 104 passed（含真官方資料 golden 測）

python verify.py            # 離線完整流程 + 每張卡「完整欄位」（= 欄位契約，給整合對接）
python run_full.py          # 5 幣真 CSV → 規模示範（9,130 筆日K → 25 筆證據）
python run_live.py BTC      # 真 live 四類來源（新聞/社群/情緒/市場）+ 真 LLM 語意抽取
```
> 三個腳本用途不同:**verify=離線契約/斷網備案**、**run_full=資料規模**、**run_live=真·多源信任提煉**。
> 環境:Python 3.12（開發用 3.11 也可跑；整合/Docker 請用 3.12）。
> 預設 `pytest` **不打外網**;所有 adapter 用 `httpx.MockTransport` 測。
> `run_live.py` 需外網;設 `OPENAI_API_KEY` 才啟用 LLM 語意層（沒設則誠實略過，不放假資料進帳本）。

---

## 給整合者(P1 / P3)：對接點

### 1) 資料流與公開函式
```
主辦 CSV / Binance / CoinGecko ─┐
CryptoPanic / RSS / Fear&Greed / Reddit ─┤→ 每個來源產出 EvidenceDraft[]
                                          ▼
                         build_ledger(all_drafts) → EvidenceLedger（去重/排序/ID）
                                          ▼
                              交 P3 Arbiter：ledger.top(30)
```

| 函式 | 位置 | 產出 |
|---|---|---|
| `load_organizer_csv(path)` | `adapters/organizer_csv.py` | `list[MarketBar]` |
| `fetch_binance_daily(asset, *, analysis_as_of, client)` | `adapters/binance.py` | `(list[MarketBar], degradation)` |
| `build_market_evidence(asset, bars, *, analysis_as_of, source_name, independence_group, source_url)` | `data/market_worker.py` | `WorkerResult`（市場 EvidenceDraft） |
| `build_regime_evidence(asset, bars, *, analysis_as_of)` · `classify_regime(...)` | `data/regime.py` | `WorkerResult`（市場狀態 Regime） |
| `fetch_coingecko_snapshot(asset, *, analysis_as_of, client)` | `adapters/coingecko.py` | `WorkerResult` |
| `fetch_cryptopanic_news(*, assets, analysis_as_of, client, api_token)` | `adapters/cryptopanic.py` | `WorkerResult` |
| `fetch_rss_news(asset, *, analysis_as_of, client, feed_url, source_name, publisher_domain)` | `adapters/rss.py` | `WorkerResult`（第一手媒體，medium） |
| `fetch_fear_greed(*, analysis_as_of, client)` | `adapters/alternative_me.py` | `WorkerResult` |
| `fetch_reddit_posts(asset, *, analysis_as_of, client)` | `adapters/reddit.py` | `WorkerResult`（**Atom feed**；`.json` 已被 Reddit 擋） |
| `clean_text(raw)` | `data/text_clean.py` | `str`（去 HTML/實體/正規化空白） |
| `extract_news_facts(records, *, llm)` | `reasoning/research_extractor.py` | `WorkerResult`（LLM 結構化多筆事實） |
| `build_ledger(drafts, *, max_for_arbiter=30)` | `evidence/processor.py` | `EvidenceLedger` |

**慣例**:每個 adapter 都**注入一個 `httpx.Client`**（測試給 MockTransport、正式給真 client）＋ 一個
`analysis_as_of`（凍結的 UTC 基準,只收此時間以前的資料）。失敗一律回**降級**、不丟例外，
所以任一 optional 來源掛掉不會拖垮整個 run。

### 2) 資料型別（⚠️ 臨時型別，待換 P1 的 `models.py`）
以下型別是我先寫的**臨時版**，**欄位名已對齊 `evidence-contracts.md`**，P1 交出正式 Pydantic
models 後**機械式替換 import 即可**：
- `data/types.py` → `MarketBar`
- `evidence/types.py` → `EvidenceDraft`、`EvidenceItem`、`EvidenceLedger`
- `data/market_worker.py` → `WorkerResult`

### 2b) 證據欄位契約（每筆 EvidenceItem 的完整欄位）
`EvidenceDraft` = 下表欄位；`EvidenceItem` = draft ＋ `evidence_id` ＋ `content_hash`（由 processor 補）。

| 欄位 | 說明 | 命題必填 |
|---|---|---|
| `evidence_id` | 帳本穩定 ID `ev_001…`（processor 給） | |
| `content_hash` | SHA-256 去重指紋（processor 給） | |
| `asset` | 幣種；`None`=全市場（如 Fear&Greed） | |
| `source_type` | `market` / `news` / `social` | |
| `source_name` | 來源名稱 | ✅ source |
| `source_url` | 來源網址 | ✅ source |
| `published_at` | 發布時間（UTC；無則 `None` 並揭露） | |
| `fetched_at` | 取得時間（UTC，tz-aware） | ✅ fetched_at |
| `query_or_parameters` | 可重現參數（**不含金鑰**，寫 `credentials removed`） | |
| `content_reference` | 引用片段／指標範圍／摘要 | ✅ content_reference |
| `normalized_fact` | 一句事實命題（無立場） | |
| `reliability` | `high`/`medium`/`low`（靜態表） | |
| `independence_group` | 上游獨立群（原發布者／註冊網域） | |
| `is_cached` / `cache_time` / `is_stale` | cache 狀態 | |
| `metric_name` / `metric_value` | 市場證據專用（如 `return_14d` / `-0.0488`），可精確回溯 | |

> `related_claim`（命題第 4 欄）由 **P3 建立 Claim-Evidence Link 時補**——要先有結論才知道連到哪。

### 3) 新聞語意抽取（P3 邊界，暫放這裡）
`reasoning/` 是 **P3 的範圍**（我先搭好骨架，整合時可交接）。兩段式:先 deterministic 清洗，再 LLM 結構化理解——
LLM **只判相關性 / 分事件類型 / 抽多筆無立場事實**,不編數字、不給可信度、不表態:
- `data/text_clean.py` → `clean_text()`：去 HTML/實體/空白，LLM 只看乾淨純文字
- `reasoning/research_extractor.py` → `extract_news_facts()`：一篇 →「相關性 + 事件類型 + 多筆原子事實」,**一篇可產多張證據卡**（非單篇摘要）
- `reasoning/llm_client.py` → `LLMClient` 介面 + `FakeLLMClient`（測試）
- `reasoning/gpt_client.py` → GPT mock（讀 `OPENAI_API_KEY`）
- `reasoning/bedrock_client.py` → **`BedrockClient`（正式）**：boto3 `bedrock-runtime` `invoke_model`，model id/region 讀環境變數，走標準 AWS 憑證鏈（Bedrock API 金鑰／臨時憑證／EC2 IAM 角色皆可，無需改碼）。
- **provider 自動選擇**：`run_live.py` 設 `BEDROCK_MODEL_ID` → 用 Bedrock；否則 `OPENAI_API_KEY` → GPT；都沒有 → 誠實略過。

  ```powershell
  $env:AWS_REGION       = "us-west-2"
  $env:BEDROCK_MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"   # 從 Bedrock 模型目錄複製
  $env:AWS_BEARER_TOKEN_BEDROCK = "..."   # 或用 IAM 角色 / 臨時憑證
  python run_live.py BTC        # [LLM] 那段即跑 Bedrock
  ```

### 4) 刻意不做的事（界線）
- ✕ **TA 技術指標**（MACD/RSI/K線型態）——題目明訂「不是技術指標回測」;我的指標是**狀態描述**非買賣訊號。
- ✕ **用 LLM 產生市場數字或可信度**——數字只來自 deterministic 工具、可信度只來自靜態表。
- ✕ **立場（利多/利空）**——只在 P3 的 Claim-Evidence Link 才產生。
- ✕ **前端/K線圖**——P4 的事;該呈現的是「證據與信任」不是看盤圖。

---

## 採用的指標與「選擇依據」

**官方（HOYA）只提供資料（OHLCV CSV），未指定指標。** 以下指標由**團隊 spec 指定**——
清單見 `tasks.md` Task 4、公式定義於 `evidence-contracts.md §15`——本模組**依 spec 實作**。
選用這些指標的理由:(1) 只用官方 OHLCV 就能算、可重現;(2) 業界標準量化指標;(3) 對應三種題型。
**預設窗口（14/30/90）是本模組挑的合理值（spec 只要求「declared window」，未定天數），可透過 `MarketWindows` 調整。**

| 指標 | 定義 | 對應題型/用途 |
|---|---|---|
| `simple_return(n)` | close[T]/close[T−n] − 1 | 走勢（範例一） |
| `realized_volatility(n)` | 近 n 日日報酬樣本標準差(ddof=1) | 風險、盤整判斷（範例二） |
| `max_drawdown(n)` | 近 n 日 close/cummax − 1 最小值 | 下檔風險 |
| `rolling_volume_zscore(n)` | 最新量相對自身近 n 日 z-score | 量能異常（單幣自身比較） |
| `relative_change(a,b)` | a/b − 1 | 跨幣可比尺度（範例三） |
| `market_regime`（綜合） | 報酬＋波動百分位＋區間位置 → 趨勢／盤整／高波動 | **市場狀態判斷**（範例一、二） |

### 延伸分析產出（A5/A6/A7，`data/price_analysis.py`）
移植自 `price` 分支設計文件（`price-data-analysis-outputs.html`），deterministic、幣種無關,
且**實算值對得上該文件**（回歸測試以其數字為 golden）：

| 產出 | 函式 | 用途 |
|---|---|---|
| **A5 歸因** | `attribution` / `build_attribution_evidence` | 相關性/beta/相對強弱 → 判「單幣事件 vs 全市場」（省 Research 預算） |
| **A6 事件時間軸** | `anomaly_days` / `build_event_timeline_evidence` | ±3σ 異常日 → 給 Research 的**有界查詢日期** |
| **A7 歷史類比基準率** | `analog_base_rates` | 類似狀態後 N 日的結果分布（**只談幅度、不談方向**，方向≈擲硬幣並誠實揭露） |

> 跨幣只用報酬/比值/百分位,**絕不比 base-asset volume**。`run_full.py` 已把 A5/A6 併入帳本示範。

**市場資料鐵則**：只用 `analysis_as_of` 前**已完成**的 UTC 日 K;缺 bar 標 unavailable、**不 forward-fill**;
**跨幣禁比 base volume**（單位不同）——跨幣只用報酬/波動/相對變化/各自 z-score/quote volume;
CSV↔live 以 **2026-06-01** 為來源切換點並揭露差異。

---

## 資料來源與信任分級（reliability 由靜態表決定，非人工逐筆、非 LLM）

可信度**不是主觀判斷、也不是 LLM 評分**，而是依「來源類型」查**固定表**（`evidence/policies.py`），
判準為「是否第一手/可驗證」（依 `evidence-contracts.md §4`）。

| 來源 | 類型 | 可信度 | 獨立群 | 金鑰 |
|---|---|---|---|---|
| 主辦 CSV | market | `high` | organizer-public-market-data | — |
| Binance Spot | market | `high` | binance.com | 免 |
| **OKX Spot** | market | `high` | okx.com | 免 |
| **Binance Futures（永續資金費率）** | market（衍生品維度） | `high` | binance.com | 免 |
| CoinGecko | market | `medium` | coingecko.com | 免 |
| **CoinDesk · The Block · Bitcoin Magazine · CryptoSlate · Decrypt · Cointelegraph · NewsBTC · Bitcoinist · CoinJournal**（RSS） | news | `medium` | 各自網域（9 群） | 免 |
| **Google News（依幣種搜尋）** | news | `low` | 原發布者網域 | 免 |
| CryptoPanic | news | `low` | 原發布者網域 | 免費 token |
| Alternative.me F&G | social | `low` | alternative.me | — |
| Reddit r/CryptoCurrency | social | `low` | reddit.com | — |

達標:**約 15 來源、5 個維度（市場/衍生品/新聞/社群/情緒）、~13 個獨立群、含第一手**，且 high/medium/low 三級齊全。
市場層有 **2 個獨立交易所（Binance + OKX）** 可交叉驗證,並加入 **永續資金費率(槓桿情緒)** 這個衍生品維度。
一次真 live 跑 ≈ **60 張證據卡**。
全部**幣種無關**（用符號查五幣）。**選源原則**:只收「用符號就能查五幣」的來源;要為每條鏈各寫一套的一律跳過並揭露;
**不收**任何第三方「已產出的完整判斷/交易訊號/投資報告」。

**噪音處理哲學**:不主觀刪源（判斷是 P3 的事），而是**分級 + 隔離**——低訊號社群鎖在 `low`,
結構上（confidence 上限）**無法驅動高信心結論**;這比直接刪除更可回溯。

**五幣覆蓋（現場抽哪個都能做）**:市場（CSV+OKX）、衍生品（資金費率）、情緒（F&G）對 **BTC/ETH/SOL/BNB/XRP 全涵蓋**。
新聞的一般 RSS 偏 BTC/ETH,小幣（SOL/BNB/XRP）會不足——因此加入 **Google News 依幣種搜尋**保證每個幣都有新聞（實測 5 幣各 15+ 篇）。

---

## Evidence Processor（去重／排序／帳本）
`build_ledger()` 對所有來源的 draft 做:
1. `content_hash` = SHA-256（對正規化後的事實，排除來源名/URL → 純轉載自動塌陷）
2. 依 **可信度 → 新鮮度** 排序
3. 精確 hash 去重（留最高排序的一張，記錄丟棄數）
4. 給穩定 ID `ev_001…`;`ledger.top(30)` 供 Arbiter

`EvidenceLedger` 提供 `items`、`dropped_duplicates`、`source_type_count`、`independence_group_count`、`top(n)`。

---

## 目前是 mock 還是真的?
- **`verify.py`（離線）**:主辦 CSV 是真的;Binance/CoinGecko/CryptoPanic/RSS/F&G/Reddit 用 MockTransport 餵樣本;
  LLM 用 FakeLLM。全部離線、可重現——當**欄位契約展示 + demo 斷網備案**。
- **`run_full.py`（離線）**:5 幣**全真官方 CSV**,9,130 筆 → 25 筆市場證據。
- **`run_live.py`（真 live）**:真打 6 家新聞 RSS + Reddit（Atom）+ Fear&Greed;設 `OPENAI_API_KEY` 則
  用**真 GPT** 對真新聞做語意抽取。實測一次 ≈ 60 張卡（市場/新聞/社群/情緒四類齊全）。
- **adapter 程式碼皆照真 API 寫、契約測過**;接真只要換真 `httpx.Client`。正式 LLM 換 Bedrock 只改注入一行。

---

## 待整合 / 待辦（給團隊）
- [x] 接真 live 多源（`run_live.py`：6 新聞 + Reddit + F&G，+ 真 GPT 語意抽取）
- [ ] 整合進主 repo `src/hoya_agent/`（目前為獨立原型）
- [ ] 換 P1 的正式 `models.py`（替換臨時型別）
- [ ] 落盤 `evidence.json`（等 P1 artifact 契約）
- [ ] material conflict 偵測（需 P3 的 Claim 結構）
- [ ] `research_extractor` 歸屬確認（P2 or P3）
- [ ] LLM 由 GPT mock → **Bedrock 上的 Claude**

---

## 檔案地圖
```
adapters/  organizer_csv · binance · okx · coingecko · cryptopanic · rss · alternative_me · reddit · _assets
data/      types(MarketBar) · indicators · market_series · market_worker · regime(市場狀態) · text_clean(清洗)
evidence/  policies · types(EvidenceDraft/Item/Ledger) · processor
reasoning/ llm_client · research_extractor(結構化多筆) · gpt_client   ← P3 邊界
verify.py  離線契約   run_full.py  規模示範   run_live.py  真·多源+LLM     tests/  104 passed
```

> 本模組**產研究導向分析,不提供投資建議**。
