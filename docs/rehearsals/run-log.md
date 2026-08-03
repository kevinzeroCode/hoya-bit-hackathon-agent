# Gold local Exit — run log

Records the **two independent single-asset runs** required by S10 (`tasks.md` Task 9).
Two different assets, two separate runs, two separate ledgers — this gate proves the
pipeline is coin-agnostic and is **not** a substitute for the dual-asset comparison
(Requirement 17), which has its own gate.

No credentials, tokens, response headers or prompt bodies are recorded here.

**Driver:** `python scripts/run_acceptance.py [--live] [--markdown]`
**Automated contract:** `tests/acceptance/test_{gold_assets,artifact_contract,deadline_budget}.py`

---

## 2026-08-02 — offline baseline (organizer CSV), `agent/s11-delivery` @ `c844a38`

Deterministic, network-free, credential-free. This is the run pair the automated
gate mirrors, and the one anybody can reproduce.

```bash
python scripts/run_acceptance.py --artifact-root artifacts --markdown
```

| 資產 | run ID | 模式 | terminal state | 時長 (s) | evidence | 獨立上游 | artifact 目錄 |
|---|---|---|---|---:|---:|---|---|
| BTC | `run_20260802_011444_g1bt` | rehearsal／offline CSV | degraded | 0.3 | 5 | organizer-public-market-data | `artifacts/run_20260802_011444_g1bt` |
| ETH | `run_20260802_011445_g2et` | rehearsal／offline CSV | degraded | 0.3 | 5 | organizer-public-market-data | `artifacts/run_20260802_011445_g2et` |

- Cutoff frozen at `2026-05-31T00:00:00Z` (the organizer dataset's last bar).
- Four artifacts present in both runs; distinct `run_id`s; each ledger carries only its own asset.
- **Degradation (expected, disclosed):** `OrganizerCsvPipeline` has no Arbiter, so both runs
  end `degraded` with `insufficient_data=true` and the deterministic
  「目前無法可靠判定」 report over real Evidence. Nothing is claimed that the Evidence
  cannot support.

## 2026-08-02 — live baseline paths, same branch

```powershell
$env:AWS_REGION = "us-west-2"
$env:BEDROCK_PRIMARY_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
python scripts/run_acceptance.py --live --artifact-root artifacts --markdown
```

| 資產 | run ID | 模式 | terminal state | 時長 (s) | evidence | 獨立上游 | artifact 目錄 |
|---|---|---|---|---:|---:|---|---|
| BTC | `run_20260802_011225_g1bt` | rehearsal／live | degraded | 4.1 | 5 | organizer-public-market-data | `artifacts/run_20260802_011225_g1bt` |
| ETH | `run_20260802_011230_g2et` | rehearsal／live | degraded | 3.5 | 5 | organizer-public-market-data | `artifacts/run_20260802_011230_g2et` |

**Source gaps actually observed** (from `execution_log.jsonl`, not inferred):

| Stage / source | Outcome |
|---|---|
| `market_worker` | ✅ completed — 4 deterministic market drafts + regime → 5 ledger items |
| `evidence_processor` | ✅ completed — ledger built with 5 items |
| Planner (Bedrock) | 🔴 `LLMUnavailableError` → deterministic default plan |
| Research extraction (Bedrock) | 🔴 `LLMUnavailableError` → raw records kept, no Evidence draft |
| Arbiter (Bedrock) | 🔴 `LLMUnavailableError` → deterministic fallback result |
| `fetch_official_announcements` (BTC) | ⚠️ `http_error` on first attempt, retried once inside the acquisition window, then `SourceUnavailable` |
| `fetch_cryptopanic_news` | ⏸ `SourceUnavailable` — `CRYPTOPANIC_API_TOKEN` not configured |

### 🔴 Blocker: Bedrock is not enabled on this AWS account

Every Bedrock call from AWS account `035741228337` in `us-west-2` returns:

```
ResourceNotFoundException: Model use case details have not been submitted for this
account. Fill out the Anthropic use case details form before using the model.
```

Reproduced with `scripts/diagnose_bedrock.py` against
`us.anthropic.claude-haiku-4-5-20251001-v1:0`,
`global.anthropic.claude-haiku-4-5-20251001-v1:0`,
`us.anthropic.claude-3-haiku-20240307-v1:0` and
`us.anthropic.claude-sonnet-4-5-20250929-v1:0` — 0/3 successful calls each.

This is an **account enablement action in the Bedrock console**, not a code defect: the
pipeline degrades exactly as designed and still ships four honest artifacts. The S8
Silver Exit recorded on 2026-08-02 was executed against a *different*, already-enabled
account.

**Until the form is submitted and propagated**, no run from this account can produce
inference or conclusion Claims, so:

- the two run pairs above prove **artifact contract, provenance, coin-agnosticism,
  deterministic rendering and honest degradation**;
- they do **not** prove a complete-Evidence Gold run with reasoning. That half stays
  open and must not be recorded as passed.

---

## Gold local Exit status

| S10 exit condition | Status | Evidence |
|---|---|---|
| Silver has passed | ✅ | S8, 2026-08-02, separate account |
| Two different assets, separate single-asset runs | ✅ | four runs above, two assets, four distinct `run_id`s |
| Required degradation checks | ✅ | missing-baseline-source and Bedrock-unavailable cases both disclosed, four artifacts each |
| Deterministic artifact checks | ✅ | `tests/acceptance/` — 29 passed |
| Fake-clock deadline acceptance | ✅ | `tests/acceptance/test_deadline_budget.py` — minute-12 cancel + finalize before the reserve |
| Complete-Evidence run with reasoning | 🔴 | blocked on the Bedrock account form above |

**Explicitly excluded from this local gate:** Docker build/runtime acceptance, ECR
deployment, EC2 deployment, the timed judged-flow rehearsal and submission verification.
Those belong to S11.

---

## 2026-08-02 (第二次) — 帳號改為主辦方 Workshop Studio `411451203311`，Bedrock 可用

主辦規定必須使用 `411451203311`（Workshop Studio 臨時帳號），原本的 `035741228337` 作廢。
該帳號的 Anthropic use case 已由主辦開通：`scripts/diagnose_bedrock.py` → **3/3 成功，約 8 秒/次**。

```powershell
$env:AWS_PROFILE = "hoya"; $env:AWS_REGION = "us-west-2"
$env:BEDROCK_PRIMARY_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
python scripts/run_acceptance.py --live --artifact-root artifacts
```

| 資產 | run ID | terminal state | 時長 (s) | evidence | source types | 獨立上游 | Arbiter | 結論 |
|---|---|---|---:|---:|---|---|---|---|
| BTC | `run_20260802_023614_g1bt` | degraded | 67.6 | 20 | market, news, social | alternative.me, coindesk.com, decrypt.co, organizer-public-market-data | 🔴 `DeadlineExceeded` | **無** |
| ETH | `run_20260802_023723_g2et` | degraded | 35.3 | 6 | market, social | alternative.me, organizer-public-market-data | ✅ completed | 有，信心 `high` |

### 這一輪學到的兩件事

**1. 取證越成功，推理越可能失敗。** BTC 達成了 run 目標（≥3 種 source type、≥3 個
independence group），正因為證據多，Arbiter 的單次呼叫超過 45 秒硬上限而整個掉掉，
報告首頁變成「目前無法可靠判定」。ETH 證據少反而順利完成並拿到 `high`。
45 秒是競賽規則與 `config.py` 寫死的，可動的是 `ArbiterSettings.max_evidence`（預設 30）
與 `max_tokens`（預設 8000），兩者都能從非凍結組裝端注入。**尚未變更——推理層 owner 決定。**

**2. Planner 的 LLM 計畫每次都被丟棄。** `orchestration/pipeline.py:_reasoning_request`
傳的是 `asset.value`（字串 `"BTC"`），`reasoning/planner.py:56` 卻用 `str()` 比對 plan 端
pydantic 轉出來的 `Asset` enum。Python 3.11 起 `str(Asset.BTC)` 回 `'Asset.BTC'`，
兩邊永遠不相等，於是每次都判「plan changed the requested assets」並退回決定論預設計畫。
修點在凍結的 `reasoning/`，需 owner 同意。

### 已修（本分支）

`application.build_research_pipeline` 先前沒有對自建的 market branch 關掉
`emit_no_arbiter_note`，導致**有結論的 run 同時在報告裡寫「未產出經驗證的推論或結論」**——
報告自己打自己臉。已修，並補上兩條回歸測試
（`tests/integration/test_composed_research_pipeline.py`），其中一條在修復前確實會紅。

## 2026-08-02 — `arbiter_max_tokens` 實測（同帳號、同模型、同一天）

模型：`us.anthropic.claude-haiku-4-5-20251001-v1:0` @ `us-west-2`，account `411451203311`。

| 路徑 | max_tokens | 時長 (s) | evidence | Arbiter | 信心 | 結論層 claim |
|---|---:|---:|---:|---|---|---|
| UI（`composition.build_live_pipeline`） | 3000 | 49.0 | 21 | ✅ completed | low | **無** |
| UI | 3000 | 75.7 | 35 | ✅ completed | medium | **無** |
| UI | **6000** | 116.0 | 32 | 🔴 `DeadlineExceeded` | low | 無 |
| 腳本（`build_research_pipeline`） | 8000 | 67.6 | 20 | 🔴 `DeadlineExceeded` | low | 無 |
| 腳本 | 8000 | 35.3 | 6 | ✅ completed | high | **有**（`cl_009`） |
| 腳本 | 3000 | 52.0 | 18 | ✅ completed | medium | **無** |
| 腳本 | 3000 | 46.2 | 6 | ✅ completed | low | **無** |

### 結論一：`max_tokens=3000` 是對的，🚫 不要調高

6000 直接把 Arbiter 推過 45 秒單次上限。`composition.py` 早就把 UI 路徑設成 3000 並留了註解
（「default 8000 tokens can overrun → DeadlineExceeded → fallback」），只是
`application.build_research_pipeline` 沒跟上，仍用凍結預設 8000。**已補齊**（`ARBITER_MAX_TOKENS`）。

### 結論二：結論層 claim 不穩定，這是尚未解決的問題

七次 live run 中**只有一次**產出結論層 claim。其餘即使 Arbiter 正常完成、
信心到 `medium`、`insufficient_data=False`，第 7 段仍是「本次 run 未產出可驗證的結論層 claim」。
用 `MappingArbiter` 的 spy 攔截模型原始輸出，看到的是 `claims` **本身就是空的**（0 筆），
不是 mapping 丟掉的。

先前一度以為是 UI 與腳本用不同 Arbiter schema（`ArbiterGeneration` vs `ArbiterOutput`）造成的差異，
**但更多樣本推翻了這個假設**——兩條路徑都會出現空結論，差別是 run 之間的變異。
`main` 上的 `a1d17f2 fix(arbiter): guarantee non-empty structured claims on live runs`
顯然沒有完全蓋住這個情況。

**未修：** 修點在凍結的 `reasoning/` 套件（Arbiter 或 prompt），屬推理層 owner 的決定。

### 對 demo 的實際影響

live run 可以展示：多來源即時證據（18–35 筆、2–4 個獨立上游、3 種 source type）、
信任漏斗、Evidence Ledger、Execution Log、四項可下載 artifacts、以及決定論的信心上限規則。
**不能保證展示的是：第 7 段的結論。** 彩排時要先知道這件事。

### Gold local Exit 狀態更新

complete-Evidence run **未達成**：曾有一次 ETH 取得完整證據＋推論＋結論（信心 `high`），
但無法穩定重現。兩資產都要能穩定產出才算 S10 收尾。

## 2026-08-03 — 五幣完整驗證矩陣（Task 19，offline organizer CSV）

`tests/acceptance/test_five_asset_matrix.py` — 把 Task 9 的兩幣（BTC/ETH）模式擴到剩下三幣
（SOL、BNB、XRP），驗證同一套 artifact/provenance/terminal-state 契約，不是新契約。

```bash
python -m pytest tests/acceptance/test_five_asset_matrix.py tests/acceptance/test_gold_assets.py -q
```
→ **8 passed**（SOL/BNB/XRP 各一次獨立單幣 run、五幣合併驗證 run_id 互異、
無 per-coin 分支的靜態檢查）。

| 資產 | terminal state | evidence 筆數 | 缺口揭露 |
|---|---|---|---|
| SOL | degraded（無 Arbiter，符合預期） | > 0 | 無新增缺口，與 BTC/ETH 行為一致 |
| BNB | degraded（無 Arbiter，符合預期） | > 0 | 無新增缺口，與 BTC/ETH 行為一致 |
| XRP | degraded（無 Arbiter，符合預期） | > 0 | 無新增缺口，與 BTC/ETH 行為一致 |

**誠實揭露：** 這是 offline organizer CSV 路徑（`OrganizerCsvPipeline`，無 Arbiter），
所以五幣的 `terminal_state` 都是 `degraded`——這與 Task 9 記錄的 BTC/ETH offline baseline
一致，**不是**五幣各自的新缺口。live baseline（含推論結論）沿用同一批既有已知限制
（Bedrock 帳號臨時、結論層不穩定，見上方章節），本次矩陣未另外重跑 live，
因為那條路徑的缺口與資產無關，重跑五次不會產生新資訊。
五幣的請求 allowlist 與 pipeline 路徑完全共用同一份程式碼，無任何 per-coin 分支
（`test_five_asset_coverage_requires_no_per_coin_branch_in_src` 靜態檢查）。
