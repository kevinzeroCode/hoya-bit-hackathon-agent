# Kiro 執行指引 — Task 1a：凍結規範性資料契約

> Task 1a 現在是 `.kiro/specs/hoya-market-agent/tasks.md` 裡的**正式任務**，
> 所以優先走 Kiro 原生的 spec 執行流程，而不是貼一大段聊天 prompt。
>
> 原本那份長 prompt 的內容已經拆進兩個地方：任務範圍與 checklist 進了 `tasks.md`、
> 跨 session 的約束進了 `.kiro/steering/work-in-progress.md`。兩者都會自動載入。

## 執行前置

1. **先備妥 Python 3.12。** `tech.md` 鎖定 3.12，Kiro 會照著寫 `requires-python = ">=3.12"`；
   系統 Python 若仍是 3.11.9，`pip install -e ".[dev]"` 會直接失敗，Kiro 的 TDD 驗證步驟
   就跑不完，等於產出無法驗證。

   **已於 2026-08-01 解決（用 `uv`，不必動系統 Python）**——每台機器各跑一次：

   ```bash
   uv python install 3.12          # 已驗證：cpython-3.12.13
   uv venv --python 3.12 .venv
   .venv/Scripts/python.exe -V     # 應顯示 3.12.x
   ```

   同日已在 3.12.13 上實跑兩棵現有的樹：`task/6-bedrock-reasoning` 134 passed + 15 subtests、
   `feat/p2-report-integration` 122 passed。所以 3.12 不再是未知數，`tech.md` 也不需要放寬到 3.11。
   **不要**讓 Kiro 寫 3.12 然後跳過驗證步驟——那會產出一批沒跑過測試的契約。
2. 從最新的 `main` 開分支：

   ```bash
   git checkout main && git pull
   git checkout -b task/1a-contracts-core
   ```

3. 在 **repo 根目錄**開啟 Kiro（不要開在 `.kiro/`，否則它看不到 `src/` 與 `tests/`）。
4. 在 `docs/ACTIVE_WORK.md` 的 P1 區塊確認這項工作沒有人同時在做。

## 主要路徑：讓 Kiro 原生執行 spec task

1. 在 Kiro 側邊欄開啟 `hoya-market-agent` spec。
2. 找到 **Task 1a. Freeze the normative data contracts**，執行該項任務（只點這一項，
   **不要按 Run all Tasks**）。
3. 執行模式選**逐步審核**而非全自動。`models.py` 是全 repo 錯誤半徑最大的檔案，
   四個人都 import 它，值得逐檔看過再放行。

Kiro 會自動載入七份 `inclusion: always` 的 steering 檔案，以及該 task 底下的 checklist
作為執行計畫。你**不需要**再貼任何範圍說明、欄位清單或禁止事項。

如果需要補一句話讓它更聚焦，這樣就夠了：

```text
執行 spec 中的 Task 1a。欄位名與驗證規則一律以 .kiro/steering/evidence-contracts.md
為唯一權威，不得自行命名或簡化。docs/ai/P3_CONTRACT_EXPECTATIONS.md 是下游已寫好的
消費端需求，請盡量滿足；若與 evidence-contracts.md 衝突，以 evidence-contracts.md 為準。
先寫會失敗的測試，跑到確認失敗，再實作。
```

## 備用路徑：用 CLI 下指令

Kiro 有 `chat` 子指令（已在本機驗證，v0.12.333）：

```
kiro chat [options] [prompt]
  -m --mode <mode>      ask | edit | agent | 自訂 mode，預設 agent
  -a --add-file <path>  把檔案釘進 context
  -r --reuse-window / -n --new-window
```

它**不是 headless**——會開／重用 Kiro 視窗，不會把結果印回終端。好處是指令可重現、
可以寫進文件讓四個人跑一模一樣的東西，而且照樣產生可截圖的 session。

先在專案根目錄執行唯讀的前置檢查（`ask` 模式不會動檔案）：

```powershell
kiro chat -m ask "在開始寫任何檔案之前先回答三題：1. 你目前載入了哪些 steering 檔案？2. Task 1a 要建立哪幾個檔案？3. 有哪些路徑是你不得修改的？"
```

答不出七份 steering、或講不出「不得修改 `src/hoya_agent/reasoning/`」，就代表 steering
沒載入。**先別讓它動手**，回頭查 frontmatter。

確認後再執行：

```powershell
kiro chat -m agent -a .kiro/specs/hoya-market-agent/tasks.md -a docs/ai/P3_CONTRACT_EXPECTATIONS.md "執行 spec 中的 Task 1a。欄位名與驗證規則一律以 .kiro/steering/evidence-contracts.md 為唯一權威。先寫會失敗的測試，跑到確認失敗，再實作。不要動 Task 1b 與 Task 2 的檔案。"
```

## 執行中要盯的四件事

逐步審核模式的價值在於你真的會看。重點看這四個：

1. **它有沒有先寫測試再實作。** 如果第一個產出就是 `models.py`，它跳過了 TDD——叫停，
   要求先補測試。
2. **欄位名對不對。** 隨機抽三個對照 `evidence-contracts.md`：`source_name`（不是 `source`）、
   `independence_group`、`content_reference`。錯一個就全錯，因為四個人都會照著寫。
3. **`EvidenceItem` 有沒有混進 stance 欄位。** 這是規範最強調的一條，也是最容易被
   「這樣比較方便」的直覺破壞的一條。
4. **它有沒有去碰凍結路徑。** 只要看到 `src/hoya_agent/reasoning/` 或 `tests/contract/`
   出現在 diff 裡，立刻停。

## 完成後立刻做的契約驗收（約 15 分鐘）

這一步是拆分策略的主要價值，不要跳過。

1. 打開 `tests/unit/reasoning/_stubs.py`，把 `Evidence`、`Claim`、`Link`、`Invalidation`、
   `Result`、`Indicator`、`Ledger` 這幾個替身類別改成從 `hoya_agent.models` import。
   `FakeLLM`、`FakeRegistry`、`Record`、`Plan`、`Draft` 這些測試用假件保留不動。
2. 跑 `python -m pytest tests/unit tests/contract -q`。
3. 失敗的地方就是 Kiro 產出與 P3 既有程式碼的契約落差。**以 Kiro 產出為準去修 P3**，
   不是反過來。
4. 把修正後的結論寫進 `.kiro/steering/work-in-progress.md` 的「已定案的規格歧義」一節，
   下一個 session 就不會再爭論一次。

那 134 個測試已經把契約行為寫成可執行斷言（Evidence 不得帶 stance、Link 只收三種 stance、
Claim 依賴圖不得有環、信心上限怎麼套），等於用現成資產替最高風險的產出做即時驗收。

## 收尾

- 只勾選 Task 1a 底下實際完成的子項目。**不要**勾 Task 1 的父層 checkbox（1b 還沒做）。
- 在 `docs/ACTIVE_WORK.md` 把這項從「進行中」移到「已完成並凍結」。
- 把「任務編號／分支／驗證指令與結果／commit SHA／Kiro session 摘要」送給 P1，
  由 P1 統一更新 `docs/evidence/kiro/README.md`（依 `development-workflow.md`，
  不要自己改那個檔，否則四條分支會撞在一起）。

## 順手留下 Kiro 使用證據（關係到 +10%）

命題文件的加分項是「採用 AWS Kiro 作為 AI 整合開發環境之工具」，而
`docs/evidence/kiro/README.md` 的檢核表要的是可查證的痕跡。執行 Task 1a 時順手抓這幾樣，
比事後補容易得多：

- spec 側邊欄顯示 requirements／design／tasks 三段式結構的截圖；
- Task 1a 執行中的畫面，看得到它把 checklist 當成執行計畫逐項推進；
- 逐步審核模式下的 diff 審核畫面；
- 執行完成後 `tasks.md` 的 checkbox 被勾起來的樣子。

截圖不得出現 `.env` 內容、AWS 憑證或任何 API key。

值得在簡報中講的一點：這個專案的 steering 不只是塞背景知識，而是**分工邊界的執行機制**——
`structure.md` 定義模組依賴方向與檔案歸屬，`work-in-progress.md` 記錄哪些路徑已完成凍結，
所以四個人平行開發時，Kiro 不會去改別人已通過測試的程式碼。這比「我們有用 Kiro 生程式碼」
具體得多。
