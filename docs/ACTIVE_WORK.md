# Active Work — 誰正在做什麼

> **開工前先讀這一頁。** 目的只有一個：避免兩個人同時寫同一個檔案。
>
> 更新規則：認領工作時**在自己那一節**加一行，完成時把它移到「已完成並凍結」。
> 只改自己的區塊，不要重排別人的，這樣四條分支同時編輯也不會衝突。
>
> 最後更新：2026-08-01（下午：原始碼樹實掃 + Python 3.12 驗證）

## 現況快照

| 項目 | 狀態 |
|---|---|
| `main` | 規格、steering、官方資料集、docs 齊全，但**零個 `.py`、沒有 `pyproject.toml`**——clone 下來裝不起來也跑不了 |
| 可執行的 Agent 程式碼 | 全部在未合併分支，且分屬**兩棵不相容的樹**（見下節） |
| 共享契約 `models.py` | **尚不存在——這是目前的頭號阻塞** |
| 測試 | Task 6：134 passed + 15 subtests；P2：122 passed。兩邊都在 Python 3.12 離線實跑通過（2026-08-01 驗證） |
| Bedrock 實際呼叫 | **尚未驗證過任何一次** |

## 原始碼樹現況（2026-08-01 實掃所有分支）

**這是目前最大的結構性問題：同一個專案有兩棵互不相容的 Python 樹，而 `main` 上一棵都沒有。**

| 分支 | `.py` 數 | 位置 | 合乎 `structure.md` canonical tree？ |
|---|---|---|---|
| `origin/main` | **0** | — | 連 `pyproject.toml` 都沒有 |
| `task/6-bedrock-reasoning` | 18（9 src + 9 test） | `src/hoya_agent/` | ✅ 唯一合乎，**尚未合併** |
| `feat/p2-report-integration` | 48 | `p2-etl-mvp/` | ❌ 平行目錄，自帶 `pyproject.toml` |
| `feat/p2-etl-data-evidence` | 47 | `p2-etl-mvp/` | ❌ 是 report-integration 的**子集**，可忽略 |
| `price`、`task/7-html-report-template` | 0 | — | 只有 docs |
| `analysis/dataset-eda` | 1 | 單一 script | — |

收斂 `p2-etl-mvp/` → `src/hoya_agent/` 時要處理的實際工作：
- **48 個檔的 import 全要改寫**。P2 用頂層平面式（`from data.indicators import ...`、`from evidence.types import ...`）配合 `pythonpath = ["."]`，搬進套件樹就全斷。
- 兩個 `pyproject.toml` 併一（P2 的叫 `hoya-etl-mvp`，且**未宣告任何依賴**——實際需要 `httpx`、`pytest`、`openai`）。
- 兩個 `tests/` 目錄合併（P2 是扁平 `p2-etl-mvp/tests/`，canonical 是 `tests/unit|contract|integration`）。
- 型別對齊：P2 的 `data/types.py`、`evidence/types.py` 是 **provisional frozen dataclass**，檔頭已註明「`models.py` 落地後照樣搬，欄位名刻意保持一致」。所以這步是機械式的，不是重寫——但**得等 `models.py` 先定案**。
- 順手清掉規格外的東西：`reasoning/gpt_client.py`、`run_gpt_extract.py`（規格是 Bedrock-only）、`adapters/coingecko.py`（steering 已定為 MVP 不實作）。

## 可用的設計輸入

開工前先看有沒有現成的設計文件，別重做別人算過的東西。

| 文件 | 內容 | 誰該讀 |
|---|---|---|
| `docs/price-data-analysis-outputs.html` | 只靠 OHLCV 能產出什麼：九個資訊類別 I1–I9、十個分析產出 A1–A10、欄位使用矩陣。數值以主辦方資料集**實算**（含五幣的 regime 標籤）。已驗證資料集 0 缺漏日、0 NaN、0 筆 OHLC 違反，因此**不需要缺口填補邏輯**；另發現每列 `open` 幾乎等於前列 `close`，`open` 不帶獨立資訊。 | P2（Task 4）、Task 11 |
| `docs/ai/P3_CONTRACT_EXPECTATIONS.md` | reasoning 層實際 import 的欄位名清單，全部溯源 `evidence-contracts.md` | P1（Task 1a／1b） |
| `docs/ai/P3_HANDOFF.md` | Task 6 完成範圍、兩個設計決定、明日待辦 | P1、P3 |

## 待 P1 裁決

- **P2 與 P3 各寫了一套 LLM 邊界與研究抽取（最嚴重的一條，2026-08-01 發現）。**
  兩邊都建了 `reasoning/`，且都實作了同樣兩個接縫：

  | 職責 | P2 的版本 | P3 的版本 |
  |---|---|---|
  | LLM 邊界 | `reasoning/llm_client.py`（Protocol）+ `gpt_client.py` | `adapters/bedrock.py`（boto3 Converse、逾時 clamp、schema repair、備援模型） |
  | 研究抽取 | `reasoning/research_extractor.py` | `reasoning/research_agent.py` |

  兩邊都有測試、都會通，收斂時會落進同一個 `src/hoya_agent/reasoning/`。**建議裁決：**
  - **LLM 邊界留 P3 的 `bedrock.py`** — 它有逾時 clamp、一次 repair、備援模型，合乎鐵則 8 與 11；
    P2 的 `LLMClient` 只有 `complete()`。P2 版本降為測試用 fake 或直接刪除。
  - **研究抽取留 P2 的 `research_extractor.py`** — 它做了 relevance filtering 與多事實拆解
    （一篇文章 → 多個 EvidenceDraft），比 P3 版本完整；但要改成依賴 `bedrock.py` 而非自有 Protocol。
  - 附帶必修：`llm_client.py` docstring 教人用 `AnthropicBedrockMantle`，**這個類別不存在**
    （Anthropic SDK 是 `AnthropicBedrock`），且 P3 已走 boto3 Converse。照抄會直接爆。
- **`data/analogs.py` 不在正式樹裡。** `price-data-analysis-outputs.html` 的 A7（歷史類比基準率）
  指名這個模組，但 `.kiro/steering/structure.md` 的 canonical tree 沒有它，而且該檔明文要求
  「不要為單一 helper 新增檔案」。二選一：併進 `data/indicators.py`，或修改 `structure.md`。
  不能兩邊各說各話。
- **A1 的 regime 標籤是以 `as_of 2026-05-31` 算的示範值**，比賽當天的 `analysis_as_of` 是當天。
  那些數字不得寫死進程式或報告。

## 已完成並凍結（不要修改）

改動這些路徑會默默弄壞別人已通過的測試。真的需要動，先找 owner。

| 路徑 | 內容 | Owner | 分支 |
|---|---|---|---|
| `src/hoya_agent/adapters/bedrock.py` | Bedrock Converse 邊界（強制 tool call、一次 repair、逾時 clamp、備援模型） | P3 | `task/6-bedrock-reasoning` |
| `src/hoya_agent/reasoning/` | Planner、Research Agent、Arbiter、H3 停用樁、prompt 載入器 | P3 | 同上 |
| `prompts/` | `planner-v1`、`research-extraction-v1`、`arbiter-v1` | P3 | 同上 |
| `tests/contract/`、`tests/unit/reasoning/` | 上述的測試 | P3 | 同上 |

同樣的清單也寫在 `.kiro/steering/work-in-progress.md`，所以 Kiro 每次執行都會知道。

## 進行中的認領

### P1（整合／發布）

> **現在的工作＝任務 A**，但**先做 gate**：把 `task/6-bedrock-reasoning` 合進 `main`，
> 其他三人才能開工。細節見「四份平行任務」。

- **Task 1a — 凍結規範性資料契約**（`pyproject.toml`、`models.py`、`tests/unit/test_models.py`）
  - 分支：`task/1a-contracts-core`
  - 工具：**Kiro**，從 spec 原生執行 Task 1a
  - 佔用路徑：`src/hoya_agent/models.py`、`pyproject.toml`、`tests/unit/test_models.py`
  - **這是全隊的阻塞點。** 完成前 P2 和 P4 都無法寫真正的實作。
  - 完成後立刻做 `docs/ai/P3_HANDOFF.md` §5 的契約驗收（約 15 分鐘）
- **Task 1b — 凍結執行期接縫**（`config.py`、`clock.py`、`ports.py`、`tests/fakes.py`）
  - 分支：`task/1b-runtime-seams`，等 1a 合併後開
  - 工具：Kiro

### P2（資料／證據）

- **已有大量產出，不是「尚未認領」**（此處先前記載錯誤，2026-08-01 更正）。
  分支 `feat/p2-report-integration`（48 個 `.py`，122 passed on 3.12）已涵蓋：
  - `adapters/`：organizer_csv、binance、okx、cryptopanic、reddit、rss、alternative_me（+ 規格外的 coingecko）
  - `data/`：indicators、market_series、market_worker、price_analysis、regime、text_clean
  - `evidence/`：policies（reliability 靜態表）、processor、types
  - `render_report.py` + HTML 模板（已產出 `render/out/hoya-report-BTC.html`）
- **未認領的是「收斂」而非「重寫」**：把上述搬進 `src/hoya_agent/`。等 `models.py`。
- 動手前務必先看這條分支，**不要重做已經寫好且測試通過的東西**。

### P3（推理／報告）

> **現在的工作＝任務 C**（推理層去重 + `reporting/lint.py`）。等 P1 的 gate 合併完就能開工，
> **不必等 `models.py`**——lint 是純字串比對，去重動的是既有檔案。

- **Task 6 已完成**，待 P1 審核合併（分支 `task/6-bedrock-reasoning`）。
- 型別替換（`_stubs.py` → 真 `models.py`）與 Bedrock live 冒煙留到 A 合併後。
  `renderer.py` 屬 Task 2，要等 Kiro 跑完。

### P4（UI／Demo／部署）

> **現在的工作＝任務 D**。**四個人裡唯一連 gate 都不用等的**——不碰 `src/hoya_agent/`，
> 現在就能開工，而且 Bedrock 模型開通有前置時間，越早越好。

- 分支：`task/0-service-preflight`
- 最高優先的一件事：**跑出專案史上第一次真實 Bedrock Converse 呼叫**（目前是零次）。

## 四份平行任務（2026-08-01 重新分配）

> 先前的排程讓三個人同時卡在 `models.py`。以下重新切成**四份路徑互不重疊的任務**，
> 四個人可以同時動工。關鍵在於把「搬檔案」和「換型別」拆開——
> 搬移與 import 改寫**不需要** `models.py`，只有最後的型別替換需要。

### 唯一的 gate（約 30–60 分鐘，做完四份就全部解鎖）

**P1 先把 `task/6-bedrock-reasoning` 合併進 `main`。** 它已測過（134 passed + 15 subtests）、
路徑合乎 `structure.md`、不需修改。合併後 `main` 第一次有一棵真的樹，其餘三人才有目標可搬。
合併時唯一會撞的是 `src/hoya_agent/__init__.py` 與 `adapters/__init__.py`，兩個都是空殼。

### 四份任務與路徑佔用（互不重疊，可同時 commit）

| | 任務 | 分支 | 獨佔路徑 |
|---|---|---|---|
| **A／P1** | 地基與契約 | `task/1a-contracts-core` | `pyproject.toml`、`src/hoya_agent/models.py`、`tests/unit/test_models.py` |
| **B／P2** | 資料層搬家 | `task/4-data-layer-move` | `src/hoya_agent/{adapters（除 bedrock.py）,data,evidence}/`、`tests/unit/{data,evidence}/`、`tests/contract/adapters/` |
| **C／P3** | 推理層去重 + 報告 lint | `task/6b-reasoning-consolidation` | `src/hoya_agent/reasoning/`、`src/hoya_agent/reporting/lint.py` |
| **D／P4** | AWS preflight + UI 骨架 | `task/0-service-preflight` | `scripts/`、`streamlit_app.py`、`Dockerfile`、`compose.yaml`、`docs/evidence/` |

**A — 地基與契約（P1）**
用 Kiro 依 `docs/ai/KIRO_TASK_1A_PROMPT.md` 跑 Task 1a，產出 `pyproject.toml`（含依賴：
`httpx`、`pydantic`、`boto3`、`pytest`、`ruff`）與凍結版 `models.py`。
**驗收**：`uv venv --python 3.12 .venv` + `pip install -e ".[dev]"` 成功，`test_models.py` 全綠。

**B — 資料層搬家（P2）**
`p2-etl-mvp/{adapters,data,evidence}` → `src/hoya_agent/`，import 從頂層平面式改成
`from hoya_agent.data.x import ...`，扁平 `tests/` 分流進 `tests/unit/` 與 `tests/contract/`，
刪 `adapters/coingecko.py`（steering 已定 MVP 不實作），`pyproject.toml` 的依賴交給 A。
**先不動型別**——`data/types.py`、`evidence/types.py` 原地保留，等 A 合併後另開一輪機械替換。
**驗收**：122 個測試在新路徑上原封不動全綠。

**C — 推理層去重 + 報告 lint（P3）**
依「待 P1 裁決」第一條收斂：LLM 邊界留 `adapters/bedrock.py`，把 P2 的
`research_extractor.py`（多事實抽取）併進 `reasoning/`，改成依賴 `bedrock.py`；
刪 `gpt_client.py`、`run_gpt_extract.py`；修掉 `AnthropicBedrockMantle` 那段錯誤 docstring。
接著寫 `reporting/lint.py`（純字串比對，不依賴 `models.py`）。
**驗收**：reasoning 只剩一套 LLM 邊界；lint 對「買進／加倉／做多」等詞全部攔下。

**D — AWS preflight + UI 骨架（P4）**
Task 0：Bedrock 模型開通、確認模型 ID、**跑出專案史上第一次真實 Converse 呼叫**（目前是零次，
這是目前最大的未驗證風險）。接著 Streamlit 骨架先接假資料跑通三種 run mode 的標示，
再補 `Dockerfile` / `compose.yaml`。全程不碰 `src/hoya_agent/` 的核心模組。
**驗收**：一次成功的 Bedrock 呼叫截圖進 `docs/evidence/`；`streamlit run` 能開起來。

### 合流順序（四份做完之後）

1. A 先合 → `models.py` 進 `main`
2. B、C 各自 rebase 到 A 之上，做型別替換（P2 的 provisional dataclass 欄位名刻意與契約一致，是機械式取代）
3. D 最後接真資料
4. 然後才是 Task 2 fixture 垂直切片、Task 3 編排、Task 11 創意層
   （註：Task 11 的 `data/regime.py`、`evidence/policies.py` P2 已寫過，先看過再動手）

## 已知的環境問題

- **Python 3.12（已解決，但每個人要各自做一次）。** 系統 Python 可能仍是 3.11.9，而
  `tech.md`／P2 的 `pyproject.toml` 都要求 3.12。用 `uv` 一行解決，不必動系統 Python：

  ```bash
  uv python install 3.12
  uv venv --python 3.12 .venv
  ```

  已於 2026-08-01 在 3.12.13 上實跑：Task 6 樹 134 passed + 15 subtests、P2 樹 122 passed。
- `feature/crypto-data-html` 分支的 `tests/` 佔用了 Agent 測試的保留路徑，合併時會撞。
- ~~遠端 `feat/p2-*` 等分支都沒有 Python 原始碼樹~~ ——**此說法已作廢（2026-08-01）**。
  `feat/p2-*` 有 47–48 個 `.py`，只是位在 `p2-etl-mvp/` 而非 `src/`。照舊說法認領會重工。
  真的沒有 Python 樹的只有 `price`、`task/7-html-report-template`、`analysis/dataset-eda`。
