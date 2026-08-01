# Active Work — 誰正在做什麼

> **開工前先讀。** 這份文件只記當前事實與路徑 ownership；歷史狀態請看 Git。
>
> 最後更新：2026-08-01，S8 PR #25 基準 `main@3158031`。

## Authoritative status

| 階段 | 狀態 | 當前事實 |
|---|---|---|
| S0 | 🟡 | 外部模型曾成功呼叫，但正式 Converse 證據與 rehearsal 紀錄尚未補齊 |
| S1 | ✅ | canonical contracts/runtime seams 完成 |
| S2 | ✅ | fixture vertical slice 與四 artifacts 完成；provisional seam 已刪除 |
| S3 | 🔴 | canonical Streamlit、lint、container 與 Bronze acceptance 未完成 |
| S4 | ✅ | per-stage 預算、finalize 保留、stage 狀態機、`WorkerStatus` 映射、cancel-then-await fork-join、取消落盤與固定跳過順序（含裁剪 `ResearchPlan` 的執行點）全部完成（2026-08-01 第二輪，75 tests）。⚠️ optional／反方訊號的**來源清單**由組裝端宣告，待 S6 填入才會在真實 run 觸發 |
| S5 | ✅ | deterministic market evidence 完成 |
| S6 | 🟡 | research adapters/processor 大部分完成；canonical baseline acceptance 未完成 |
| S7 | ✅ | bounded reasoning 完成並凍結 |
| S8 | 🟡 | PR #25 補上 run-mode/provenance/degradation 與 opt-in live gates；受限於驗證環境，尚未實跑 Silver |
| S9 | ✅（離線） | Trust/Regime/Invalidation 完成 |
| S9B | ✅（離線） | one-run dual-asset comparison 完成 |
| S10 | 🔴 | Gold local Exit 未開始 |
| S11 | 🔴 | 部署與 judged-flow rehearsal 未開始 |

## Current main

- Commit：`d7245e4`（PR #18 squash merge）。
- `src/hoya_agent/` 有 42 個 Python 檔。
- `_provisional_seams.py` 與 `test_s1_seam_bridge.py` 已刪除。
- 新增 `orchestration/{deadline,pipeline,run_state}.py`、`evidence/trust.py` 與雙幣報告路徑。
- PR #18 的離線 S8/S9/S9B acceptance smoke、compileall、變更 whitespace check 通過。
- GitHub Actions/status checks 尚未配置；live Silver 仍不得宣稱通過。
- **完整 pytest／Ruff 已於 `b84622c` 實跑**（Claude Code，2026-08-01，Python 3.12.13，
  `uv pip install -e ".[dev]"` 後的乾淨 venv，含 streamlit 1.60.0）：
  `pytest tests -q` → **598 passed，零失敗**；`ruff check .` → **All checks passed**。
- **Ruff 基線 87 → 0**：PR #16 清一批，`9537d3e` 清掉剩餘 84 個，
  `37b1379` 引進的 2 個 `I001` 也已修掉。`Implementation-Plan.md` §3.3 的
  「`ruff check .` 乾淨」這條 DoD **現已達成**。
- `tests/acceptance/` 尚不存在；PR #25 新增 `tests/live/` 的 opt-in source/Bedrock gate。

## Completed and frozen

以下路徑若需修改，先取得 owner 同意並補 regression：

```text
src/hoya_agent/models.py
src/hoya_agent/config.py
src/hoya_agent/clock.py
src/hoya_agent/ports.py
src/hoya_agent/adapters/bedrock.py
src/hoya_agent/reasoning/
src/hoya_agent/evidence/policies.py
prompts/
tests/contract/
tests/unit/reasoning/
```

S9B 的 per-asset/source 配額位於 orchestration projection；完整 Ledger artifact 不截斷，
且 PR #18 沒有修改 frozen `reasoning/arbiter.py`。

## Remaining work and ownership

| 優先 | 工作 | Owner | 完成條件 |
|---:|---|---|---|
| 1 | S3 Streamlit Bronze＋禁語 lint＋container shell | UI/P4 | 完整離線 UI run 產出四 artifacts |
| 2 | S4 專項 deadline/fork-join tests | P1 | fake clock、timeout、cancellation、sibling preservation 全綠 |
| 3 | S6 canonical research baseline 收斂 | P2/P3 | schema-valid Evidence、失敗 typed degradation |
| 4 | S8 live Silver | 全員，P1 gate | live Bedrock baseline success＋獨立 fallback acceptance |
| 5 | S10 Gold local Exit | 全員 | 兩個不同資產各一次獨立單幣 run＋deadline/artifact gate |
| 6 | S11 deploy/rehearse | P1/P4 | CI、ECR/EC2、rollback、15 分鐘完整彩排 |
| 7 | repository hygiene | 各 owner | full pytest 綠、Ruff 零錯誤、狀態文件同步 |

## Commands

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit tests/contract tests/integration -q
ruff check .
python scripts/verify_s8_s9_s9b.py
```

## Coordination rules

1. 一律從最新 `main` 開分支；不要從 `feat/p2-*` 搬整棵平行目錄。
2. shared contracts、frozen reasoning/prompts 需 owner 同意才改。
3. S9/S9B 的「完成」只代表離線能力；S8 Silver、S10 Gold、S11 deployment 各有獨立 gate。
4. 每次合併後同步本檔、Implementation Plan 與 Kiro WIP；不得保留已刪檔案的現況描述。
