# Active Work — 誰正在做什麼

> **開工前先讀這一頁。** 目的只有一個：避免兩個人同時寫同一個檔案。
>
> 更新規則：認領工作時**在自己那一節**加一行，完成時把它移到「已完成並凍結」。
> 只改自己的區塊，不要重排別人的，這樣四條分支同時編輯也不會衝突。
>
> 最後更新：2026-08-01（晚：主幹狀態全面更新，S2 合併、1b 完成、S5 整合）

## 現況快照

| 項目 | 狀態 |
|---|---|
| `main` | ✅ **`f7536fb`（Add: AGENTS.md）**。44 個 `.py` 在 `src/hoya_agent/`，`pyproject.toml` 已存在 |
| 測試 | `main` 上 **501+ passed**，Python 3.12.13 離線實跑（2026-08-01） |
| 共享契約 `models.py` | ✅ **已存在於 `main`**，40 個 Pydantic class、1603 LOC。Task 1a（PR #6）+ Task 1b 均已合併 |
| Task 1b runtime seams | ✅ **已合併進 `main`**：`config.py`（155 LOC）、`clock.py`（41 LOC）、`ports.py`（137 LOC）、`tests/fakes.py`、`tests/conftest.py` |
| S2（Task 2 fixture 垂直切片） | ✅ **已合併進 `main`**（PR #12）：`application.py`、`reporting/artifacts.py`、`reporting/renderer.py`、fixture vertical slice |
| CSV Pipeline 增量 | ✅ **已在 `main`**：`orchestration/pipeline.py`（`OrganizerCsvPipeline`）— 離線四 artifact 產出 |
| S5 市場證據 data 層 | ✅ **已整合進 `main`**：`data/indicators.py`、`data/market_worker.py`、`data/market_series.py`、`data/regime.py`、`data/price_analysis.py` |
| Port adapters | ✅ **已在 `main`**：`adapters/port_adapters.py`（112 LOC） |
| 可執行的 Agent 程式碼 | `adapters/bedrock.py`、`reasoning/`、`evidence/{types,policies}.py` 都在 `main` 上 |
| Bedrock 實際呼叫 | ⚠️ **仍未驗證過任何一次**——這是目前最大的未爆彈 |
| ruff | ⚠️ 87 errors（76 在 `p2-etl-mvp/`，~10 在 `src/`/`tests/` 來自 PR #8 整合） |
| `tests/acceptance/`、`tests/live/` | ⚠️ **尚不存在**，Day 2 計劃建立 |

跑測試：

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit tests/contract tests/integration -q
ruff check .
```

## 原始碼樹現況（2026-08-01 晚；S2 + 1b + S5 合併後更新）

`main` 現在有 **44 個 `.py`** 在 `src/hoya_agent/` 底下，完整涵蓋：
- 核心契約與 runtime：`models.py`、`config.py`、`clock.py`、`ports.py`、`application.py`、`_provisional_seams.py`
- 資料層：`data/indicators.py`、`data/market_worker.py`、`data/market_series.py`、`data/regime.py`、`data/price_analysis.py`
- 證據層：`evidence/types.py`、`evidence/policies.py`、`evidence/processor.py`
- 推理層：`reasoning/planner.py`、`reasoning/research_agent.py`、`reasoning/arbiter.py`、`reasoning/prompt_library.py`、`reasoning/conflict_extension.py`
- 適配器：`adapters/bedrock.py`、`adapters/binance.py`、`adapters/organizer_csv.py`、`adapters/cryptopanic.py`、`adapters/alternative_me.py`、`adapters/rss.py`、`adapters/port_adapters.py`
- 報告層：`reporting/artifacts.py`、`reporting/renderer.py`
- 編排層：`orchestration/pipeline.py`

原本的 `p2-etl-mvp/` 平行目錄仍在 `feat/p2-report-integration` 分支上（48 個檔），
尚未完全清理，但 **核心功能已經以正確路徑存在於 `main`**。

| 分支 | `.py` 數 | 位置 | 合乎 `structure.md` canonical tree？ |
|---|---|---|---|
| `origin/main` | **44** | `src/hoya_agent/` | ✅ 501+ passed |
| `feat/p2-report-integration` | 48 | `p2-etl-mvp/` | ❌ 平行目錄（歷史參考） |
| `feat/p2-etl-data-evidence` | 47 | `p2-etl-mvp/` | ❌ 是 report-integration 的**子集**，可忽略 |

剩餘收斂工作：
- 清理 `p2-etl-mvp/` 中尚未搬入的非核心檔案（`coingecko.py`、`gpt_client.py` 等規格外項目）
- `tests/acceptance/` 與 `tests/live/` 目錄建立
- ruff 87 個 error 清理（76 個在 `p2-etl-mvp/`，可考慮直接刪除該目錄或加入 ruff exclude）

## 可用的設計輸入

開工前先看有沒有現成的設計文件，別重做別人算過的東西。

| 文件 | 內容 | 誰該讀 |
|---|---|---|
| `docs/price-data-analysis-outputs.html` | 只靠 OHLCV 能產出什麼：九個資訊類別 I1–I9、十個分析產出 A1–A10、欄位使用矩陣。數值以主辦方資料集**實算**（含五幣的 regime 標籤）。已驗證資料集 0 缺漏日、0 NaN、0 筆 OHLC 違反，因此**不需要缺口填補邏輯**；另發現每列 `open` 幾乎等於前列 `close`，`open` 不帶獨立資訊。 | 資料層、Task 11 |
| `docs/ai/P3_CONTRACT_EXPECTATIONS.md` | reasoning 層實際 import 的欄位名清單，全部溯源 `evidence-contracts.md` | P1（整合） |
| `docs/ai/P3_HANDOFF.md` | Task 6 完成範圍、兩個設計決定、明日待辦 | P1、P3 |

## 待裁決

- **`reasoning/arbiter.py` 的 `select_evidence()` 需加 per-asset 配額——但它是凍結路徑（2026-08-01 新增）。**
  雙幣比較已成為承諾能力（Requirement 17 / Task 12 / S9B）。實際讀過 `arbiter.py:82` 後確認：
  該函式**完全沒有資產概念**——先無上限收下**所有** high-reliability 項目，再收 conflict pair，
  最後才按 `independence_group` round-robin。而市場證據**全都是** `high`，
  所以雙幣 run 很可能在碰到任何新聞證據之前就用完 30 個名額，且不保證兩個資產各拿到多少。
  這是**正確性問題**，不是調參。
  **需要原 P3（該檔 owner）同意才能修**；在同意之前 🚫 不得逕行修改該檔。
  `asset=null` 的全市場項目不計入任一資產配額。

- **`data/analogs.py` 不在正式樹裡。** `price-data-analysis-outputs.html` 的 A7（歷史類比基準率）
  指名這個模組，但 `.kiro/steering/structure.md` 的 canonical tree 沒有它，而且該檔明文要求
  「不要為單一 helper 新增檔案」。二選一：併進 `data/indicators.py`，或修改 `structure.md`。
  不能兩邊各說各話。

- **A1 的 regime 標籤是以 `as_of 2026-05-31` 算的示範值**，比賽當天的 `analysis_as_of` 是當天。
  那些數字不得寫死進程式或報告。

## 已完成並凍結（不要修改）

改動這些路徑會默默弄壞別人已通過的測試。真的需要動，先找 owner。

| 路徑 | 內容 | Owner | 里程碑 |
|---|---|---|---|
| `src/hoya_agent/models.py` | 40 個 Pydantic domain model（1603 LOC），canonical 共享契約 | Task 1a+1b | PR #6 + corrective |
| `src/hoya_agent/config.py` | Typed Settings（155 LOC），env 解析、sanitized snapshot | Task 1b | 已合併 `main` |
| `src/hoya_agent/clock.py` | SystemClock + build_run_context（41 LOC） | Task 1b | 已合併 `main` |
| `src/hoya_agent/ports.py` | Protocol interfaces + StaticToolRegistry（137 LOC） | Task 1b | 已合併 `main` |
| `tests/fakes.py`、`tests/conftest.py` | 共用 test doubles：FixedClock、FakeLLM、FakeSourceAdapter 等 | Task 1b | 已合併 `main` |
| `src/hoya_agent/adapters/bedrock.py` | Bedrock Converse 邊界（強制 tool call、一次 repair、逾時 clamp、備援模型） | P3 | `task/6-bedrock-reasoning` |
| `src/hoya_agent/reasoning/` | Planner、Research Agent、Arbiter、H3 停用樁、prompt 載入器 | P3 | 同上 |
| `prompts/` | `planner-v1`、`research-extraction-v1`、`arbiter-v1` | P3 | 同上 |
| `tests/contract/`、`tests/unit/reasoning/` | reasoning 層測試 | P3 | 同上 |
| `src/hoya_agent/evidence/types.py` | FROZEN — provisional dataclass 暫替（field names 與 contracts 一致） | Gate | 已在 `main` |
| `src/hoya_agent/evidence/policies.py` | 靜態 reliability / independence group 政策 | Gate | 已在 `main` |
| `tests/unit/evidence/test_policies.py` | policies 測試 | Gate | 已在 `main` |
| `src/hoya_agent/application.py` | Single entry point、artifact ordering、terminal state | S2 / Task 2 | PR #12 |
| `src/hoya_agent/reporting/artifacts.py` | Atomic writes（tmp+fsync+replace）for 4 fixed files | S2 / Task 2 | PR #12 |
| `src/hoya_agent/reporting/renderer.py` | 繁中 11 段 deterministic renderer | S2 / Task 2 | PR #12 |
| `tests/fixtures/vertical_slice/` | S2 fixture pair | S2 / Task 2 | PR #12 |
| `tests/unit/reporting/` | Renderer 單元測試 | S2 / Task 2 | PR #12 |
| `tests/integration/test_vertical_slice.py` | 四項 artifact 整合測試 | S2 / Task 2 | PR #12 |
| `src/hoya_agent/_provisional_seams.py` | Task 1b seam 的暫時替身；**1b 已合併，待清除程序執行** | S2 / Task 2 | PR #12 |
| `tests/integration/test_s1_seam_bridge.py` | 橋接測試（1b seam 到位後用於驗證 field-name parity） | S2 / Task 2 | PR #12 |
| `src/hoya_agent/orchestration/pipeline.py` | OrganizerCsvPipeline — CSV-only 四 artifact 產出 | CSV Pipeline 增量 | 已在 `main` |
| `src/hoya_agent/data/indicators.py` | return, volatility, drawdown, volume z-score | S5 市場證據 | 已在 `main` |
| `src/hoya_agent/data/market_worker.py` | OHLCV bars → high-reliability EvidenceDrafts | S5 市場證據 | 已在 `main` |
| `src/hoya_agent/data/market_series.py` | bars_asof, merge_with_cutover（CSV/live cutover） | S5 市場證據 | 已在 `main` |
| `src/hoya_agent/data/regime.py` | Market state classification（first-match rule） | S5 市場證據 | 已在 `main` |
| `src/hoya_agent/data/price_analysis.py` | Cross-asset: anomaly, attribution, comparison | S5 市場證據 | 已在 `main` |
| `src/hoya_agent/adapters/port_adapters.py` | Port-conforming async wrappers（CSV, Binance, RSS） | Port 適配 | 已在 `main` |
| `src/hoya_agent/adapters/organizer_csv.py` | Competition OHLCV benchmark data adapter | Adapters | 已在 `main` |
| `src/hoya_agent/adapters/binance.py` | Daily UTC klines → MarketBar | Adapters | 已在 `main` |
| `src/hoya_agent/adapters/cryptopanic.py` | News aggregation（low reliability） | Adapters | 已在 `main` |
| `src/hoya_agent/adapters/alternative_me.py` | Fear & Greed（low, market-wide, asset=None） | Adapters | 已在 `main` |
| `src/hoya_agent/adapters/rss.py` | Original publisher feeds（medium reliability） | Adapters | 已在 `main` |

同樣的凍結清單也寫在 `.kiro/steering/work-in-progress.md`，所以 Kiro 每次執行都會知道。

## 進行中的認領

> **P1–P4 是舊的角色代號；現行分工以「四份平行任務」的專長切分為準。**
> 對照：`agent 用 Kiro → A`、`分析指標 → B`、`資訊整理 → C`、`UI → D`。
> 底下各節與「已完成並凍結」表裡的 P2／P3 標記保留為**歷史紀錄**——
> 指的是「誰寫了那批 code」，不是現在誰負責哪一份。

### Task 1 — 契約與 Runtime Seams：✅ 全部完成

- **Task 1a — 凍結規範性資料契約**：✅ 完成（`models.py` 40 classes、`pyproject.toml`、`tests/unit/test_models.py`）
- **Task 1b — 凍結執行期接縫**：✅ 完成（`config.py`、`clock.py`、`ports.py`、`tests/fakes.py`、`tests/conftest.py`）

### Task 2 — S2 Fixture 垂直切片：✅ 已合併（PR #12）

- `application.py`、`reporting/artifacts.py`、`reporting/renderer.py`
- `_provisional_seams.py`（待 swap 清除）
- 離線四 artifact 整合測試全綠

### Task 3 — Pipeline / Orchestration：🔶 部分完成

- `orchestration/pipeline.py`（`OrganizerCsvPipeline`）已在 `main`
- 尚缺：`DeadlineManager`、`deadline.py`、`run_state.py`、Market/Research fork-join 整合

### S5 — 市場證據 data 層：✅ 已整合

- `data/indicators.py`、`data/market_worker.py`、`data/market_series.py`、`data/regime.py`、`data/price_analysis.py`
- BTC run 可離線產出四 artifact（含四個 high-reliability market Evidence Items）

### 尚未開始或部分完成

| 任務 | 狀態 | 阻塞 |
|---|---|---|
| Task 3 fork-join / deadline | 🔶 Pipeline 增量在，缺 deadline + fork-join | 無 |
| `reporting/lint.py` | ❌ 未建立 | 無（renderer 已預留 hook） |
| `tests/acceptance/` | ❌ 目錄不存在 | Day 2 |
| `tests/live/` | ❌ 目錄不存在 | Day 2 |
| Bedrock 實際呼叫驗證 | ⚠️ 從未成功執行過 | 最高風險項 |
| Streamlit UI | ❌ 未開始 | 無 |
| Docker / EC2 部署 | ❌ 未開始 | Bedrock 驗證先 |
| `_provisional_seams.py` 清除 | 🔶 1b 已合併，可執行 swap 程序 | 無 |
| R16 Trust Scorecard | ❌ 未開始 | evidence layer 已就位 |
| R17 雙幣比較 | ❌ 未開始 | Arbiter per-asset 配額需先解決 |

### D — 呈現與交付（UI）

> **最高優先且不等任何人**：Bedrock 模型開通、確認模型 ID、**跑出專案史上第一次真實 Converse 呼叫**。

- 分支：`task/0-preflight-and-ui`
- 最高優先的一件事：**跑出專案史上第一次真實 Bedrock Converse 呼叫**（目前是零次）。
- 接著：Streamlit 骨架、`reporting/lint.py`、`Dockerfile` / `compose.yaml`。
- **可直接接手**：P2 已寫好 `p2-etl-mvp/render_report.py` 與 HTML 模板。
- **驗收**：一次成功的 Bedrock 呼叫證據進 `docs/evidence/`；`streamlit run` 能開起來；
  lint 對「買進／加倉／做多／配置」等詞全部攔下。

## 三條協調規則（不遵守一定會撞）

1. **一律從 `main` 開分支。** `main` 現在已有完整的 44 個 `.py` 檔案樹，不需要再從 `feat/p2-*` 拉檔案。
   新功能直接在 `main` 的基礎上開發。
2. **不要自建第二個 `pyproject.toml`。** `pyproject.toml` 已在 `main` 上，用標準方式安裝：

   ```bash
   python -m pip install -e ".[dev]"
   python -m pytest tests/unit tests/contract tests/integration -q
   ```
3. **`evidence/types.py`、`evidence/policies.py` 已凍結在 `main` 上，不要碰。**
   它們是契約性質的檔案，修改需要 owner 同意。

## 合流順序（剩餘工作）

1. `_provisional_seams.py` swap — 1b 已合併，可執行清除程序（`docs/ai/S2_CONTRACT_EXPECTATIONS.md` §4）
2. Task 3 fork-join + deadline — 在現有 `orchestration/pipeline.py` 上擴充
3. `reporting/lint.py` — 純字串比對，不依賴外部
4. Bedrock preflight — 最高風險項，做完才確認 H2-Lite 可跑
5. Streamlit UI + Docker + EC2 部署
6. `tests/acceptance/` 與 `tests/live/` — Day 2 freeze 前建立

## 已知的環境問題

- **Python 3.12（已解決，但每個人要各自做一次）。** 系統 Python 可能仍是 3.11.9，而
  `tech.md`／`pyproject.toml` 都要求 3.12。用 `uv` 一行解決，不必動系統 Python：

  ```bash
  uv python install 3.12
  uv venv --python 3.12 .venv
  ```

  已於 2026-08-01 在 3.12.13 上實跑：501+ passed。
- **ruff 87 errors**：76 在 `p2-etl-mvp/`（歷史殘留），~10 在 `src/`/`tests/`（PR #8 整合）。
  建議：將 `p2-etl-mvp/` 加入 ruff exclude 或直接刪除該目錄（其核心已搬入 `src/hoya_agent/`）。
- `feature/crypto-data-html` 分支的 `tests/` 佔用了 Agent 測試的保留路徑，合併時會撞。

## 2026-08-01 S8/S9/S9B integration branch

Branch `agent/s8-s9-s9b` owns the canonical seam swap, H2-Lite orchestration, deterministic Trust/Regime, and dual-asset report path. Frozen `reasoning/` and prompts were not changed. Offline smoke is green; full pytest/Ruff and live Silver are still explicit gates. See [implementation note](S8-S9-S9B-implementation.md).
