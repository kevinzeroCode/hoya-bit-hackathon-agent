# HOYA Market Agent — 技術棧、架構與可回溯性基礎計畫

> **② of ⑤ — design-pipeline 第二份產出。**
> 上一份：[Features.md](Features.md)｜下一份：[Architecture-FileMap.md](Architecture-FileMap.md)｜索引：[README.md](README.md)

> **這份文件是衍生視圖，不是新的真相來源。**
> 規範性權威仍是 `.kiro/specs/hoya-market-agent/` 與 `.kiro/steering/`（技術棧的規範性擁有者是
> `tech.md`，模組邊界是 `structure.md`）。本文的工作是把那些鐵則**收攏成一份「動工前必須鎖死的決定」**，
> 並補上 `.kiro` 沒有明說的兩件事：授權/合規對照與**風險導向的第一個里程碑**。
> **若本文與 `.kiro/` 衝突，以 `.kiro/` 為準。**

## 1. Context

[Features.md](Features.md) 列出了這個 agent 做得到什麼。本文回答動工前**必須先鎖死、事後改代價極高**的幾件事：

1. 用什麼技術棧、什麼授權姿態；
2. 分層長什麼樣、依賴往哪個方向流；
3. Features.md §7 列出的外部相依面要抽多厚；
4. **唯一那個會塑形整個架構的橫切關注點**——「證據可回溯性」——端到端怎麼設計、怎麼強制；
5. 第一個里程碑該切哪一刀，才能在第一天就知道架構是不是錯的。

專案硬限制：**4 位 junior developer、2 個日曆天、單次 15 分鐘的正式執行機會**。
這個限制本身就是最強的架構壓力——它排除了任何需要「先建基礎設施才能跑第一次」的方案。

---

## 2. Decisions（已確認鎖定）

以下每一項都已在 `.kiro/steering/tech.md` 核准，本文只是把它們並列成一張可十秒讀完的表。
**要改任何一項，必須先改核准設計，不得為了實作方便繞過。**

### 2.1 技術棧（confirmed）

| 面向 | 鎖定選擇 | 附註 |
|---|---|---|
| 語言 | **Python 3.12** | 所有 public function 要型別註記 |
| 驗證 | **Pydantic v2** | 所有跨模組 payload 都是 validated model；`extra="forbid"` |
| 非同步 | **標準庫 `asyncio`** | 只用顯式 fork/join 與 deadline，🚫 無框架 |
| HTTP | **`httpx.AsyncClient`** | 每個 run / application lifecycle 共用一個 client |
| 表格計算 | **`pandas`** | 只用於 deterministic 市場指標 |
| AWS SDK | **`boto3`** | Bedrock Runtime **Converse API** |
| LLM | **Amazon Bedrock** | primary + optional fallback model ID 來自 config |
| UI | **Streamlit** | 與 application service **同 process** |
| 測試 | **`pytest` + `pytest-asyncio`** | mock provider 契約；rehearsal fixture 做 E2E |
| 打包 | **`pyproject.toml` + `src/` layout** | 部署前釘死可重現的 dependency lock |
| 執行環境 | **Docker → ECR → 單台 EC2 → Docker Compose** | MVP 一個 image、一個 service |
| Log / artifact | **stdout + JSONL + 本機 volume** | 🚫 S3 / CloudWatch 非 MVP |

**🚫 禁止引入**（除非先改核准設計）：LangGraph、AWS Strands Agents、FastAPI、Celery、Redis、
message broker、向量資料庫、任何其他 orchestration 框架。

### 2.2 授權姿態（confirmed）

- **全部執行期相依都是寬鬆授權**（PSF / MIT / BSD-3 / Apache-2.0）——**沒有 copyleft 義務**，
  可安全地打進單一 Docker image 分發，本專案原始碼授權不受牽動。詳見 §8。
- **資料與內容的授權風險不在函式庫，而在「引用了什麼」**：`content_reference` 必須是
  **短引文 / 指標 / 有界摘要**，🚫 不得是整篇受著作權保護的文章。這條在 `evidence-contracts.md §3`
  是欄位規則，在本文是**授權義務**——見 §8 的義務→動作對照。

### 2.3 兩個橫切設計（confirmed）

- **頭號橫切關注點：Evidence 可回溯性（"evidence-out-of-LLM"）。**
  每一個關鍵結論都必須經 Evidence ID 回溯到 deterministic tool output 或已取得的來源；
  **LLM 產物永遠不是證據來源**。這一條決定了模組怎麼切、依賴往哪流、CI 要 gate 什麼——§6 端到端設計。
- **第二橫切：Run mode 誠實性。** `official|rehearsal|demo` 在 run 開始後不可變，
  且在 UI / 每一筆 log / `run_config.json` 都可辨識。它不像可回溯性那樣塑形分層，
  但它決定了 `config.py`、`ArtifactStore` 與 UI presenter 的介面必須攜帶 mode。

---

## 3. 支撐這些決定的證據

這個專案的優勢是**不必猜**：repo 裡已經有三份真實產出可以反推。

### 3.1 已合併進 `main` 的 reasoning 層（`task/6-bedrock-reasoning`，22 個 `.py`，157 passed）

實測結論：

- **一個 371 行的 `adapters/bedrock.py` 就能把 Bedrock 邊界做完整** ——
  強制 tool call 取得結構化輸出、逾時 clamp（`effective_timeout` 對 `MAX_CALL_TIMEOUT_SECONDS = 45.0`
  與剩餘 stage 時間取小）、可重試錯誤碼白名單、一次 schema repair、備援模型。
  → **驗證了「thin LLM port」是可行的，不需要 agent 框架。**
- **Planner / ResearchAgent / Arbiter 可以在沒有 `models.py` 的情況下先寫完並全綠**
  （用 `tests/unit/reasoning/_stubs.py` 與 `evidence/types.py` 的 provisional dataclass）。
  → **驗證了「以 Protocol 與欄位名為契約」比「以具體型別為契約」更能讓四人並行**。
  但也暴露代價：後續必須做一輪機械式型別替換（見 ④ Stage 1 的 deviation 紀錄）。
- `arbiter.py` 478 行裡，**只有一小段在呼叫 LLM**；`select_evidence`、`detect_cycle`、
  `structural_violations`、`apply_confidence_caps` 全是 deterministic 純函數。
  → **直接印證了 §6 的設計：把驗證留在 Python，prompt 只負責產出草稿。**

### 3.2 P2 原型（`feat/p2-report-integration`，48 個 `.py`，122 passed）

一份**能跑、有測試**的平行實作，涵蓋 adapters / indicators / market_worker / regime /
evidence policies / processor / HTML 報告產生器。反推出來的教訓：

- 它用**頂層平面 import**（`from data.indicators import ...` + `pythonpath = ["."]`）配一個獨立的
  `p2-etl-mvp/pyproject.toml`。搬進套件樹時 48 個檔的 import 全斷。
  → **確認 `src/` layout + `hoya_agent.` 絕對 import 必須在 Day 1 就鎖死**，不能等到收斂時才決定。
- 它獨立長出了第二套 LLM 邊界（`reasoning/llm_client.py` + `gpt_client.py`）。
  → **確認「LLM port 只能有一個擁有者」必須寫成明文規則**，否則兩個人會各寫一套且各自測試都會過。
  **裁決（已記於 `docs/ACTIVE_WORK.md`）：留 `adapters/bedrock.py`，刪 `gpt_client.py` / `run_gpt_extract.py`；
  P2 的 `research_extractor.py` 保留其 relevance filtering 與多事實拆解，但改為依賴 `bedrock.py`。**
- 它寫了 `adapters/coingecko.py`。而 steering 已定 CoinGecko 為 post-hackathon Future Work。
  → **確認 §7 的「adapter 一律出現在 canonical tree 才准寫」規則有實際價值。**

### 3.3 主辦方資料集實測（`docs/price-data-analysis-outputs.html`）

以主辦方五幣 Daily OHLCV **實算**過的結果：

- 資料集 **0 缺漏日、0 NaN、0 筆 OHLC 違反** → **不需要缺口填補邏輯**，`data/` 可以更薄。
- 每列 `open` 幾乎等於前列 `close` → `open` 不帶獨立資訊，指標設計不必為它多開一條路徑。
- A1–A10 十個分析產出（含五幣 regime 標籤）已實算可行 → **Requirement 16 的 Market Regime 不是空想**。
  ⚠️ 但該文件的 regime 值是以 `as_of 2026-05-31` 算的**示範值**，🚫 不得寫死進程式或報告。

### 3.4 我們刻意的偏離

| 常見做法 | 我們的選擇 | 理由 |
|---|---|---|
| 用 agent 框架（LangGraph / Strands）編排 | 手寫 `asyncio.gather` + `DeadlineManager` | 15 分鐘硬限要求**精確**的 stage deadline 與取消語意；框架的重試/循環會偷走時間預算。且 4 位 junior 學框架的成本 > 寫 200 行編排。 |
| 讓 LLM 寫最終報告 | deterministic 模板 Renderer | 報告禁語與「不得出現 Ledger 外的新事實」只有在 deterministic 路徑上才可驗證。 |
| 用向量檢索/語意去重提升召回 | SHA-256 精確去重 | 語意分群不可驗證、會誤併對立事實，且兩天內無法校準。 |
| 動態來源信譽評分 | 靜態 reliability 表 | 可審查、可測試、評審能一眼看懂；動態評分無法在單次 run 內校準。 |
| 多 provider fallback 鏈 | 單一 baseline + 誠實降級 | 「宣稱切換到第二個 provider」但其實沒實作，是直接丟分的誠實性風險。 |

---

## 4. 目標架構

### 4.1 目錄佈局（canonical；規範性擁有者是 `structure.md`）

```text
src/hoya_agent/
  models.py                 # 所有共用 Pydantic 契約；不 import 任何專案模組
  config.py                 # typed Settings + sanitized snapshot（只記 key 存在與否）
  clock.py                  # 可注入的 UTC / monotonic clock
  ports.py                  # 共用 Protocol 邊界；無具體 I/O
  application.py            # 單一 use-case 入口 + 組裝根（composition root）
  orchestration/            # deadline、run state、pipeline 順序
  data/                     # 市場序列、指標、Market Worker、regime
  adapters/                 # 扁平的外部 I/O 模組（唯一可 import httpx / boto3 之處）
  evidence/                 # ledger、policies、processor、trust
  reasoning/                # planner、research 抽取、arbiter、H3 停用樁
  reporting/                # deterministic renderer、artifacts、lint
  ui/presenter.py           # domain → Streamlit view model；不含商業邏輯
prompts/                    # 版本化的 planner / research / arbiter Markdown
streamlit_app.py            # UI 入口；只 import ApplicationService 與 presenter
tests/
  unit/ contract/ integration/ acceptance/ live/ fixtures/
```

**紀律：** 🚫 不為單一 helper 新增 package；🚫 不新增 `llm/` 或 `observability/`；
`adapters/` 在兩天 MVP 內保持**扁平**（一個 provider 一個檔）。

### 4.2 依賴方向：只准向內

```text
streamlit_app.py
      │ 只 import
      ▼
ui/presenter.py + application.py
      │
      ▼
orchestration/  ──▶  data/ + evidence/ + reasoning/ + reporting/
                              │
                              ▼
                          ports.py  (Protocol 介面)
                              ▲
                              │ 實作
                          adapters/  (httpx / boto3 只在這裡)

                    所有模組 ──▶ models.py  (不 import 任何專案模組)
```

**層契約（違反 = 設計 bug，不是風格問題）：**

- `models.py` 不 import 任何專案模組——它是圖的葉節點。
- `clock.py` 獨佔 UTC / monotonic 存取，所以 deadline 測試不需要真的 sleep。
- `ports.py` 只放 Protocol（adapter、LLM、worker、progress、clock、artifact store），🚫 無具體 I/O。
- `config.py` 可 import `models.py`，🚫 永不 import adapter 或 UI。
- `application.py` 是**唯一**知道具體實作存在的地方（組裝根）；provider 解析留在 adapter。
- `orchestration/` 協調 stage 與失敗，🚫 不算指標、不指派 reliability、不 render Markdown。
- **`data/`、`evidence/`、`reporting/` 是 deterministic，🚫 永不呼叫 Bedrock。**
- **只有** `adapters/*.py` 可以 `import httpx` / `import boto3`。
- `reasoning/` 消費 `LLMClient` 與 evidence ID，🚫 不寫 artifact。
- `ui/presenter.py` 只造 display model；`streamlit_app.py` 🚫 不 import 具體 adapter 或 pipeline 內部。
- `prompts/`、`HOYA_BIT_crypto_market_dataset/`、`tests/fixtures/` 是**資料，不是程式碼**——
  執行期載入，production code 🚫 不得 import fixtures。

### 4.3 生態系已經免費給我們的 vs. 必須自己寫的

抽象層要**薄**，所以先誠實列出哪些不需要自己做：

**Python / 相依函式庫已經跨平台給我們的**（🚫 這些**不進** port 層）：
資料驗證與序列化（Pydantic）、非同步 fork/join 與取消（`asyncio`）、HTTP 連線池/逾時/重試原語（`httpx`）、
rolling 統計與時間序列對齊（`pandas`）、AWS 簽章與 Converse 傳輸（`boto3`）、
UI widget / session state / 檔案下載（Streamlit）、原子 rename（`os.replace`）、測試替身（`pytest`）。

**必須自己寫的**（這份清單**就是** `orchestration/`、`evidence/`、`reporting/` 存在的理由）：

| 必須自己寫 | 為什麼生態系給不了 | 落在哪 |
|---|---|---|
| 以 monotonic 為基準、可依比例縮放、且 retry/repair 共用預算的 stage deadline 樹 | `asyncio.wait_for` 只給單點逾時，不給「整條 pipeline 的絕對里程碑」 | `orchestration/deadline.py` |
| 四固定檔名 + 原子寫 + **缺檔時指名檔名**的揭露契約 | 沒有函式庫知道「哪四個檔一定要在」以及失敗時該說什麼 | `reporting/artifacts.py` |
| 靜態 reliability 表、independence group 推導、精確 hash 去重 | 這是領域政策，不是通用演算法 | `evidence/policies.py`、`processor.py` |
| material conflict 判定 + confidence 上限 + claim DAG 驗證 | 同上；且必須 deterministic 才可驗收 | `evidence/`、`reasoning/arbiter.py` |
| 禁語 lint（買/賣/加倉/減倉/做多/做空/配置） | 這是合規最後防線，必須是純字串比對且最後執行 | `reporting/lint.py` |
| run mode 誠實性強制（official 拒 fixture） | 領域規則 | `config.py` + `application.py` + adapters |
| 「結構化輸出失敗 → 一次 repair → deterministic fallback」政策 | boto3 只給傳輸，不給政策 | `adapters/bedrock.py` |
| coin-agnostic regime 門檻、Trust Scorecard ordinal 映射 | 領域規則（R16） | `data/regime.py`、`evidence/trust.py` |

**Port 層因此保持薄**：只有 Features.md §7 那七個外部接觸點，
每一個都是因為「外部世界會失敗、會變、或需要在測試裡替換」才存在，🚫 不做臆測性抽象。

---

## 5. 相依與建置

**執行期相依（`pyproject.toml`）：** `pydantic`、`httpx`、`pandas`、`boto3`、`streamlit`
**開發相依（`[dev]` extra）：** `pytest`、`pytest-asyncio`、`pytest-cov`、`ruff`
**pytest marker：** `integration`、`acceptance`、`live`

**建置：**
- `pyproject.toml` + `src/` layout，支援 `python -m pip install -e ".[dev]"`。
- 部署前釘死可重現的 dependency lock（immutable image tag 才有意義）。
- 單一 non-root Docker image；Streamlit + application service + pipeline **同一個 container、同一個 process**。
- 只暴露 demo 需要的那個 Streamlit port；掛一個持久化的本機 artifact volume（🚫 不寫進 image layer）。
- push immutable tag 到 ECR，EC2 用 `docker compose` 拉**確切測過的那個 tag**。

> ⚠️ **目前的實況**：`pyproject.toml` **尚不存在**（屬 ④ Stage 1）。在它落地前，跑測試用臨時 venv：
> ```bash
> uv venv --python 3.12 .venv
> uv pip install --python .venv/Scripts/python.exe pydantic pytest pytest-asyncio boto3 httpx
> PYTHONPATH=src ./.venv/Scripts/python.exe -m pytest tests -q
> ```
> **🚫 在 Stage 1 之前不要自己建 `pyproject.toml`**——那會開出第三棵樹（見 ACTIVE_WORK 的協調規則 2）。

---

## 6. 頭號橫切關注點：Evidence 可回溯性，端到端設計

> **一句話規則：報告裡的每一個事實性陳述，要嘛對應到一筆 validated `EvidenceItem`，要嘛不存在。
> LLM 的產物永遠不是證據來源。**

這一條之所以是**架構層級**而不是實作細節，是因為它同時決定了：模組怎麼切（deterministic 與 LLM 分家）、
依賴往哪流（`reasoning/` 不能寫 artifact）、artifact 寫入順序（evidence 先於 report）、
以及 CI 要 gate 什麼。事後補是補不上的。

### 6.1 格式

**證據原子（`EvidenceItem`）** 必攜：來源身分（`source_type`/`source_name`/`source_url`）、
`fetched_at`、`published_at`（真的沒有才可為 `null`，且必須記為限制）、`query_or_parameters`（去識別）、
`content_reference`（短引文 / 指標 / 有界摘要）、`normalized_fact`（**單一**事實命題）、
`reliability`、`independence_group`、`content_hash`（SHA-256）、cache/stale metadata。

**關鍵不變量：`EvidenceItem` 無立場。** 立場只存在於 `ClaimEvidenceLink`
（`supports|opposes|neutral` + `reason`）。這讓同一筆證據可以支持某個 claim、同時反對另一個。

**帳本（`evidence.json`）** 是 run 級容器：`schema_version, run_id, analysis_as_of, run_mode,
items[], conflict_indicators[], degradation_events[]`。零筆 item 的帳本**只有在**
`degradation_events` 解釋了原因時才合法。

**hash 規則：** `content_hash` 只涵蓋正規化後的內容，**排除** source name、URL 與轉載時間戳，
好讓 byte-equivalent 的轉載可以塌縮成一筆。🚫 不做模糊/語意比對。

### 6.2 執行期元件與 API

```text
adapters/*        →  SourceResult[...]          （provider 欄位止步於此）
     ↓
data/ | reasoning/research_agent
                  →  EvidenceDraft[]            （= EvidenceItem 減去 processor 指派的欄位）
     ↓
evidence/processor →  EvidenceLedger + ConflictIndicator[]
     ↓
reporting/artifacts →  evidence.json            （★ 立刻落盤，不等 Arbiter）
     ↓
reasoning/arbiter  →  AnalysisResult            （只收 ≤30 筆的 ID + normalized fact）
     ↓
reporting/renderer →  final_report.md           （只讀 AnalysisResult + Ledger）
```

`EvidenceProcessor` 的 deterministic 序列（`design.md §9`）：
驗證 draft → 正規化 → 算 `content_hash` 並精確去重 → 推導 `independence_group` →
指派靜態 reliability 與 cache/stale → 配發 `ev_001…` → 偵測 material conflict → 依
reliability/直接性/時效/來源多樣性排序。

**Arbiter 的入口窄化**是這條鐵則的一部分：只餵 ≤30 筆的 ID 與 normalized fact，
所以 LLM 物理上沒有「憑空記得一個沒進帳本的數字」的機會。

### 6.3 降級行為（不是例外，是設計的一部分）

| 情況 | 行為 |
|---|---|
| 抽取不出可回溯的事實 | 該 draft 被拒收，記一筆 typed degradation，🚫 不進 Ledger |
| 缺 `published_at` | 保留 `null` + 揭露限制，🚫 不捏造時間 |
| 某分支全失敗 | 另一分支的結果照常進 Ledger；缺的那類標 unavailable |
| 完全沒有證據 | `evidence.json` 是**合法的空帳本** + degradation events |
| Arbiter 兩次都失敗 | 由 Ledger facts 組 deterministic fallback result，四項 artifacts 仍齊全 |
| R16 某面向算不出來 | 標 `unavailable` 並揭露原因，🚫 不阻塞 artifacts |

**核心保證：可回溯性永遠不會因為下游失敗而消失**——因為 `evidence.json` 在 Arbiter 之前就已經落盤。

### 6.4 怎麼強制（設計層）

1. **依賴方向本身就是強制手段**：`data/`、`evidence/`、`reporting/` 不能 import `adapters/bedrock.py`，
   所以它們**物理上**無法讓 LLM 補值。
2. **`reasoning/` 不寫 artifact**：所有落盤經過 `reporting/artifacts.py`，
   所以「LLM 直接產出交付物」在拓撲上不可能。
3. **schema 是閘門**：`extra="forbid"` + 結構驗證（參照可解析、DAG 無環、confidence 上限）
   在 `AnalysisResult` 進入 Renderer 之前執行。未通過就丟棄。
4. **Renderer 只讀兩個輸入**（`AnalysisResult` + Ledger），所以它無法加入帳本外的新事實。
5. **禁語 lint 最後跑**，即使前面全部通過也還有一道。

### 6.5 建置期閘門（CI 必須擋下的四件事）

```bash
# 1. deterministic 模組不得碰 LLM / 網路 SDK
!  grep -rnE '^\s*(import|from)\s+(boto3|httpx)' src/hoya_agent/{data,evidence,reporting,orchestration,ui}/ \
     src/hoya_agent/{models,config,clock,ports}.py

# 2. reasoning/ 不得寫 artifact
!  grep -rnE '(open\(|Path\(.*\)\.write|os\.replace)' src/hoya_agent/reasoning/

# 3. production code 不得 import 測試 fixture
!  grep -rn 'tests\.fixtures\|from tests' src/

# 4. 常規閘門
ruff check .
python -m pytest tests/unit tests/contract tests/integration -q
```

> 前三條寫成 `scripts/` 下的小 lint 或 CI step 都可以；**重點是它們必須是自動的**。
> 這正是 ④ 每個 stage 的 Definition-of-Done 都要求「boundary lint 乾淨」的原因。

---

## 7. 建議的第一個里程碑（風險導向的垂直切片）

**選擇標準是「一次撞上所有架構風險」，不是「做最多功能」。**

這個專案有兩個獨立的致命風險，而且它們**互不相依**，所以可以並行撞：

### 風險 A — 「四項 artifacts 在時限內齊全」這條路徑根本不通

命題的硬性交付就是那四個檔。如果 application service → renderer → 原子寫入這條路徑
到了第二天才第一次跑通，就沒有時間修了。

**切片 A：完全離線的 fixture 垂直切片（= Bronze）**
1. 凍結 `models.py` 契約與 `ports.py` seam。
2. 一個 BTC `rehearsal` 請求 + fixture Evidence + fixture `AnalysisResult`。
3. 穿過**真正的** `ApplicationService`（不是腳本），寫出 `run_config.json` → 串流
   `execution_log.jsonl` → 寫 `evidence.json` → deterministic render `final_report.md`。
4. 四份共用同一個 `run_id`，全部原子寫入。
5. 從 **Streamlit** 提交這一次 run 並下載四份檔案。
6. 全程**無網路、無 Bedrock、無 AWS 憑證**。

**它一次證明了：** 契約可用 · 組裝根成立 · artifact 寫入契約成立 · 缺檔揭露契約成立 ·
繁中 11 段模板成立 · 禁語 lint 成立 · UI↔application 邊界成立 · `rehearsal` 標示誠實。

### 風險 B — Bedrock 從來沒有真的被呼叫過一次

> ⚠️ `docs/ACTIVE_WORK.md`（2026-08-01）：**「Bedrock 實際呼叫 — 仍未驗證過任何一次，
> 這是目前最大的未爆彈。」** `adapters/bedrock.py` 有 371 行、契約測試全綠——
> **但那全是對著 stub 測的。** 若模型未開通、region 不對或 model ID 錯，
> 整個 H2-Lite 是死的，切片 A 做得再漂亮也沒用。

**切片 B：一次真實的 Bedrock Converse 呼叫**
1. 確認 region 與 `BEDROCK_PRIMARY_MODEL_ID` 已開通。
2. 用最小、不含敏感內容的 prompt 打一次 Converse **並取回結構化輸出**。
3. 把時間戳、region、model ID、pass/fail 記進 `docs/rehearsals/service-access-check.md`
   （🚫 不記任何憑證或 response header）。
4. 把成功證據放進 `docs/evidence/`。

**它一次證明了：** IAM/instance role 可用 · model ID 正確 · Converse 結構化輸出的實際形狀
與 `adapters/bedrock.py` 的假設一致 · 逾時 clamp 在真實延遲下合理。

> **排序理由：切片 B 不依賴任何人、卻能否決所有人，所以它排在最前面。**
> 切片 A 依賴契約凍結，是第二優先。兩者都通過之後，其餘工作才真的只是「填內容」。

**這個里程碑刻意**不**包含**：live 市場/研究來源、真實的 Planner/Arbiter 串接、
並行 fork-join、Docker、部署、R16 創意層。那些都在切片 A/B 已經證明架構成立之後才有意義。

---

## 8. 授權與合規

### 8.1 相依函式庫授權（全部寬鬆，無 copyleft）

| 相依 | 授權 | 對我們的義務 |
|---|---|---|
| Python 3.12 | PSF License | 保留授權聲明 |
| Pydantic v2 | MIT | 保留版權與授權文字 |
| httpx | BSD-3-Clause | 保留版權與授權文字；🚫 不得用作者名背書 |
| pandas | BSD-3-Clause | 同上 |
| boto3 / botocore | Apache-2.0 | 保留 NOTICE；標示修改（若有修改） |
| Streamlit | Apache-2.0 | 同上 |
| pytest / ruff（僅 dev） | MIT | 不隨 image 分發，義務最輕 |

**結論：沒有任何一項要求開源本專案原始碼，也沒有動態連結限制。**
單一 Docker image 分發是安全的。

### 8.2 義務 → 具體動作對照

| 義務 | 具體動作 |
|---|---|
| 保留第三方授權文字 | 在 image 內放一份 `THIRD_PARTY_LICENSES`（由 lock 檔產生），repo 內附同一份 |
| Apache-2.0 的 NOTICE | 若 boto3/Streamlit 附 NOTICE，一併打包，不刪 |
| 🚫 不得散布受著作權保護的全文 | **`content_reference` 只存短引文 / 指標 / 有界摘要**；adapter 層截斷長度；contract test 驗證上限 |
| 保留原始發布者歸屬 | 聚合器提供上游時，`source_url` 與 `independence_group` 用**原始發布者**，不是聚合器 |
| 遵守 provider API 條款 | 只用 public REST endpoint、固定 UA、單一共用 client、🚫 不做高頻輪詢、🚫 不散布 bulk 原始回應 |
| 主辦方資料集使用 | CSV 標為 `public_market_data`；🚫 不得推定其上游交易所；只作為競賽用途 |
| 🚫 競賽 PDF / ZIP 不入庫 | `.gitignore` 已涵蓋；提交前 `git ls-files` 複查 |
| 🚫 秘密不得外洩 | `.env` 只在本機；`.env.example` 只放名稱；`run_config.json` 只記**存在布林值**；提交前跑 secret scan |
| AWS 憑證管理 | EC2 **instance role** 取得 Bedrock 權限；🚫 長效 access key 不進原始碼 / image layer / compose / artifact / 截圖 |
| log 中不得含敏感內容 | 只記 prompt **版本**；sanitize adapter 參數（去 token / authorization header / signed URL） |
| 誠實揭露 AI 工具使用 | 在 `docs/evidence/kiro/README.md` 誠實記錄 task→commit 與實際由誰產出 |
| 🚫 不提供投資建議 | Renderer 禁語 lint 為最後防線；UI 🚫 無交易控制項；報告與簡報都加免責語 |

### 8.3 發布閘門檢查表（提交前逐項打勾）

- [ ] `THIRD_PARTY_LICENSES` 已由釘死的 lock 產生並隨 image 打包。
- [ ] `git ls-files` 不含 `.env`、憑證、API token、競賽 PDF/ZIP、產生的 run artifact。
- [ ] Secret scan 通過（tracked files + 產生的 artifact 樣本）。
- [ ] `run_config.json` 樣本檢查：optional key 只有布林值，沒有任何 key 值。
- [ ] `execution_log.jsonl` 樣本檢查：只有 prompt 版本，沒有 prompt 全文、沒有 authorization。
- [ ] Docker image 內沒有 AWS 長效憑證；compose 檔沒有明文 secret。
- [ ] `content_reference` 抽樣檢查：都是短引文/指標，沒有整篇文章。
- [ ] 報告與 UI 抽樣檢查：禁語 lint 全過，無買賣/加減倉/配置用語，有免責聲明。
- [ ] H3 在 UI、簡報、文件三處都標示為**未實作**。
- [ ] `docs/evidence/kiro/README.md` 的 task→commit 對應與實際產出者誠實無誤。

---

## 9. 驗證（怎麼證明以上都成立）

**建置與環境**
```bash
uv python install 3.12 && uv venv --python 3.12 .venv
python -m pip install -e ".[dev]"
ruff check .
```

**橫切關注點（Evidence 可回溯性）**
```bash
# 邊界 lint（§6.5 四條）
python -m pytest tests/unit/evidence tests/unit/reporting -q
```
逐項人工確認：
- 隨機挑報告裡的一個市場數值 → 能在 `evidence.json` 找到對應 `evidence_id` 與該筆的
  `query_or_parameters`，且參數足以重算出同一個值。
- 挑一個 conclusion → 沿 `based_on_claim_ids` 一路回溯到 fact，且該 fact 有非 neutral 的 Link。
- 手動把 `evidence.json` 清空成零筆 → 仍產出四份 artifacts，且 `final_report.md` 是
  deterministic 的「資料不足」報告而非空白或崩潰。

**風險切片 A（Bronze）**
```bash
python -m pytest tests/integration/test_vertical_slice.py -q
streamlit run streamlit_app.py     # 斷網、無 AWS 憑證的環境
```
預期：UI 可提交 `rehearsal` run，四份檔案可下載，`run_id` 一致，模式標示為 rehearsal。

**風險切片 B（Bedrock）**
```powershell
$env:RUN_LIVE_TESTS = "1"
python -m pytest tests/live/test_bedrock_access.py -m live -vv -s
```
預期：一次成功的 Converse 結構化輸出；證據存進 `docs/evidence/`；
`docs/rehearsals/service-access-check.md` 記下時間戳/region/model ID/pass-fail（🚫 無憑證）。

**Deadline 行為**
```bash
python -m pytest tests/unit/orchestration tests/acceptance/test_deadline_budget.py -q
```
預期：以 fake clock 證明第 12 分鐘取消非必要外部呼叫、第 13 分鐘前完成 finalize，
且測試**不真的**等 45 秒。

**部署**
```bash
docker compose config
docker compose up -d && curl -f http://<host>:<port>/_stcore/health
python scripts/smoke_test.py
```

---

**下一步 →** [Architecture-FileMap.md](Architecture-FileMap.md)：把本文的 §4.1 佈局、§4.2 依賴規則與
§6 橫切設計**變成檔案級**——每個檔做什麼、與誰互動、現在存不存在。
