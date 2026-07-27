# CLAUDE.md — HOYA Market Agent

> 這份檔案讓 **Claude Code** 與 **Kiro** 的 spec 對齊。Claude Code 只自動讀本檔，不讀 `.kiro/`，
> 所以此處鏡射 `.kiro/steering/` 的鐵則。**規則衝突時，以 `.kiro/specs` 與 `.kiro/steering` 為準。**

## 專案一句話

現場接收「指定幣種 + 未知題目」後，在 **15 分鐘內**整合多源資料，產出**可回溯、會誠實揭露限制**的繁體中文加密市場分析。MVP 唯一承諾架構：**H2-Lite**。

## 真相來源（Source of Truth）

- 需求：`.kiro/specs/hoya-market-agent/requirements.md`
- 設計：`.kiro/specs/hoya-market-agent/design.md`
- 任務：`.kiro/specs/hoya-market-agent/tasks.md`
- 契約鐵則：`.kiro/steering/`（competition-rules / evidence-contracts / tech / structure / testing / product / development-workflow）
- Evidence/Claim/Result 的欄位定義以 `.kiro/steering/evidence-contracts.md` 為**唯一**權威。

---

## 🔀 工具分工（重要 — Claude Code 必守）

為節省 Kiro token，只有「Kiro 招牌動作」交給 Kiro，其餘全部 Claude Code 做。

**保留給 Kiro，Claude Code 不要動：**
- `tasks.md` 的 **Task 1（models/contracts）** 與 **Task 2（fixture vertical slice → 四個 artifacts）** 由 Kiro 從 spec 生成，作為「Kiro 用於開發」的證據。**Claude Code 不要搶先實作這兩個 task 的核心檔案。**
- `docs/evidence/kiro/` 底下的 Kiro 使用證據（截圖 / diff / 錄影說明）。

**其餘全部 Claude Code 做：**
- Task 3–10 的所有實作（orchestration、adapters、evidence、reasoning、reporting、ui）
- 全部測試、`Dockerfile`、`compose.yaml`、部署腳本
- 修 `.kiro` / `docs` 內的 markdown（斷鏈、CoinGecko 矛盾等純文字修訂）
- 簡報、AWS 架構圖、README

若某任務原標為 Kiro 但時間不夠，可改由 Claude Code 補完 — 但要在 `docs/evidence/kiro/README.md` 誠實記錄實際由誰產出。

---

## 架構：H2-Lite 固定流程

```
Streamlit UI → ApplicationService.run() → DeadlineAwarePipeline
  Planner (1 次 bounded Bedrock)
  → asyncio.gather(return_exceptions=True):
       Market Worker (deterministic Python，不呼叫 LLM)
       Research Agent (bounded LLM 抽取)
  → Evidence Processor (schema/dedup/independence/reliability/conflict，deterministic)
       → 立刻寫 evidence.json
  → ConflictExtension (MVP 永遠 disabled stub，直接 route 到 Arbiter)
  → Arbiter (1 次 bounded Bedrock，最多 1 次 schema repair，失敗則 deterministic fallback)
  → Renderer + Artifact Builder (deterministic，不呼叫 LLM)
```

**只有 Planner / Research 抽取 / Arbiter 用 LLM。** Market Worker、Evidence Processor、conflict、render、lint、artifact、deadline 全部 deterministic。

### 模組邊界與依賴方向（`structure.md`）

```
streamlit_app → ui.presenter + application → orchestration
orchestration → data + evidence + reasoning + reporting
core modules → ports → adapters 實作
所有模組 → models
```
- `models.py` 不 import 任何專案模組。
- **只有** `adapters/*.py` 可以 import `httpx` / `boto3`。
- `data/`、`evidence/`、`reporting/` 是 deterministic，**永不呼叫 Bedrock**。
- `reasoning/` 用 `LLMClient` 與 evidence IDs，**不寫 artifacts**。
- 商業邏輯不得放進 Streamlit callback。

---

## 不可違反的鐵則（違反 = 直接丟分）

1. **四個固定檔名**：`final_report.md`、`evidence.json`、`execution_log.jsonl`、`run_config.json`。用「同目錄暫存檔 + `os.replace`」原子寫入。四項在**第 13 分鐘前**齊全。
2. **證據可回溯**：每個關鍵結論都要有 Evidence ID；LLM 產物**永遠不是**證據來源。市場數值只能來自 deterministic tool，LLM 不得補值/猜值。
3. **Evidence 無立場**；`supports|opposes|neutral` 只存在 `ClaimEvidenceLink`。
4. **Claim 分層** `fact|inference|conclusion`，經 `based_on_claim_ids` 回溯到 fact，不得循環；每個 conclusion 要有 supporting evidence，否則 `insufficient_data=true`。
5. **reliability 靜態表**（high/medium/low），**LLM 不得調整**。轉載未取原頁一律 low。
6. **material conflict** 只在「同一 claim 有不同 independence group、reliability≥medium 的 supports 與 opposes」時成立；成立則保留雙方並把該結論 confidence 壓到 low。
7. **Run mode 誠實**：`official` 禁 fixture/舊報告；`rehearsal`/`demo` 必須明顯標示。三模式在 UI、log、`run_config.json` 都可辨識。fixture 不得偽裝成 live official。
8. **Deadline**：900 秒硬限；`time.monotonic()` 算 budget，UTC 只用於落盤時間戳。單一 call ≤45 秒、最多 retry 1 次、共用 stage deadline。第 12 分鐘取消所有非必要外部呼叫。跳過順序：H3 → optional context adapter → 反方訊號二次搜尋。
9. **報告**：繁體中文，deterministic Renderer 產生（**不讓 LLM 寫全文**），含 spec 的 11 個段落。**禁止**買/賣/加倉/減倉/做多/做空/配置等投資建議 — Renderer 用字串 lint 當最後防線。confidence 只用 high/medium/low + 理由，不得包裝成精確機率。
10. **Secrets**：`.env`、API key、AWS 憑證、CryptoPanic token、prompt 全文，**不得**進 UI/log/artifact/repo/截圖。commit 前跑 secret scan。
11. **schema**：所有跨模組 payload 用 Pydantic v2 + `extra="forbid"`；欄位名在 Python/JSON/prompt/fixture/test 之間完全一致。LLM 輸出須先驗證通過才進 core。

## 幣種無關（coin-agnostic）通用作法

幣種現場才抽,五幣任一都可能中。詳見 `competition-rules.md` §Coin-Agnostic Source Policy。核心:
- Pipeline 以 `{asset}` 為參數,五幣共用同一路徑;**禁止 per-coin 分支/特調**。
- 來源「用幣種符號就能查五幣」才進 MVP(CSV、Binance `{ASSET}USDT`、CryptoPanic currency、Fear&Greed)。
- 「每個幣要各寫一套」的來源(各鏈鏈上瀏覽器、各專案官方 Blog)一律 best-effort 或跳過,缺漏誠實揭露。
- 鏈上/社群若要納入,只用「單一多鏈/多幣聚合來源」,**不為五條鏈各寫 adapter**。
- 驗證兩個不同幣各跑一次單幣即可,不做五幣完整矩陣。

## MVP 明確排除（未經 H2-Lite 全綠不得動）

H3 Bull/Bear/Judge 實作、鏈上/宏觀/額外社群 adapter、S3/CloudWatch/ECS、近似去重、動態 reliability、自由 agent loop、自建 token 計數器、PDF/HTML、五幣完整驗證矩陣、雙幣比較。不得引入 LangGraph / Strands / FastAPI / Celery / Redis / 向量 DB / message broker。

---

## 開發流程（`development-workflow.md` + `testing.md`）

- **Red → Green → Refactor**：先寫會失敗的聚焦測試 → 跑到確認失敗 → 最小實作 → 跑模組測試 + 相關 regression → 通過才 commit。
- 一次一個 task；同 commit 更新 `tasks.md` 的 checkbox。
- **絕不宣稱測試通過卻沒實際跑過。** 修 bug 先加重現用 regression test。
- Conventional commits：`feat:` `fix:` `test:` `docs:` `chore:`。每個 task 一個 commit，不要 squash。
- 在 `docs/evidence/kiro/README.md` 記錄 Kiro task→commit 對應。

## 常用指令（repo root）

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit tests/contract tests/integration -q      # 合併前
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q  # freeze 前 / CI
ruff check .
docker compose config
```
- 預設 `pytest` **絕不**碰外網。Live test 需同時 `@pytest.mark.live` + `RUN_LIVE_TESTS=1`，否則 skip。
- 用 fixed clock / fake sleeper 測 deadline，不真的 sleep 45 秒。

## 交付四項 artifacts 的欄位（速查）

- **evidence.json**：`schema_version, run_id, analysis_as_of, run_mode, items[], conflict_indicators[], degradation_events[]`；EvidenceItem 至少含 `source, fetched_at, content_reference, related_claim`（命題硬性要求）+ reliability/independence_group/content_hash。
- **execution_log.jsonl**：每行一物件，含 timestamp/run_id/run_mode/stage/event_type/status/duration_ms/provider_or_model/sanitized params。**只記 prompt 版本，不記全文。**
- **run_config.json**：run 開始即寫，含 schema/prompt 版本、sanitized request、模式、deadline、模型 ID、optional key 的存在布林值（非值）、terminal status。
- **final_report.md**：最後寫；deterministic；繁中 11 段。

## 已修正的規格矛盾（紀錄）

- 斷鏈：`design.md` 原引用不存在的 `docs/ai/SPEC_DIFF_PLAN.md`、`STAGED_DELIVERY_PROPOSAL.md` → 已改指向 `tasks.md`。
- CoinGecko：`.kiro/steering`（evidence-contracts / tech / structure / competition-rules）已統一為「post-hackathon Future Work，MVP 不實作」，與 `design.md §8.3` / requirements 一致。
- 註：`docs/superpowers/*` 是設計已註明的**歷史紀錄**（已被 `.kiro/specs` 取代），保留原文，不視為現行契約。
