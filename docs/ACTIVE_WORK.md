# Active Work — 誰正在做什麼

> **開工前先讀。** 這份文件只記當前事實與路徑 ownership；歷史狀態請看 Git。
>
> 最後更新：2026-08-02，live Silver Exit 已過、UI／live composition root／calc／skills 已落地，基準 `main@6f914dc`。

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
| S10 | ✅ | Gold local Exit 已完成（2026-08-02；BTC/ETH 獨立單幣 run、degradation/artifact/fake-clock acceptance） |
| S11 | 🔴 | 部署與 judged-flow rehearsal 未開始（CI、ECR/EC2、live smoke、rollback、15 分鐘彩排） |

2026-08-02 follow-up: the live Arbiter boundary now performs deterministic evidence-link
repair for mismatched numeric claims and conclusion support before the frozen validation
gate. P4's self-contained `final_report.html` is also integrated without removing the
Markdown/Evidence/Log/Run Config downloads. Full non-live verification: `1272 passed`;
Ruff clean. Live Bedrock rerun remains pending because this environment has no live
credentials.

Safety follow-up: report advice-lint failures now degrade to a complete deterministic
artifact set instead of aborting after Evidence List generation. Latest full non-live
verification: `1273 passed`; Ruff clean.

## Current main

- Commit：`6f914dc`（`main`）。
- `src/hoya_agent/` 有 55 個 Python 檔；新增 `composition.py`、`adapters/live_sources.py`、
  `reasoning/{mapping,schemas}.py`、`evidence/{grounding,triangulation}.py`、`ui/{presenter,streamlit_app}.py`。
- `_provisional_seams.py` 與 `test_s1_seam_bridge.py` 已刪除；runtime imports 指向 canonical models/ports。
- **平行工具套** `src/calc/`（6 檔）與 `src/skills/`（13 檔）已納入 `main` 追蹤，是獨立價格分析腳本／技能，
  非 agent pipeline 的一部分；各自有 `tests/unit/{calc,skills}/`。
- **2026-08-02 離線實跑**：`python -m pytest tests/unit tests/contract tests/integration -q` →
  **1235 passed, 0 failed**；`ruff check .` → **All checks passed!**（Python 3.12）。
- **Silver live gate**：`tests/live/test_live_silver_pipeline.py` → 1 passed in 50.15s；S8 關閉。
- GitHub Actions/status checks 尚未配置；S8 以 D 槽 credentialed manual live gate 驗收通過。
- `tests/acceptance/` 尚不存在；`tests/live/` 有 opt-in source/Bedrock/silver-pipeline gate。

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
| 1 | S10 Gold local Exit | 全員 | ✅ 2026-08-02：兩個不同資產各一次獨立單幣 run＋fake-clock deadline/artifact gate |
| 2 | S11 deploy/rehearse | P1/P4 | CI、ECR/EC2（見 `docs/deploy-ec2.md`）、rollback、15 分鐘完整彩排 |
| 3 | GitHub Actions / status checks | P1 | CI workflow 配置 |
| 4 | repository hygiene | 各 owner | full pytest 綠、Ruff 零錯誤、狀態文件同步 |

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
3. S9/S9B 的「完成」只代表離線能力；S8 Silver 已過，S10 Gold、S11 deployment 各有獨立 gate。
4. 每次合併後同步本檔、Implementation Plan 與 Kiro WIP；不得保留已刪檔案的現況描述。
5. `src/calc/`、`src/skills/` 是平行工具套，不屬 agent pipeline；改動它們不需動 agent 狀態表。
## 2026-08-02 reviewer UI polish

正式評審畫面已移除 H3 未使用提示與內部實作術語，保留報告、證據來源、執行紀錄、
限制揭露及下載功能。UI 與 HTML/Markdown 報告的文字已完成整理。
2026-08-02：推理卡片已完成桌面與窄螢幕排版修正，主張與證據標籤不再互相擠壓。
2026-08-02：研究報告區預設展開並沿頁面閱讀，避免固定內嵌視窗造成雙重捲軸。
