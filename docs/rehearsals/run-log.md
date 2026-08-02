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
