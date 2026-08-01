# Kiro 執行指引 — Task 1a：凍結規範性資料契約

> Task 1a 現在是 `.kiro/specs/hoya-market-agent/tasks.md` 裡的**正式任務**，
> 所以優先走 Kiro 原生的 spec 執行流程，而不是貼一大段聊天 prompt。
>
> 原本那份長 prompt 的內容已經拆進兩個地方：任務範圍與 checklist 進了 `tasks.md`、
> 跨 session 的約束進了 `.kiro/steering/work-in-progress.md`。兩者都會自動載入。

## 執行前置

1. **確認本機有 Python 3.12。** `tech.md` 鎖定 3.12，本機目前是 3.11.9。
   沒裝的話 Task 1a 最後的 `pip install -e ".[dev]"` 與測試步驟會失敗。
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
