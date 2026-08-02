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
| S11 | 🟡 | CI（3 job）、smoke test、本地 Docker、**ECR/EC2 已上線**（`http://44.248.255.72:8501`，tag `2cec732`）、**rollback 已實跑**、secret scan、CSV/Binance 重疊檢查、recorded fallback 全過；**只剩 15 分鐘計時彩排（人工）** |

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
- **🔴 Bedrock 帳號阻塞**：account `035741228337` @ `us-west-2` 每次呼叫都回
  `ResourceNotFoundException: Model use case details have not been submitted for this account`。
  Haiku 4.5／Claude 3 Haiku／Sonnet 4.5、`us.` 與 `global.` profile 全試過皆 0/3。
  這是 Bedrock console 的帳號開通動作。S8 的 Silver Exit 是在**另一個已開通帳號**上過的。
  未開通前，任何 live run 都只有 deterministic 市場證據、無推論與結論（誠實降級，四項 artifacts 仍齊全）。

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
| 1 | **開通 Bedrock 帳號** | 帳號持有者 | 在 `035741228337` 的 Bedrock console 送出 Anthropic use case details 表單；`scripts/diagnose_bedrock.py` 3/3 成功 |
| 2 | S10 complete-Evidence run | 全員 | 開通後 `python scripts/run_acceptance.py --live`，兩資產都出推論／結論 Claim |
| 3 | **S11 15 分鐘計時彩排** | 全員 | 用 `docs/demo-runbook.md` 走一次完整流程，§3.2 的 S11 人工清單逐項簽核 |
| 4 | 彩排後關機 | P1/P4 | `aws ec2 stop-instances --instance-ids i-0fa12c895827d6c4e`（跑著就計費） |
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
