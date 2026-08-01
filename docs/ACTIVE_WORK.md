# Active Work — 誰正在做什麼

> **開工前先讀這一頁。** 目的只有一個：避免兩個人同時寫同一個檔案。
>
> 更新規則：認領工作時**在自己那一節**加一行，完成時把它移到「已完成並凍結」。
> 只改自己的區塊，不要重排別人的，這樣四條分支同時編輯也不會衝突。
>
> 最後更新：2026-08-01

## 現況快照

| 項目 | 狀態 |
|---|---|
| `main` | 已含完整規格、steering、官方資料集、Task 6 尚未合併 |
| 可執行的 Agent 程式碼 | 只有 `src/hoya_agent/adapters/bedrock.py` 與 `src/hoya_agent/reasoning/` |
| 共享契約 `models.py` | **尚不存在——這是目前的頭號阻塞** |
| 測試 | 134 passed（Task 6 範圍），`ruff check` 乾淨 |
| Bedrock 實際呼叫 | **尚未驗證過任何一次** |

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

- 尚未認領。Task 1a 落地前可先做的事：讀 `evidence-contracts.md` §3–§6、
  `HOYA_BIT_crypto_market_dataset/` 的資料欄位與缺口，以及規劃 Binance klines 的 UTC 對齊。
- Task 1a 一合併就可以開 `task/4-market-data`。

### P3（推理／報告）

- **Task 6 已完成**，待 P1 審核合併（分支 `task/6-bedrock-reasoning`）。
- 被擋住的後續：接上真實 `models.py`、Bedrock live 冒煙測試、`reporting/lint.py`
  （`renderer.py` 屬 Task 2，要等 Kiro 跑完）。

### P4（UI／Demo／部署）

- 尚未認領。**Task 0 preflight 不需要等任何人，可以現在就做**——它是 Silver 的前置，
  而且 Bedrock 模型開通與 ID 確認有前置時間，越早越好。
- 分支：`task/0-service-preflight`

## 下一批可認領的工作（依阻塞程度）

1. **Task 0 preflight**（P4）——不被任何人擋住，且擋住 Silver。現在就能做。
2. **Task 1a**（P1／Kiro）——擋住所有人。
3. **Task 2 fixture 垂直切片**（Kiro）——擋住 Bronze。
4. Task 4／5 資料與證據（P2）、Task 3 編排（P1）、Task 7 Streamlit（P4）——等 1a。
5. Task 11 創意層——非阻塞，但對應創意度評分，別排到最後。

## 已知的環境問題

- **本機 Python 是 3.11.9，`tech.md` 要求 3.12。** Task 1a 寫出 `requires-python = ">=3.12"`
  之後，沒裝 3.12 的人會 `pip install -e .` 失敗。跑 Task 1a 前先確認。
- `feature/crypto-data-html` 分支的 `tests/` 佔用了 Agent 測試的保留路徑，合併時會撞。
- 遠端另有 `feat/p2-*`、`task/7-html-report-template`、`analysis/dataset-eda`、`price`
  等分支，目前**都沒有 Python 原始碼樹**——有分支不代表有進度，認領前先確認。
