# Active Work — 誰正在做什麼

> **開工前先讀。** 這份文件只記當前事實與路徑 ownership；歷史狀態請看 Git。
>
> 最後更新：2026-08-02，S11 已部署上線（ECR/EC2 + rollback 實跑），只剩 15 分鐘計時彩排，基準 `main@c844a38`。
> **Feature Freeze 已生效**（2026-08-02）：此後只准 bug fix、可靠性修復、部署、彩排、文件、
> rollback 準備與提交驗證。🚫 新功能、新 provider、新 artifact 格式、PDF/HTML、額外視覺化、
> 五幣矩陣、Platinum、H3 一律拒絕。

## Authoritative status

| 階段 | 狀態 | 當前事實 |
|---|---|---|
| S0 | ✅ | 外部模型已成功呼叫（Haiku 4.5 @ `us-west-2`）；designated baseline research source 已指定（第一手 RSS ＋ Google News） |
| S1 | ✅ | canonical contracts/runtime seams 完成；`_provisional_seams.py` 已退役 |
| S2 | ✅ | fixture vertical slice 與四 artifacts 完成；canonical seam swap 完成 |
| S3 | ✅ | canonical Streamlit Bronze（`ui/{presenter,streamlit_app}.py`）、`reporting/advice_lint.py`（接進 renderer）、`Dockerfile`/`compose.yaml` 已落地；離線 Bronze Exit 通過、§3.2 人工清單以瀏覽器實測完成 |
| S4 | ✅ | per-stage 預算、finalize 保留、stage 狀態機、`WorkerStatus` 映射、cancel-then-await fork-join、取消落盤與固定跳過順序全部完成。optional／反方訊號來源清單由組裝端填入 |
| S5 | ✅ | deterministic market evidence 完成 |
| S6 | ✅ | material conflict 落盤、多事實抽取、CryptoPanic／Fear & Greed／official port 包裝、組裝端宣告 baseline／optional／反方訊號清單、單次 retry、共用 `AsyncClient`、`evidence/types.py` 已刪除、reliability 改由 processor 指派、fact-grounding（G1）接進 pipeline |
| S7 | ✅ | bounded reasoning 完成並凍結；`reasoning/{mapping,schemas}.py` 新增（未改凍結檔）提供 lax LLM I/O schema 與 strict `AnalysisResult` 投影 |
| S8 | ✅ | **Silver live Exit 已過（2026-08-02）**：`tests/live/test_live_silver_pipeline.py` → 1 passed in 50.15s，schema-valid Bedrock 結構化輸出 ＋ 四項 artifacts。live composition root `composition.py` ＋ `adapters/live_sources.py` 已落地 |
| S9 | ✅（離線） | Trust/Regime/Invalidation 完成 |
| S9B | ✅（離線） | one-run dual-asset comparison 完成 |
| S10 | 🟡 | `tests/acceptance/` 29 passed（兩資產獨立單幣 run、artifact 契約、fake-clock deadline）；`scripts/run_acceptance.py` ＋ `docs/rehearsals/run-log.md` 已落地。**complete-Evidence run 仍缺**——Bedrock 帳號未開通 |
| S11 | 🟡 | CI（3 job）、smoke test、本地 Docker、**ECR/EC2 已上線**（`http://35.91.36.186:8501`，tag `2cd9b43`）、**rollback 已實跑**、secret scan、CSV/Binance 重疊檢查、recorded fallback 全過；**只剩 15 分鐘計時彩排（人工）** |

## Current main

- Commit：`c844a38`（`main`）。S11 工作在 `agent/s11-delivery`。
- `src/hoya_agent/` 有 55 個 Python 檔；新增 `composition.py`、`adapters/live_sources.py`、
  `reasoning/{mapping,schemas}.py`、`evidence/{grounding,triangulation}.py`、`ui/{presenter,streamlit_app}.py`。
- `_provisional_seams.py` 與 `test_s1_seam_bridge.py` 已刪除；runtime imports 指向 canonical models/ports。
- **平行工具套** `src/calc/`（6 檔）與 `src/skills/`（13 檔）已納入 `main` 追蹤，是獨立價格分析腳本／技能，
  非 agent pipeline 的一部分；各自有 `tests/unit/{calc,skills}/`。
- **2026-08-02 離線實跑**（`c844a38`, Python 3.12）：
  `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q`
  → **1266 passed, 0 failed**；`ruff check .` → **All checks passed!**。
- **Silver live gate**：`tests/live/test_live_silver_pipeline.py` → 1 passed in 50.15s；S8 關閉。
- **GitHub Actions 已配置**：`.github/workflows/ci.yml` — verify／container／secret-scan，皆免 AWS 憑證。
- `tests/acceptance/` **已建立**（3 檔、29 tests）；`tests/live/` 有 opt-in source/Bedrock/silver-pipeline gate。
- **✅ Bedrock 可用**：競賽帳號改為主辦方提供的 **AWS Workshop Studio** 帳號
  `411451203311`（原本的 `035741228337` 不能用）。主辦已完成 Anthropic use case 開通，
  `scripts/diagnose_bedrock.py` → **3/3 成功，每次約 8 秒**。憑證是**短期的**，過期就重新
  從活動頁面取得；帳號本身也是臨時的，活動結束會回收。
- **🔴 證據一多，Arbiter 會撞 45 秒單次呼叫上限**：2026-08-02 同一 commit 兩次 live run，
  ETH（6 筆證據／2 個獨立上游）Arbiter 完成、信心 `high`；**BTC（20 筆證據／4 個獨立上游）
  `DeadlineExceeded`，整個推理層掉光，報告首頁變成「目前無法可靠判定」**。
  取證做得越好越容易失敗。45 秒上限是競賽規則與 `config.py` 寫死的，不能調高；
  可動的是 `ArbiterSettings` 的 `max_evidence`（預設 30）與 `max_tokens`（預設 8000），
  兩者都能從非凍結的組裝端注入。**尚未變更——屬推理層 owner 的決定。**
- **🔴 Planner 的資產比對永遠不相等**：`orchestration/pipeline.py:_reasoning_request` 傳
  `asset.value`（字串），`reasoning/planner.py:56` 卻拿 `str()` 去比 plan 端的 `Asset` enum，
  Python 3.11 起 `str(Asset.BTC)` 是 `'Asset.BTC'` 不是 `'BTC'`，所以**每次 live run 的
  LLM 計畫都被判違規丟棄**，改用決定論預設計畫。修點在凍結的 `reasoning/`，需 owner 同意。
- **2026-08-02 報告不再有內層捲軸**：`ui/streamlit_app.py:_embed_report()` 改用
  `st.iframe(..., height="content")`——Streamlit 會量測 srcdoc 內容並同時調整 **frame 與其
  element container**，報告隨主頁面一起捲動。兩個已知陷阱：① 用字元數推估高度（`722c6df`
  已撤回）永遠會猜錯；② 只放大 iframe 而不動 container，報告會溢出並蓋住下方的下載列與
  其他分頁。舊版 Streamlit（`pyproject` 允許 >=1.36，無 `st.iframe`）自動退回固定 1100px
  元件——會有內層捲軸，但不會破版。`_embeddable_report()` 另注入 TOC 錨點腳本（content-sized
  frame 不會捲動，導覽連結需改捲外層）＋一個 1px 高度 nudge：Streamlit **只在量測值改變時**
  才回報，而 srcdoc frame 可能在 host 掛上 listener 前就 load 完，那唯一一次量測會遺失，
  報告就卡在未量測高度（矮框＋內層捲軸）；報告是靜態的，不會再觸發重送。腳本只在 UI 路徑
  注入，下載的 `final_report.html` artifact 維持乾淨（`tests/unit/ui/test_report_embed.py`
  與 renderer 測試把關）。以 Edge headless + CDP 實測：frame 4419px／內容 4418px、三個
  分頁皆可見且未被遮蓋、下載列位於 frame 之下。

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
| 1 | **開通 Bedrock 帳號** | 帳號持有者 | 在 `411451203311` 的 Bedrock console 送出 Anthropic use case details 表單；`scripts/diagnose_bedrock.py` 3/3 成功 |
| 2 | S10 complete-Evidence run | 全員 | 開通後 `python scripts/run_acceptance.py --live`，兩資產都出推論／結論 Claim |
| 3 | **S11 15 分鐘計時彩排** | 全員 | 用 `docs/demo-runbook.md` 走一次完整流程，§3.2 的 S11 人工清單逐項簽核 |
| 4 | 彩排後關機 | P1/P4 | `aws ec2 stop-instances --instance-ids i-000a2cdc6d3c1afab`（跑著就計費） |
| 5 | repository hygiene | 各 owner | full pytest 綠、Ruff 零錯誤、狀態文件同步 |

## Commands

```bash
python -m pip install -e ".[dev]"

# tasks.md 的 Final Required Gate（逐字）
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short

# 額外驗收
python scripts/verify_s8_s9_s9b.py       # S8/S9/S9B 離線 smoke
python scripts/run_acceptance.py          # S10 兩資產獨立單幣 run（離線）
python scripts/smoke_test.py --artifacts-only
python scripts/diagnose_bedrock.py        # Bedrock 可用性（需 AWS_REGION + BEDROCK_PRIMARY_MODEL_ID）
```

## Coordination rules

1. 一律從最新 `main` 開分支；不要從 `feat/p2-*` 搬整棵平行目錄。
2. shared contracts、frozen reasoning/prompts 需 owner 同意才改。
3. S9/S9B 的「完成」只代表離線能力；S8 Silver 已過，S10 Gold、S11 deployment 各有獨立 gate。
4. 每次合併後同步本檔、Implementation Plan 與 Kiro WIP；不得保留已刪檔案的現況描述。
5. `src/calc/`、`src/skills/` 是平行工具套，不屬 agent pipeline；改動它們不需動 agent 狀態表。
