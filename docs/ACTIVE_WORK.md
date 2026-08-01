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

> **P1–P4 是舊的角色代號；現行分工以「四份平行任務」的專長切分為準。**
> 對照：`agent 用 Kiro → A`、`分析指標 → B`、`資訊整理 → C`、`UI → D`。
> 底下各節與「已完成並凍結」表裡的 P2／P3 標記保留為**歷史紀錄**——
> 指的是「誰寫了那批 code」，不是現在誰負責哪一份。

### P1（整合／發布）＝ agent 用 Kiro

> **現在的工作＝任務 A**，但**先做 gate**：把 `task/6-bedrock-reasoning` 合進 `main`，
> B 和 C 才能開工。細節見「四份平行任務」。

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
- **未認領的是「收斂」而非「重寫」**：把上述搬進 `src/hoya_agent/`。
- **這棵樹現在拆給兩個人**：`data/` 與行情 adapters → 任務 B（分析指標）；
  `evidence/` 與新聞社群 adapters → 任務 C（資訊整理）。兩人的協調規則見「四份平行任務」。
- 動手前務必先看這條分支，**不要重做已經寫好且測試通過的東西**。

### P3（推理／報告）

> `reasoning/` 的工作已依專長重新拆開：**LLM 邊界與去重併進任務 A**（agent 用 Kiro），
> **多事實抽取 `research_agent.py` 併進任務 C**（資訊整理），
> **`reporting/lint.py` 併進任務 D**（UI）。

- **Task 6 已完成**，待 gate 合併（分支 `task/6-bedrock-reasoning`）。
- 型別替換（`_stubs.py` → 真 `models.py`）留到 A 合併後。
  `renderer.py` 屬 Task 2，要等 Kiro 跑完。

### P4（UI／Demo／部署）＝ UI

> **現在的工作＝任務 D，而且排在全隊最前面。** 不是因為它擋人，是因為它若失敗，
> 其他三份全部白做——Bedrock 到今天為止一次都沒有真的呼叫過。它也不需要等 gate。

- 分支：`task/0-preflight-and-ui`
- 最高優先的一件事：**跑出專案史上第一次真實 Bedrock Converse 呼叫**（目前是零次）。
- 可直接接手 P2 已寫好的 `render_report.py` 與 HTML 模板，不必從零開始。

## 四份平行任務（2026-08-01 重新分配）

> 先前的排程讓三個人同時卡在 `models.py`。以下重新切成**四份路徑互不重疊的任務**，
> 四個人可以同時動工。關鍵在於把「搬檔案」和「換型別」拆開——
> 搬移與 import 改寫**不需要** `models.py`，只有最後的型別替換需要。
>
> **開工順序不是照依賴排的，是照風險排的。** Bedrock 到今天為止一次都沒有真的呼叫過；
> 若模型開通沒過或 model ID 不對，整個 H2-Lite 架構是死的，A／B／C 做得再好都沒用。
> 所以 **D 的 Bedrock preflight 排在所有事情前面**，而且它剛好不需要等任何人。

### 唯一的 gate（約 30–60 分鐘，做完就解鎖 B 和 C）

**「agent 用 Kiro」的人先把 `task/6-bedrock-reasoning` 合併進 `main`。**
它已測過（134 passed + 15 subtests）、路徑合乎 `structure.md`、不需修改。
合併後 `main` 第一次有一棵真的樹，B 和 C 才有目標可搬。
合併時唯一會撞的是 `src/hoya_agent/__init__.py` 與 `adapters/__init__.py`，兩個都是空殼。

**D（UI）不受這個 gate 影響，現在就能開工。**

### 四份任務與路徑佔用（依四人專長切分，互不重疊，可同時 commit）

分工依據是四個人實際的專長：**UI／資訊整理／agent 用 Kiro／分析指標**。
P2 現有那 48 個檔照這個切法會自然裂成兩半——`data/` 與行情 adapters 屬分析指標，
`evidence/` 與新聞社群 adapters 屬資訊整理。已確認**沒有跨界共用檔案**
（`_assets.py` 只被 reddit／rss 用，`text_clean.py` 只被 research 抽取用）。

| 專長 | 任務 | 分支 | 獨佔路徑 |
|---|---|---|---|
| **agent 用 Kiro** | A 契約與骨幹 | `task/1a-contracts-core` | `pyproject.toml`、`models.py`、`config.py`、`clock.py`、`ports.py`、`orchestration/`、`reasoning/`（除 `research_agent.py`）、所有 `__init__.py` |
| **分析指標** | B 市場數據層 | `task/4-market-data-layer` | `data/`、`adapters/{organizer_csv,binance,okx}.py`、`tests/unit/data/` |
| **資訊整理** | C 證據與敘事層 | `task/5-evidence-layer` | `evidence/`、`adapters/{_assets,cryptopanic,reddit,rss,alternative_me}.py`、`reasoning/research_agent.py`、`tests/unit/evidence/` |
| **UI** | D 呈現與交付 | `task/0-preflight-and-ui` | `streamlit_app.py`、`ui/`、`reporting/`、`scripts/`、`Dockerfile`、`compose.yaml`、`docs/evidence/` |

**A — 契約與骨幹（agent 用 Kiro）**
> 一句話：用 Kiro 把全隊共用的型別凍結下來，並讓 `main` 從零個 `.py` 變成一棵裝得起來的樹。

先做 gate（見上），再用 Kiro 依 `docs/ai/KIRO_TASK_1A_PROMPT.md` 跑 Task 1a，產出
`pyproject.toml`（依賴至少含 `httpx`、`pydantic`、`boto3`、`pytest`、`ruff`）與凍結版 `models.py`。
接著收斂 LLM 邊界：留 `adapters/bedrock.py`，刪 `gpt_client.py`、`run_gpt_extract.py`，
修掉 `llm_client.py` 裡 `AnthropicBedrockMantle` 那段錯誤 docstring。
**驗收**：`uv venv --python 3.12 .venv` + `pip install -e ".[dev]"` 成功，`test_models.py` 全綠，
`reasoning/` 只剩一套 LLM 邊界。

**B — 市場數據層（分析指標）**
> 一句話：把 OHLCV 變成可回溯的數字——指標計算、market regime 判定、量化 invalidation 門檻。

`p2-etl-mvp/data/`（indicators、market_series、market_worker、price_analysis、regime）與
`adapters/{organizer_csv,binance,okx}.py` 搬進 `src/hoya_agent/`，import 從頂層平面式改成
`from hoya_agent.data.x import ...`，測試分流進 `tests/unit/data/` 與 `tests/contract/`。
**先不動型別**——`data/types.py` 原地保留，等 A 合併後另開一輪機械替換。
延伸工作：R16 創意層的 **Market Regime** 與 **量化 invalidation 門檻**本來就屬這一層。
設計輸入看 `docs/price-data-analysis-outputs.html`（A1–A10 已用主辦方資料集實算過）。
**驗收**：既有測試在新路徑上原封不動全綠。

**C — 證據與敘事層（資訊整理）**
> 一句話：把新聞社群的雜訊變成無立場、可查證的證據——來源可信度、去重與獨立性、多事實抽取、Trust Scorecard。

`p2-etl-mvp/evidence/`（policies、processor）、`adapters/{_assets,cryptopanic,reddit,rss,alternative_me}.py`、
`data/text_clean.py`（搬到 `evidence/text_clean.py`，canonical `data/` 只放市場序列與指標）搬進套件樹。
刪 `adapters/coingecko.py`（steering 已定 MVP 不實作）。
把 `research_extractor.py` 的 relevance filtering 與多事實拆解併進 `reasoning/research_agent.py`，
改成依賴 A 的 `bedrock.py` 而非自有 `LLMClient` Protocol。
延伸工作：R16 創意層的 **Trust Scorecard**（`evidence/trust.py`）本來就屬這一層。
**驗收**：既有測試在新路徑上全綠；一篇文章能拆出多個 EvidenceDraft。

**D — 呈現與交付（UI）**
> 一句話：讓評審看得到也跑得動——Streamlit 三模式介面、繁中報告渲染、投資建議 lint、Docker 與 demo。

**最高優先且不等任何人**：Bedrock 模型開通、確認模型 ID、**跑出專案史上第一次真實 Converse 呼叫**
（目前是零次；若這件事失敗，A／B／C 三份全部白做，所以它排在所有事情前面）。
接著 Streamlit 骨架先接假資料跑通三種 run mode 的標示，寫 `reporting/lint.py`
（純字串比對，不依賴 `models.py`），再補 `Dockerfile` / `compose.yaml`。
**可直接接手**：P2 已寫好 `p2-etl-mvp/render_report.py` 與 HTML 模板，並產出過
`render/out/hoya-report-BTC.html`，不必從零開始。
**驗收**：一次成功的 Bedrock 呼叫證據進 `docs/evidence/`；`streamlit run` 能開起來；
lint 對「買進／加倉／做多／配置」等詞全部攔下。

### 兩條協調規則（不遵守一定會撞）

1. **`p2-etl-mvp/` 誰都不要刪。** B 和 C 會同時掏空這個目錄（B 拿 `data/` 與行情 adapters，
   C 拿 `evidence/` 與新聞 adapters）。任何一方順手 `git rm -r p2-etl-mvp/`，另一方 rebase 就會炸開。
   **兩人都只用 `git mv`，目錄本身留著，最後由 A 在合流時清掉。**
2. **A 落地前，B 和 C 不要自己建 `pyproject.toml`。** 那是 A 的獨佔路徑，自己建等於開出第三棵樹。
   要跑測試就用臨時 venv：

   ```bash
   uv venv --python 3.12 .venv
   uv pip install --python .venv/Scripts/python.exe httpx pydantic boto3 pytest
   PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests -q
   ```

### 合流順序（四份做完之後）

1. A 先合 → `models.py` 與 `pyproject.toml` 進 `main`
2. B、C 各自 rebase 到 A 之上，做型別替換（P2 的 provisional dataclass 欄位名刻意與契約一致，是機械式取代）
3. D 最後把 UI 從假資料接到真資料
4. 然後才是 Task 2 fixture 垂直切片與 Task 3 編排
   （R16 創意層已分進 B 和 C，不再是孤兒任務）

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
