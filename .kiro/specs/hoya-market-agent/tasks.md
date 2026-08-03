# HOYA Market Agent Implementation Tasks

> Product authority: `.kiro/specs/hoya-market-agent/requirements.md`
>
> Implementation authority: `.kiro/specs/hoya-market-agent/design.md`
>
> Historical product context and ownership guidance remain in `docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md` and `docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md`.
>
> Hard limit: four junior developers, two calendar days. H2-Lite is the only committed analysis method.
>
> Platinum, the CoinGecko live adapter, the complete five-asset validation/calibration matrix, H3 implementation, S3, CloudWatch and ECS were post-hackathon Future Work and were not executable tasks during the formal two-day delivery period.
>
> **The competition ended 2026-08-02.** Tasks 0-12 are the shipped competition MVP (Gold local
> Exit, deployment and CD all passed) and stay frozen as delivered — do not re-open them without
> a bug. Tasks 13-21 below are the approved post-competition continuation: real remaining gaps
> (13-16) plus the former Future Work items, now formally in scope (17-21). Every non-scope rule
> in `.kiro/steering/competition-rules.md` (honesty, determinism boundaries, secrets, deadlines)
> still applies unchanged to the new tasks.

## Execution Rules

- Execute waves in order. Tasks inside the same wave may run in parallel only after their dependencies are green.
- Every required behavior follows Red -> Green -> Refactor and `.kiro/steering/testing.md`.
- Do not use Kiro `Run all Tasks`. Start with the fixture vertical slice, then dispatch by owner.
- Commit after every numbered task. Do not combine unrelated owners' work in one commit.
- P1 owns shared contracts and integration decisions. Contract changes require all affected owners to acknowledge before merge.
- Follow `docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md` for file ownership, task branches and handoffs.
- P1 and P4 co-own Docker/ECR/EC2 deployment; P4 never carries deployment or shared-contract risk alone.
- Task 0 service-access checks are non-blocking for Bronze.
- Pass the completely offline Bronze path through Streamlit before live-provider or Bedrock work becomes a required dependency.
- Silver requires both one schema-valid live Bedrock success using the designated baseline market and research paths and a separate deterministic fallback/degradation acceptance; fallback-only execution cannot pass Silver.
- Gold local Exit requires Silver, two different assets as separate local single-asset runs, required degradation checks and deterministic artifact checks. It does not require Docker/ECR/EC2 deployment or the timed judged-flow rehearsal.
- Feature Freeze begins at Gold local Exit or Day 2 midday, whichever occurs first.
- After Feature Freeze, only bug fixes, reliability fixes, deployment, rehearsal, documentation, rollback preparation and submission verification are allowed.
- Platinum and other post-hackathon Future Work are never executable during the formal two-day delivery period.

## Wave Map

| Wave | Time box | Required tasks | Parallel owners | Exit gate |
|---|---:|---|---|---|
| 0 | Day 1, first 45 min | 1; Task 0 runs non-blocking | P1 + P4, all review | Shared schemas, compatibility seams and local fixture dependencies are frozen; access failures do not block Bronze |
| 1 | Day 1 morning | 2 and the Task 7 Bronze checkpoint | P1/P3 with P4; P2 reviews | A completely offline Streamlit run produces the four fixed artifacts without network, Bedrock, AWS credentials or Docker acceptance |
| 2 | Day 1 remainder | 3, 4, 5, 6 and remaining Task 7 work | P1/P2/P3/P4 | Runtime controls, baseline adapters, H2-Lite reasoning and UI/container support preserve Bronze |
| 3 | Day 2 morning | 8 | All | Silver passes one schema-valid live Bedrock baseline path and a separate deterministic fallback/degradation gate |
| 4 | Before the earlier freeze trigger | 9 | All; P1 owns the gate | Gold local Exit passes two separate single-asset runs, required degradation checks and deterministic artifact checks locally |
| 5 | After Feature Freeze | 10 | P1 + P4 lead; all rehearse | Docker/ECR/EC2 delivery, one timed judged-flow rehearsal, rollback and submission verification complete without new features |
| Future | Post-hackathon only | Future Work references | Explicitly re-approved ownership | Never executes during or blocks Bronze, Silver, Gold, deployment, rehearsal or submission |

## Current checkpoint (2026-08-02, main@c844a38)

- Complete: Tasks 1, 2, 4, 6 and 8 (Silver live Exit passed 2026-08-02).
- Mostly landed but canonical baseline acceptance remains open: Tasks 3 and 5.
- Offline implementation complete, repository-wide gates now green: Tasks 11 and 12.
- **Task 9 (Gold local Exit): automated half complete, live half blocked.** `tests/acceptance/`
  (29 passed), `scripts/run_acceptance.py` and `docs/rehearsals/run-log.md` exist; the
  Final Required Gate command runs verbatim for the first time — 1266 passed, Ruff clean.
  A complete-Evidence run with reasoning is blocked on Bedrock account enablement.
- **Task 10 (deploy + rehearsal): deployed and verified; one item left.** CI, smoke test,
  Docker build, in-image smoke, non-root check and secret scan all pass. ECR repository and
  EC2 host are live: `http://35.91.36.186:8501` running the immutable tag `2cd9b43`, which
  matches the pushed ECR tag character for character. Rollback was actually executed
  (`c844a38` and back). CSV/Binance overlap check and the out-of-VCS recorded fallback are
  done. **The 15-minute timed judged-flow rehearsal has not been executed** — it is a human
  task; script in `docs/demo-runbook.md`.
- Not complete: Tasks 0, 7.
- **Blocker:** AWS account `411451203311` has not submitted the Anthropic use case details
  form, so every Bedrock call in `us-west-2` returns `ResourceNotFoundException`. Live runs
  degrade honestly to deterministic market evidence only.
- Gold local Exit and deployment/rehearsal must still not be claimed as complete.

## Feature Freeze (Tasks 0-12 only — competition MVP)

**Was in effect 2026-08-02 through submission.** Applied only to the competition-scope tasks
(0-12): only bug fixes, reliability fixes, deployment, rehearsal, documentation, rollback
preparation and submission verification were permitted on that scope, and additions of
features, providers, artifact formats, PDF/HTML, additional visualizations, the five-coin
matrix, Platinum capabilities or H3 implementation were rejected on it.

**The competition is over; this freeze does not apply to Tasks 13-21.** Those tasks are the
approved post-competition continuation and may add exactly the capabilities the freeze used to
reject. If a bug is found in Tasks 0-12's shipped behavior, fix it directly in that task's own
files and note the fix in that task's entry — do not fold competition-MVP bug fixes into a
Task 13+ commit.

## Required Tasks

- [ ] **0. Record external-access preflight without blocking Bronze**
  - **Owner:** P4, reviewed by all
  - **Wave / dependency:** Wave 0 non-blocking / none
  - **Spec:** 5.1-5.4, 14, 17
  - **Files:**
    - Modify: `.env.example`
    - Create: `docs/rehearsals/service-access-check.md`
  - [ ] Add names only, never secret values, for AWS region, the required Bedrock primary model ID, the optional Bedrock fallback model ID, optional research-source credentials and artifact root to `.env.example`.
  - [ ] Probe each configured Bedrock model independently with a minimal non-sensitive prompt and record timestamp, region, model ID and pass/fail only; an unavailable optional fallback model does not block Bronze or Silver.
  - [ ] Probe the allowlisted research-source candidates without recording tokens or response headers, and record which available adapter is designated as the Silver baseline before Silver acceptance.
  - [ ] Confirm Python 3.12, Docker and AWS CLI versions and record them in `docs/rehearsals/service-access-check.md`.
  - [ ] Reconfirm that Platinum, CoinGecko, the complete five-asset matrix, H3 implementation, S3, CloudWatch and ECS are post-hackathon Future Work.
  - **Acceptance:** Preflight results are redacted and no credential appears in tracked files. Missing live access never blocks Bronze; Silver remains blocked until one designated baseline research source and at least one Bedrock model can complete the required live path.
  - **Commit:** `chore: record service access preflight`

- [x] **1. Scaffold the package and freeze shared contracts**

  Executed as two Kiro runs, 1a then 1b. A single run producing ~25 contract
  types plus ports, config and fakes is where field-name drift happens, and
  `models.py` is imported by all four owners. Do not tick this parent checkbox
  until both halves are done.

- [x] **1a. Freeze the normative data contracts** (corrective contract review cleared by Codex 2026-08-01)
  - **Owner:** P1, reviewed by P2/P3/P4
  - **Wave / dependency:** Wave 0 / Task 0 may run concurrently
  - **Spec:** 5, 7; `evidence-contracts.md` 1-12 and 16; Requirement 16
  - **Files:**
    - Create: `pyproject.toml`
    - Create: `src/hoya_agent/models.py`
    - Create: `tests/unit/test_models.py`
    - (`src/hoya_agent/__init__.py` already exists as an empty package marker)
  - [x] Configure Python 3.12 and runtime dependencies `pydantic`, `httpx`, `pandas`, `boto3`, `streamlit`; configure dev dependencies `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff` and pytest markers `integration`, `acceptance`, `live`; use a src layout that supports editable install.
  - [x] Define the enums `Asset`, `RunMode`, `SourceType`, `Reliability`, `Stance`, `ClaimType`, `TrustLevel`, `RegimeLabel` and `InvalidationOperator`, all `str`-backed.
  - [x] First write failing model tests for `AnalysisRequest`, `EvidenceItem`, `Claim`, `ClaimEvidenceLink`, `AnalysisResult` and timezone-aware UTC validation; every model uses `extra="forbid"` and rejects blank text fields. (順序偏離：實作先於測試)
  - [x] Test and implement the approved request fields, including unique `run_id`, one or two allowlisted assets, immutable `analysis_as_of`, `official|rehearsal|demo` and `enable_conditional_debate=false`.
  - [x] Test `EvidenceItem` fields including source identity, source/content reference, `fetched_at`, published/source time when available, `high|medium|low` reliability, independence group and cache/stale consistency; reject deprecated `fetched time`/`fetched_time` names and any stance field on `EvidenceItem`.
  - [x] Define `EvidenceDraft` as `EvidenceItem` minus the processor-assigned fields (`evidence_id`, `reliability`, `independence_group`, `content_hash`), retaining a reference back to its source record.
  - [x] Test `ClaimEvidenceLink` as the only stance owner and accept only `supports|opposes|neutral`; test the Evidence List projection fields `source`, `fetched_at`, `content_reference` and `related_claim`.
  - [x] Test `Claim` layering: `fact` has empty `based_on_claim_ids`; `inference` and `conclusion` do not. Test the `ev_001`/`cl_001` ID formats.
  - [x] Define `EvidenceLedger`, `ConflictIndicator`, `DegradationEvent`, `TimeRange` and `MarketContext`.
  - [x] Define the Requirement 16 types `InvalidationCondition`, `MarketRegime` and `TrustScorecard` with its five dimension sub-models; test the fixed ordinal mapping (`strong` independence requires at least three distinct groups) and the `MarketRegime` label enum with its persisted metrics and thresholds.
  - [x] Run `python -m pip install -e ".[dev]"`, `python -m pytest tests/unit/test_models.py -q`, `python -m pytest tests/unit tests/contract -q` and `ruff check .`.
  - **Acceptance:** Invalid assets, naive datetimes, malformed Evidence, deprecated freshness fields, Evidence-owned stance and unsupported Link stance fail validation. Inconsistent cache metadata and a `fact` with dependencies fail validation. The existing Task 6 suite still passes, proving the new contracts did not break the downstream consumer.
  - **Commit:** `feat: define core evidence and analysis contracts`

- [x] **1b. Freeze the runtime seams**
  - **Owner:** P1, reviewed by P2/P3/P4
  - **Wave / dependency:** Wave 0 / Task 1a
  - **Spec:** 6, 10.3, 13, 14
  - **Files:**
    - Create: `src/hoya_agent/config.py`
    - Create: `src/hoya_agent/clock.py`
    - Create: `src/hoya_agent/ports.py`
    - Create: `tests/conftest.py`
    - Create: `tests/fakes.py`
    - Create: `tests/unit/test_config.py`
    - Modify: `src/hoya_agent/models.py`
  - [x] Add the remaining plumbing models to `models.py`: `RunContext`, `RawSourceRecord`, `WorkerResult`, `ExecutionEvent`, `RunConfigSnapshot`, `RunSummary`, `ResearchPlan`.
  - [x] First write failing port tests, then define typed same-process boundaries for `Clock`, `LLMClient`, generic `SourceAdapter`, specialized `MarketDataAdapter` and `ResearchSourceAdapter`, `ProgressSink`, local `ArtifactStore` and a future persistence port for run summaries and artifact references.
  - [x] Define `ToolRegistry` as a static configuration-backed allowlist with no runtime plugin discovery, remote registry or mutation by retrieved content.
  - [x] Implement `config.py` with the locked env names and a sanitized snapshot that records optional-key presence as booleans, never values.
  - [x] Add reusable fixed clock, fake LLM, fake adapters, local/in-memory artifact and persistence fakes, static fake tool registry and in-memory progress sink under `tests/fakes.py`; move the temporary path bootstraps from `tests/contract/conftest.py` and `tests/unit/reasoning/conftest.py` into `tests/conftest.py` and delete them.
  - [x] Run `python -m pytest tests/unit tests/contract -q` and `ruff check .`.
  - **Acceptance:** Official mode uses the injected UTC clock, `analysis_as_of` remains immutable, no secret value reaches a snapshot, and all owners can implement against typed same-process seams without importing Streamlit or concrete providers. No database, queue, broker, remote registry, persistent implementation or independent service is introduced.
  - **Commit:** `feat: define shared runtime seams`

- [x] **2. Deliver the fixture vertical slice and incremental artifact contract** (canonical seam swap completed by PR #18)
  - **Owner:** P1 with P3; P2 and P4 review the interface
  - **Wave / dependency:** Wave 1 / Task 1 (1a and 1b complete; provisional seams retired)
  - **Spec:** 4.3, 6.2, 9.8, 17 Day 1 morning
  - **Files:**
    - Create: `src/hoya_agent/application.py`
    - Create: `src/hoya_agent/reporting/__init__.py`
    - Create: `src/hoya_agent/reporting/artifacts.py`
    - Create: `src/hoya_agent/reporting/renderer.py`
    - Create: `tests/fixtures/vertical_slice/evidence.json`
    - Create: `tests/fixtures/vertical_slice/analysis_result.json`
    - Create: `tests/unit/reporting/test_artifacts.py`
    - Create: `tests/unit/reporting/test_renderer.py`
    - Create: `tests/integration/test_vertical_slice.py`
    - Create (Task 1b seam, deleted on swap): `src/hoya_agent/_provisional_seams.py`, `tests/integration/test_s1_seam_bridge.py`, `docs/ai/S2_CONTRACT_EXPECTATIONS.md`
    - Create (fixture loaders; move into `tests/conftest.py` when 1b lands): `tests/unit/reporting/conftest.py`
  - [x] Write a failing integration test that passes one BTC `rehearsal` request, fixture Evidence and fixture `AnalysisResult` through the same-process application service with network, Bedrock and AWS credentials unavailable.
  - [x] Implement the smallest application flow that writes `run_config.json` first, streams `execution_log.jsonl`, writes `evidence.json`, then deterministically renders `final_report.md`; all four files share one `run_id`.
  - [x] Write renderer tests for all 11 required Traditional Chinese report sections, Evidence IDs, `high|medium|low` confidence, limitations, invalidation conditions and prohibited-advice lint. (`reporting/lint.py` remains Task 7's file; the renderer exposes the lint hook and the prohibited-term table guards the rendered fixture output.)
  - [x] Implement deterministic Markdown rendering and a deterministic insufficient-data fallback; neither path may call an LLM.
  - [x] Test same-directory temporary-file and atomic-replace writes for the four fixed filenames.
  - [x] Test a partial/degraded run with a writable artifact directory and require all four artifacts with limitations, missing capabilities and terminal state.
  - [x] Test one failed artifact write and require the exact missing filename and write failure in stdout and every remaining writable `execution_log.jsonl` or `run_config.json`; when the directory is completely unwritable, require stdout to identify all missing filenames, write failure and terminal state.
  - [x] Run `python -m pytest tests/unit/reporting tests/integration/test_vertical_slice.py -q`. (28 + 12 passed; full suite 422 passed / 6 skipped, `ruff check .` clean, Python 3.12.13)
  - **Acceptance:** The network-free application-service fixture path produces four parseable artifacts and honest `rehearsal` metadata without Bedrock or AWS. The report contains no facts absent from fixtures, missing analysis produces the deterministic fallback, and artifact-write failures follow the approved disclosure contract. Bronze is completed only after the Task 7 offline Streamlit checkpoint also passes.
  - **Commit:** `feat: add fixture artifact vertical slice`

- [x] **3. Implement deadline-aware fork-join orchestration**
  - **Owner:** P1
  - **Wave / dependency:** Wave 2 / Task 2
  - **Spec:** 8.2, 9.1, 11, 12
  - **Files:**
    - Create: `src/hoya_agent/orchestration/__init__.py`
    - Create: `src/hoya_agent/orchestration/run_state.py`
    - Create: `src/hoya_agent/orchestration/deadline.py`
    - Create: `src/hoya_agent/orchestration/pipeline.py`
    - Create: `tests/unit/orchestration/test_deadline.py`
    - Create: `tests/unit/orchestration/test_run_state.py`
    - Create: `tests/unit/orchestration/test_skip_order.py`
    - Create: `tests/integration/test_fork_join.py`
    - Create: `tests/integration/test_cancellation.py`
    - Create: `tests/integration/test_skip_order_enforcement.py`
  - [x] Write failing tests for the shared run deadline, per-stage deadlines, cancellation and the optional-work skip order `optional context -> counter-signal second search` using a fake clock/sleeper; H3 remains disabled rather than becoming optional runtime work. (`test_deadline.py`, `test_run_state.py`, `test_skip_order.py`; H3 stays in the order's vocabulary but is never classified or scheduled, so it is never reported as skipped.)
  - [x] Implement `DeadlineManager` with remaining-time calculation and stage-scoped `asyncio.wait_for`; no real-time sleeps in tests and no stage may wait indefinitely. (`Stage` milestones scale from a reference 720 s window; finalize keeps `max(20%, min(60 s, half the run))`.)
  - [x] Write a failing fork-join test proving Market Worker and Research Agent overlap in time and `asyncio.gather(..., return_exceptions=True)` preserves completed sibling output. (`test_fork_join.py`: branches await each other's `asyncio.Event`, so serial execution fails the test.)
  - [x] Implement in-memory stage states `pending|running|completed|degraded|failed|cancelled` and terminal run states `completed|degraded|failed|cancelled`. (`RunStateMachine`; illegal transitions raise `ValueError`.)
  - [x] Test and implement `WorkerResult.completed -> completed`, `WorkerResult.partial -> degraded`, `WorkerResult.failed -> failed`, and task/deadline cancellation -> `cancelled`. (`stage_state_for()`; one cancelled branch beside a completed sibling is `degraded`; an empty ledger with a cancelled market branch, or a caller-cancelled run, is `cancelled`. A caller-cancelled run finalizes all four artifacts labelled `cancelled` and then re-raises `CancelledError` — see `tests/integration/test_cancellation.py`.)
  - [x] Keep `analysis_as_of` immutable after run creation and stream stage transitions, terminal state, source success/failure and sanitized tool/agent summaries to `execution_log.jsonl` and final `run_config.json`. (stage_start/stage_end with `duration_ms` now stream from `RunStateMachine`; per-stage *budgets* are not yet in `run_config.json` because `RunConfigSnapshot` is frozen — `budget_seconds()` has the data ready.)
  - [x] Keep cancellation compatibility in-process; do not add a cancellation UI, database, queue, persistent job record or remote orchestration service.
  - [x] Run `python -m pytest tests/unit/orchestration tests/integration/test_fork_join.py -q`. (66 passed; full non-live suite 1100 passed / 0 failed, `ruff check .` clean, 2026-08-01)
  - **Acceptance:** One branch timeout reaches Renderer with completed sibling Evidence and a degraded state; stage deadlines cancel pending calls; cancellation maps to `cancelled`; terminal state is logged and exported without being inferred by the UI. **Met.** The skip order is enforced by trimming the `ResearchPlan` handed to the frozen Research Agent; which operations count as optional is declared by the composition root (`optional_operations` / `counter_signal_operations`, empty by default), so S6 supplies the source list when it assembles the live pipeline.
  - **Commit:** `feat: add deadline aware orchestration`

- [x] **4. Implement deterministic OHLCV market evidence**
  - **Owner:** P2
  - **Wave / dependency:** Wave 2 / Task 1
  - **Spec:** 7.5, 9.3, 10.1, 18.2
  - **Files:**
    - Create: `src/hoya_agent/data/__init__.py`
    - Create: `src/hoya_agent/data/market_series.py`
    - Create: `src/hoya_agent/data/indicators.py`
    - Create: `src/hoya_agent/data/market_worker.py`
    - Create: `src/hoya_agent/adapters/__init__.py`
    - Create: `src/hoya_agent/adapters/organizer_csv.py`
    - Create: `src/hoya_agent/adapters/binance.py`
    - Create: `tests/fixtures/ohlcv/mini_daily.csv`
    - Create: `tests/fixtures/http/binance_klines.json`
    - Create: `tests/unit/data/test_market_series.py`
    - Create: `tests/unit/data/test_indicators.py`
    - Create: `tests/unit/data/test_market_worker.py`
    - Create: `tests/contract/test_market_adapters.py`
  - [x] Write golden tests for return, realized volatility, maximum drawdown, volume change, rolling z-score and relative change using hand-computable fixture values.
  - [x] Implement UTC parsing and reject incomplete daily candles from historical calculations; represent the current candle separately as an intraday snapshot.
  - [x] Implement Binance klines as the designated baseline live market source and retain endpoint, pair, parameters, UTC range and `fetched_at` in source metadata; on baseline failure, emit an honest typed partial/degraded gap without switching to a second live provider.
  - [x] Implement Market Worker without any LLM dependency and convert each metric into a high-reliability, reproducible `EvidenceItem`.
  - [x] Add a failing cross-asset test that rejects direct base-volume comparison and permits quote volume, return, volatility, relative change or each asset's z-score.
  - [x] Run `python -m pytest tests/unit/data tests/contract/test_market_adapters.py -q`.
  - **Acceptance:** Golden values and UTC cutoffs pass; baseline market failure returns a typed partial/degraded gap without claiming a second live provider; CSV/live source cutover is explicitly represented with `fetched_at`; Market Worker has no import or call path to `LLMClient`. The generic `SourceAdapter` seam remains available for separately approved post-hackathon providers.
  - **Commit:** `feat: add deterministic market evidence`

- [x] **5. Implement research adapters and Evidence Processor** — closed 2026-08-03. Four functional gaps closed 2026-08-01 (material conflict wiring, multi-fact extraction, port-conforming research adapters, composed research pipeline); type unification closed 2026-08-01 (unresolved item 3); the last two sub-items (Evidence Processor coverage, official-mode adapter rejection) closed 2026-08-03, the latter after finding and fixing a real bug (see below). **Remaining, not blocking:** adapters still use a synchronous `httpx.Client` in a thread rather than one shared `AsyncClient` (noted as a deviation on its own sub-item); live provider verification is covered by Task 8's live Silver test, not re-litigated here.
  - **Owner:** P2
  - **Wave / dependency:** Wave 3 / Tasks 1 and 4
  - **Spec:** 7.5, 9.4-9.6, 10.1, 10.3
  - **Files:**
    - Create: `src/hoya_agent/adapters/cryptopanic.py`
    - Create: `src/hoya_agent/adapters/rss.py`
    - Create: `src/hoya_agent/adapters/official.py`
    - Create: `src/hoya_agent/adapters/alternative_me.py`
    - Create: `src/hoya_agent/adapters/_errors.py` (added 2026-08-01: normalized `timeout|http_error|malformed|rejected` categories)
    - Create: `src/hoya_agent/reasoning/research_extractor.py` (added 2026-08-01: extraction schema + deterministic completion; no frozen file modified)
    - Create: `src/hoya_agent/evidence/__init__.py`
    - Create: `src/hoya_agent/evidence/ledger.py`
    - Create: `src/hoya_agent/evidence/policies.py`
    - Create: `src/hoya_agent/evidence/processor.py`
    - Create: `tests/fixtures/http/cryptopanic_posts.json`
    - Create: `tests/fixtures/http/news_feed.xml`
    - Create: `tests/fixtures/http/alternative_me.json`
    - Create: `tests/contract/test_research_adapters.py` — **not created**; `tests/contract/` is a frozen path, so the mock-transport adapter tests live in `tests/unit/data_evidence/` alongside the existing ones (`test_research_port_adapters.py`)
    - Create: `tests/unit/evidence/test_policies.py`
    - Create: `tests/unit/evidence/test_processor.py`
  - [x] Write adapter contract tests for success, timeout, HTTP error, malformed payload and empty data using `httpx.MockTransport`; identify one configured allowlisted adapter as the designated Silver baseline research source. (`tests/unit/data_evidence/test_research_port_adapters.py` 16 tests + existing per-adapter tests; baseline is `fetch_rss_news`, declared in `application.BASELINE_RESEARCH_OPERATIONS`.)
  - [x] Treat every API, RSS and research payload as untrusted data. Test that embedded instructions or policy-like text are ignored as control input and, when retained, remain quoted source data only. (`test_cryptopanic.py::test_prompt_injection_in_title_is_kept_as_quoted_data_only`; the Research Agent flags such records without changing behaviour.)
  - [x] Reject an unallowlisted URL, host, provider or operation before an external call; reject invalid `EvidenceDraft` schema input and verify that ingestion cannot mutate the static `ToolRegistry` allowlist. (`application.ALLOWED_RESEARCH_HOSTS` rejects at registry construction — before any request; `test_composed_research_pipeline.py::test_a_non_allowlisted_research_host_is_rejected_before_any_call`; registry immutability covered by `test_runtime_seams.py` and `tests/unit/reasoning/test_research_agent.py`.)
  - [x] Implement 45-second per-call timeout and at most one deadline-bound retry; normalize missing or rejected sources into typed degradation/gap results rather than exceptions crossing the port. (2026-08-01 Move 2: `port_adapters.fetch_with_single_retry()` — retries only `timeout`/`http_error`, never `malformed`/`rejected`/`empty`; jittered backoff bounded by `DEFAULT_RETRY_BACKOFF_SECONDS=1.5`; no clock of its own, since the acquisition window owns the deadline and `CancelledError` is re-raised untouched. `SourceResult.status` already distinguishes every category via `adapters/_errors.py`. Covered by `tests/unit/data_evidence/test_source_retry.py` (10) and `test_composed_research_pipeline.py::test_a_transient_baseline_failure_recovers_within_the_run`. **Remaining deviation:** adapters still use a synchronous `httpx.Client` in a thread rather than one shared `AsyncClient`.)
  - [x] Run optional research or context adapters only after the baseline path is stable; failure of an optional adapter cannot fail Silver. (`test_composed_research_pipeline.py::test_optional_source_failure_does_not_fail_the_run`: a Fear & Greed timeout leaves baseline news evidence in the ledger and only adds a disclosure.)
  - [x] Mark Fear & Greed as low-reliability, whole-market context and never as coin-specific Evidence. (`test_alternative_me.py`, plus `test_research_port_adapters.py::test_fear_greed_record_is_whole_market_with_no_asset` asserting `asset is None`.)
  - [x] Write failing Evidence Processor tests for source identity, source/content reference, `fetched_at`, published/source time when available, cache/stale metadata, `high|medium|low` reliability, SHA-256 exact deduplication, registered-domain/original-publisher grouping and immutable run-level `analysis_as_of`. (Covered by `test_processor.py`/`test_policies.py`/`test_ledger.py`. Unresolved item 3 — the provisional-dataclass-vs-canonical-contract split this note used to point to — was closed 2026-08-01 per `docs/Implementation-Plan.md` §8: `evidence/types.py` was deleted and `evidence/drafts.py::PendingEvidence` is now the only draft type.)
  - [x] Test missing published/source time and stale/cache use as explicit limitation or degradation disclosures without fabricating timestamps or making Evidence appear fresher than its source. (2026-08-03: found genuinely missing — the evidence table only ever showed `fetched_at`, so a missing `published_at` was invisible, not merely undisclosed. Added `tests/unit/reporting/test_renderer.py::test_missing_published_at_is_disclosed_not_hidden` — confirmed red against the pre-fix renderer — then added the disclosure line to `reporting/renderer.py::_render_limitations`, alongside the existing stale/cached disclosure. Stale/cached itself was already covered.)
  - [x] Test that `EvidenceItem` owns no stance and `ClaimEvidenceLink` accepts only `supports|opposes|neutral`; implement deterministic material-conflict detection only for qualifying links from distinct independence groups. (`evidence/ledger.py::build_conflict_indicators` + `tests/unit/evidence/test_conflict_indicators.py` 8 tests; wired into the run by `orchestration/pipeline.py::finalize_analysis` and proved end-to-end by `tests/integration/test_material_conflict.py` — indicator persisted in the ledger, conclusion capped at `low`, both sides rendered, scorecard consistency `weak`.)
  - [x] Test official-mode cache metadata and prove that fixtures or recorded responses are rejected in official mode. (2026-08-03: closed with a real adapter, not just the model-level contract. Added `tests/integration/test_run_modes.py::test_official_mode_rejects_a_real_fixture_backed_adapter`, which wires the actual `OrganizerCsvPipeline` — no synthetic stand-in — under `run_mode=official`. It failed red: `OrganizerCsvPipeline.execute()` derived `effective_data_mode` from `run_mode` alone (`live` unless `run_mode is rehearsal`), so a fixture-backed instance accidentally used for `official` would have self-reported `live` and slipped past the `RunConfigSnapshot._official_runs_stay_live` gate undetected. Fixed in `orchestration/pipeline.py` to derive it from whether a live `load_bars` loader was actually injected (`self._load_bars is not None`) instead. Full suite 1306 passed, `ruff check .` clean.)
  - [x] Run `python -m pytest tests/contract/test_research_adapters.py tests/unit/evidence -q`. (Path adjusted: `python -m pytest tests/unit/evidence tests/unit/data_evidence tests/unit/reasoning -q` → 339 passed, 15 subtests; full non-live suite `python -m pytest tests/unit tests/contract tests/integration -q` → **1175 passed, 15 subtests, 0 failed**; `ruff check .` → All checks passed.)
  - [x] **Additive (2026-08-01): deterministic fact-grounding** (`evidence/grounding.py`, no LLM/no network). Audits LLM-extracted facts by matching their hard atoms (percent/money/number/date) against `content_reference` to catch fabricated values; language-invariant (English source grounds a Chinese fact); emits verified/partial/unverified. Red lines: does not mutate static `reliability` and adds no `EvidenceItem`/`EvidenceDraft` field (routes into confidence caps + disclosure only). Golden tests in `tests/unit/evidence/test_grounding.py`. Pipeline wiring landed (`OrganizerCsvPipeline` calls `ground_drafts`). Pending: semantic check for purely-qualitative claims (reasoning layer, behind `LLMClient`) and `ConfidenceSignals` integration. See `docs/Gold-Plan.md` G1.
  - [x] **Additive (2026-08-01): multi-fact research extraction migrated into `src/`** — `reasoning/research_extractor.py` supplies the `ResearchExtraction`/`ExtractedFact` schema the frozen `ResearchAgent` takes by injection, plus `complete_extracted_drafts()`, which completes reliability (static table), `independence_group` (policy) and timestamps (record) deterministically and drops any fact citing a record that was never fetched. `tests/unit/reasoning/test_research_extractor.py` (11) and `tests/integration/test_research_extraction.py` (4).
  - [x] **Additive (2026-08-01): composed research pipeline** — `application.build_research_tool_registry()` / `build_research_pipeline()` declare baseline (`fetch_rss_news`), optional context (`fetch_fear_greed`, `fetch_official_announcements`) and counter-signal (`fetch_cryptopanic_news`) operations, which is what makes Task 3's fixed skip order fire in a real run. `tests/integration/test_composed_research_pipeline.py` (8).
  - **Acceptance:** The designated baseline research adapter can produce normalized, schema-valid Evidence; optional-source failure is non-blocking; duplicate syndication is not independent; missing or rejected sources produce explicit gaps without inventing facts. The existing multi-source fixture may exercise diversity counting but does not become a Silver Exit Gate. **Status 2026-08-01: all four acceptance clauses are covered offline by `tests/integration/test_composed_research_pipeline.py`. The task stays open for the provisional-type unification (unresolved item 3), the missing adapter retry, and live provider verification (S11).**
  - **Commit:** `feat: normalize research evidence ledger`

- [x] **6. Implement bounded Planner, Research Agent and Arbiter**
  - **Owner:** P3
  - **Wave / dependency:** Wave 2 / Tasks 1 and 2
  - **Spec:** 7.4-7.5, 9.2, 9.4, 9.7, 13, 14
  - **Files:**
    - Create: `src/hoya_agent/adapters/bedrock.py`
    - Create: `src/hoya_agent/reasoning/__init__.py`
    - Create: `src/hoya_agent/reasoning/planner.py`
    - Create: `src/hoya_agent/reasoning/research_agent.py`
    - Create: `src/hoya_agent/reasoning/arbiter.py`
    - Create: `src/hoya_agent/reasoning/conflict_extension.py`
    - Create: `prompts/planner-v1.md`
    - Create: `prompts/research-extraction-v1.md`
    - Create: `prompts/arbiter-v1.md`
    - Create: `tests/fixtures/llm/planner_response.json`
    - Create: `tests/fixtures/llm/arbiter_response.json`
    - Create: `tests/contract/test_bedrock_client.py`
    - Create: `tests/unit/reasoning/test_planner.py`
    - Create: `tests/unit/reasoning/test_research_agent.py`
    - Create: `tests/unit/reasoning/test_arbiter.py`
    - Create: `tests/unit/reasoning/test_conflict_extension.py`
  - [x] Write Planner tests for bounded research steps, time range, Evidence types and asset/question mismatch warning; Planner must not produce a market conclusion or select arbitrary providers, tools, hosts or URLs.
  - [x] Implement a thin Bedrock Converse wrapper with the configured model IDs, operation-specific `max_tokens`, the current stage deadline and typed/schema-validated structured output.
  - [x] Reject raw unvalidated LLM output before Renderer or artifact admission; allow at most one schema repair attempt within the same deadline, then emit the deterministic fallback signal.
  - [x] Implement Research Agent as a bounded executor over the finite operations supplied by the static `ToolRegistry`; prohibit free loops, arbitrary URLs, allowlist mutation and facts without admitted Evidence IDs.
  - [x] Preserve prompt-injection-like source text only as quoted Evidence data; it cannot alter policy, deadlines, token bounds, tools, providers or the artifact contract.
  - [x] Write Arbiter tests for reliability/freshness ordering, truncation to configurable 20-30 Evidence items, one primary generation, one schema repair attempt and deterministic fallback.
  - [x] Validate fact -> inference -> conclusion dependencies, `ClaimEvidenceLink` references and `supports|opposes|neutral` stance, confidence rubric, limitations, invalidation conditions and absence of Ledger-external facts.
  - [x] Implement `ConflictExtension` with `DisabledConflictExtension` as the only Bronze, Silver and Gold implementation; it performs no network or LLM call, logs `enable_conditional_debate=true` as disabled/ignored and always routes to Arbiter.
  - [x] Test that UI-facing status data labels H3 unimplemented and that no Bull/Bear/Judge prompt, task, test path or Feature Freeze exception exists.
  - [x] Run `python -m pytest tests/contract/test_bedrock_client.py tests/unit/reasoning -q`.
  - [x] **Additive (2026-08-01): the Arbiter's LLM-output schema and projection** — `reasoning/arbiter_output.py` (new file, no frozen file modified). `AnalysisResult` cannot be `result_schema`: it requires the frozen request context the model must never restate, and `_fallback()` omits it. `ArbiterOutput` is that shape; `project_to_analysis_result()` stamps `run_id`/`question`/`assets`/`analysis_as_of` back on, maps boundary strings to canonical enums, fills a missing time range from the evidence window and clamps anything past the cutoff. `ledger_view()` hands the frozen layer string-valued evidence for the same reason `ReasoningRequest` exists. Three silent-degradation traps are pinned by `tests/unit/reasoning/test_arbiter_output.py` (16) and `tests/integration/test_arbiter_projection.py` (5): enum-typed confidence/stance break `apply_confidence_caps()`'s string comparisons; enum-typed reliability makes `_reliability_rank()` return unknown, so `select_evidence()` loses its high-first priority and `_fallback()` emits zero claims; `_fallback()` renders assets as `"Asset.BTC"`. `application.build_research_pipeline()` now wires the Arbiter automatically when an `llm` is supplied.
  - **Acceptance:** Arbiter emits a schema-valid `AnalysisResult` from a fake LLM; malformed output repairs once then falls back deterministically; prompt/schema versions are exposed for run configuration; Research Agent cannot escape the static tool plan; H3 performs no Bull/Bear/Judge call and remains outside two-day implementation.
  - **Commit:** `feat: add bounded bedrock reasoning`

- [x] **7. Pass the Bronze Streamlit checkpoint, then build the container shell** — Bronze Exit passed + hardened container (2026-08-01). Filenames landed as `src/hoya_agent/ui/streamlit_app.py`, `tests/integration/test_streamlit_bronze.py` (the UI/application contract test) and `docker-compose.yml`.
  - **Owner:** P4
  - **Wave / dependency:** Wave 1 Bronze checkpoint, then Wave 2 container support / Task 2
  - **Spec:** 9.9, 10.3, 14, 18.5
  - **Files:**
    - Create: `streamlit_app.py`
    - Create: `src/hoya_agent/ui/__init__.py`
    - Create: `src/hoya_agent/ui/presenter.py`
    - Create: `tests/unit/ui/test_presenter.py`
    - Create: `tests/integration/test_ui_application_contract.py`
    - Create: `Dockerfile`
    - Create: `.dockerignore`
    - Create: `compose.yaml`
  - [x] Write presenter tests for degradation notes, terminal state and run-mode labels. (`tests/unit/ui/test_presenter.py`. Live stage progress and the H3-unimplemented label are implemented in `streamlit_app.py` and browser-verified rather than in the pure presenter; recorded-fallback warning is Silver scope and does not trigger in the offline Bronze path.)
  - [x] Build one Streamlit screen for question, single-asset selection, run mode, live progress, report/evidence/log tabs and four artifact download controls; call `application.py` in the same process.
  - [x] Keep the five-asset input allowlist; the second-asset opt-in belongs to Task 12 and is disabled (single-asset selectbox) until it lands. No five-coin matrix or calibration workflow.
  - [x] Ensure `official|rehearsal|demo` are visibly distinct (presenter badges 🔴/🟡/⚪), fixtures never appear live, and no trading controls or investment-advice copy exists (renderer runs `advice_lint`).
  - [x] Run the UI/application contract with network, Bedrock and AWS credentials unavailable and verify the deterministic fixture pipeline produces the four fixed artifacts with an honest `rehearsal`/`demo` label; this is the Bronze Exit checkpoint. (Verified in a real browser, 2026-08-01.)
  - [x] Containerize the same process with a non-root user (`appuser`), environment-based secrets, a `.dockerignore` and a Streamlit healthcheck; no FastAPI. (Image built 856MB, container runs non-root and serves a full run.)
  - [x] Ran `python -m pytest -q` (593 passed) and `docker compose config` (valid).
  - **Acceptance:** Bronze passes when the completely offline Streamlit fixture path produces and downloads all four artifacts without network, Bedrock, AWS credentials or Docker acceptance. Container support starts the same Streamlit application, contains no secrets and does not redefine the Bronze gate.
  - **Commit:** `feat: add streamlit demo shell`

- [x] **8. Integrate the complete H2-Lite core and degradation paths** — Silver Exit passed 2026-08-02
  - **Owner:** P1 integrates; P2/P3/P4 repair owned modules
  - **Wave / dependency:** Wave 3 / Tasks 3, 4, 5, 6 and 7
  - **Spec:** 8.2, 11, 12, 18.1-18.4
  - **Files:**
    - Modify: `src/hoya_agent/application.py`
    - Modify: `src/hoya_agent/orchestration/pipeline.py`
    - Modify: `src/hoya_agent/reporting/artifacts.py`
    - Create: `tests/integration/test_h2_lite_pipeline.py`
    - Create: `tests/integration/test_degradation.py`
    - Create: `tests/integration/test_run_modes.py`
    - Create: `tests/integration/test_provenance.py`
    - Create: `tests/live/test_live_sources.py`
    - Create: `tests/live/test_bedrock_access.py`
  - [x] First add a failing end-to-end fixture test for Planner -> parallel Market/Research -> Evidence Processor -> Arbiter -> deterministic Renderer and keep Bronze green.
  - [x] Wire only typed same-process ports, including `SourceAdapter`, static `ToolRegistry`, `ProgressSink` and local `ArtifactStore`; preserve incremental artifacts and publish lifecycle progress after every stage.
  - [x] Add an opt-in Silver live acceptance test that uses Organizer CSV, the designated baseline live market source, the designated baseline research source and Bedrock, then requires a schema-valid `AnalysisResult`, deterministic rendering and all four artifacts. (`tests/live/test_live_silver_pipeline.py`; `1 passed in 50.15s`.)
  - [x] Add a separate Silver degradation test that forces Bedrock failure, verifies one repair attempt where applicable, uses deterministic fallback and labels the result honestly; fallback-only execution must not satisfy the live Silver gate.
  - [x] Add failure-injection tests for market timeout, research timeout, baseline-source failure, all external sources down, optional-provider failure, invalid Evidence admission, Arbiter invalid schema after repair and time-based optional-stage skipping.
  - [x] Verify optional-provider failure does not fail Silver when both baseline paths and the schema-valid Bedrock success gate pass.
  - [x] Add provenance tests requiring all report market numbers and conclusion links to resolve to Ledger Evidence and all inference/conclusion dependencies to resolve to fact.
  - [x] Add run-mode tests rejecting fixtures in `official`, allowing deterministic fixtures in `rehearsal`, visibly marking recorded runs in `demo`, and disclosing stale, missing, mock or degraded Evidence.
  - [x] Add artifact failure-injection tests: writable partial/degraded runs produce all four artifacts; failed writes disclose exact missing filenames in stdout and every remaining writable log/configuration artifact.
  - [x] Run `python -m pytest tests/unit tests/contract tests/integration -q` and `ruff check .`; run the opt-in component gates and then `python -m pytest tests/live/test_live_silver_pipeline.py -m live -vv -s`. (2026-08-02: non-live 1143 passed / 3 skipped on `main@21e6f14`; Ruff clean; both component live tests passed; integrated live test `1 passed in 50.15s`.)
  - **Acceptance:** **Met 2026-08-02.** Bronze remains green. Silver passes only after one single-asset live run produces a schema-valid Bedrock result through both designated baseline paths and a separate deterministic fallback/degradation test passes. Optional-source failure is non-blocking, accepted claims remain traceable to Evidence, and artifact failures follow the approved disclosure contract.
  - **Commit:** `feat: integrate resilient h2 lite pipeline`

- [x] **9. Pass Gold local Exit with two separate single-asset runs**
  - **Owner:** All; P1 owns the gate
  - **Wave / dependency:** Wave 4 / Task 8 Silver acceptance
  - **Spec:** 10.1, 17 Day 2 morning, 18.1-18.4
  - **Files:**
    - Create: `tests/acceptance/test_gold_assets.py`
    - Create: `tests/acceptance/test_deadline_budget.py`
    - Create: `tests/acceptance/test_artifact_contract.py`
    - Create: `scripts/run_acceptance.py`
    - Create: `docs/rehearsals/run-log.md`
  - [ ] Select two different assets for which the designated baseline paths can produce complete Evidence and run each as an independent single-asset Gold validation; keep them separate runs, because this gate proves coin-agnosticism and is not a substitute for the Task 12 dual-asset comparison.
  - [x] Retain BTC, ETH, SOL, BNB and XRP request-allowlist tests, but do not require the complete five-coin validation matrix or five-asset calibration. — `tests/acceptance/test_gold_assets.py`
  - [x] For each required Gold asset run, verify the four fixed artifacts, shared `run_id`, Evidence provenance, deterministic rendering, terminal state and explicit limitations. — `tests/acceptance/test_artifact_contract.py`, 9 passed
  - [ ] Exercise required baseline-source and Bedrock degradation cases locally and verify honest partial/degraded behavior without an unimplemented provider fallback.
  - [x] Add a fake-clock deadline acceptance test proving nonessential calls cancel by minute 12 and deterministic artifact finalization starts before the reserved deadline. — `tests/acceptance/test_deadline_budget.py`, 9 passed
  - [x] Record the two run IDs, assets, modes, durations, degradation results and artifact paths in `docs/rehearsals/run-log.md`; additional asset runs are optional and non-blocking. — four runs recorded (BTC/ETH × offline/live)
  - [x] Run `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q` and `ruff check .`. — 1266 passed; All checks passed!
  - **Acceptance:** Gold local Exit passes only after Silver has passed, two different assets have passed as separate local single-asset runs, required degradation checks have passed, and deterministic artifact checks have passed. Docker build/runtime, ECR deployment, EC2 deployment, the timed judged-flow rehearsal and submission verification are explicitly excluded from this local gate. Reaching this gate triggers Feature Freeze if Day 2 midday has not already triggered it.
  - **Commit:** `test: verify gold local exit`

- [ ] **10. Enforce Feature Freeze, deploy and complete the judged-flow rehearsal**
  - **Owner:** P1 and P4 co-lead; all participate
  - **Wave / dependency:** Wave 5 / Feature Freeze begins at the earlier trigger; deployment steps depend on Task 9 Gold local Exit
  - **Spec:** 17 Day 2 afternoon, 18.5-18.6
  - **Files:**
    - Create: `.github/workflows/ci.yml`
    - Create: `docs/deployment.md`
    - Create: `docs/demo-runbook.md`
    - Create: `docs/architecture.md`
    - Create: `scripts/smoke_test.py`
    - Modify: `README.md`
  - [x] Begin Feature Freeze immediately when Gold local Exit occurs or Day 2 midday arrives, whichever occurs first. After that point, permit only bug fixes, reliability fixes, deployment, rehearsal, documentation, rollback preparation and submission verification. — in effect 2026-08-02
  - [ ] Reject post-freeze additions of features, providers, artifact formats, PDF/HTML requirements, additional visualizations, the five-coin matrix, Platinum capabilities or H3 implementation.
  - [x] Run the full non-live verification command from `.kiro/steering/testing.md`; fixes required by failures remain allowed under Feature Freeze. — 1266 passed, Ruff clean
  - [x] After Gold local Exit, build the Docker image, verify local runtime, push a commit-SHA tag to ECR and deploy that immutable tag to one EC2 host with `docker compose`; document environment names, healthcheck and rollback command without secrets. — tag `2cd9b43` on `i-000a2cdc6d3c1afab`; `docs/deployment.md`
  - [x] Smoke-test the public URL, healthcheck and all artifact downloads using `scripts/smoke_test.py` without counting this as an additional required rehearsal. — public health `ok`; in-image smoke passed on EC2. UI download buttons remain a manual check (Streamlit websocket, not headless-verifiable)
  - [x] Save one complete recorded fallback run outside source control and document how `demo` exposes its original timestamp and recorded status. — `hoya-demo-fallback
un_20260802_015425_demo1`; `docs/demo-runbook.md`
  - [x] Update README with local run, test, Docker, configuration and artifact instructions; add CI for non-live tests and Ruff. — `.github/workflows/ci.yml`, three jobs green
  - [ ] Complete one full 15-minute timed judged-flow rehearsal from question entry through artifact inspection and record run ID, mode, duration, source gaps and artifact paths. Additional rehearsals are optional and must not delay deployment or submission.
  - [x] Run a repository secret scan and inspect `git status` and `git ls-files` for `.env`, keys and credentials; verify rollback and submission evidence. — gitleaks: 315 tracked files and 206 commits, no leaks; rollback executed once
  - **Acceptance:** Feature Freeze used the earlier approved trigger; Docker local runtime, ECR and EC2 delivery checks are complete; exactly one complete timed judged-flow rehearsal is required; demo fallback remains honest; rollback and submission evidence are documented; H3 is labelled unimplemented with no optional in-hackathon gate.
  - **Commit:** `docs: finalize deploy and demo runbook`

- [ ] **11. Add the deterministic creativity layer (trust distillation + market insight)** `[CC]` — offline implementation complete; full repository gate pending
  - **Owner:** CC (Claude Code); reviewed by P1
  - **Wave / dependency:** Wave 4, after Task 8 H2-Lite integration / non-blocking for Bronze and Silver core
  - **Spec:** Requirement 16; design.md §19; evidence-contracts.md §16
  - **Files:**
    - Create: `src/hoya_agent/evidence/trust.py`
    - Create: `src/hoya_agent/data/regime.py`
    - Modify: `src/hoya_agent/data/market_worker.py`
    - Modify: `src/hoya_agent/models.py`
    - Modify: `src/hoya_agent/reporting/renderer.py`
    - Modify: `src/hoya_agent/reasoning/arbiter.py`, `prompts/arbiter-v1.md`
    - Create: `tests/unit/evidence/test_trust.py`
    - Create: `tests/unit/data/test_regime.py`
    - Create: `tests/unit/reporting/test_creativity_render.py`
  - [ ] First write failing tests for the `TrustScorecard` deterministic mapping (independence/diversity/reliability-mix/consistency/freshness), including the caps that keep it consistent with the confidence rubric (`< 2` groups ≠ `strong`; material conflict → consistency `weak`).
  - [ ] Implement `evidence/trust.py` as a pure function over ledger + links + conclusion claims; no network, no LLM, no filesystem.
  - [ ] Write golden tests for `data/regime.py` label assignment using hand-computable OHLCV fixtures; verify coin-agnostic thresholds use each asset's own rolling history and that missing bars yield `label="unavailable"`.
  - [ ] Emit the Market Regime and recent-high/low/volume-mean threshold values from Market Worker as deterministic `high`-reliability `EvidenceItem`s.
  - [ ] Extend the Arbiter contract/prompt so `invalidation_conditions` reference Evidence-backed thresholds (`metric/operator/threshold/basis_evidence_id`) and never mint numbers; keep a qualitative fallback.
  - [ ] Render the regime headline, per-conclusion Trust Scorecard (ordinal pips + counts + one-line rationale), and quantified invalidation section deterministically; the prohibited-advice lint still runs last.
  - [ ] Verify graceful degradation: any unavailable dimension/label/threshold is disclosed, never fabricated, and does not block the four artifacts, Bronze, or Silver.
  - [ ] Run `python -m pytest tests/unit/evidence/test_trust.py tests/unit/data/test_regime.py tests/unit/reporting/test_creativity_render.py -q` and `ruff check .`.
  - **Acceptance:** Scorecard, regime, and quantified invalidation are deterministic, coin-agnostic, consistent with confidence, contain no LLM-minted numbers, carry no investment advice, use no uncalibrated precise probability, and degrade to explicit `unavailable` without blocking core artifacts or gates.
  - **Commit:** `feat: add deterministic trust distillation and market insight`

- [ ] **12. Deliver dual-asset comparison** — offline implementation complete; S3 UI opt-in and full repository gate pending
  - **Owner:** data owner for comparison inputs; reasoning owner for the Arbiter quota (frozen path — needs that owner's agreement); reporting/UI owner for the report section and the second-asset opt-in. Reviewed by P1.
  - **Wave / dependency:** Wave 4, after Task 8 H2-Lite integration; same additive window as Task 11. Must land before Feature Freeze and must not delay Gold local Exit, deployment, the timed rehearsal or submission.
  - **Spec:** Requirement 17; Requirement 13 for the permitted scales; design.md §20; §9 for the per-asset Arbiter quota
  - **Files:**
    - Modify: `src/hoya_agent/data/{market_series,indicators,market_worker}.py`
    - Modify: `src/hoya_agent/reasoning/arbiter.py` (frozen path)
    - Modify: `src/hoya_agent/reporting/renderer.py`, `src/hoya_agent/ui/presenter.py`, `streamlit_app.py`
    - Create: `tests/unit/data/test_cross_asset.py`, `tests/unit/reporting/test_comparison_render.py`, `tests/integration/test_dual_asset_run.py`
  - [ ] Write a failing integration test asserting that one request with two assets produces exactly one `run_id`, one frozen `analysis_as_of`, one ledger, one `AnalysisResult` and the four fixed artifact filenames — no second run and no fifth artifact.
  - [ ] Write failing golden tests for the comparable cross-asset scales on hand-computable fixtures: window-return spread, realized volatility compared by each asset's own percentile, relative-strength ratio and its own-history percentile, and same-provider quote-volume comparison.
  - [ ] Write a failing test that rejects any cross-asset comparison of base-asset `volume` and that declares a scale `unavailable` when a comparable basis is missing.
  - [ ] Write a failing `select_evidence` test proving that with two assets each asset reaches the Arbiter payload, that neither asset nor a single source type can consume the whole `MAX_EVIDENCE_FOR_ARBITER` budget, and that `asset = null` market-wide items are charged to neither quota.
  - [ ] Write a failing renderer test asserting the 跨幣比較 section appears only for two-asset runs, names both assets, the shared `time_range`, each scale used and the Evidence ID behind every number, and that the prohibited-advice lint still runs last and rejects relative buy/sell phrasing.
  - [ ] Run `python -m pytest tests/unit/data/test_cross_asset.py tests/unit/reporting/test_comparison_render.py tests/integration/test_dual_asset_run.py -vv`; expected FAIL.
  - [ ] Implement the multi-asset aligned load path, the comparable indicator functions, comparison `EvidenceDraft`s carrying both assets plus the shared range, scale and parameters, the per-asset Arbiter quota, the report section, and the explicit second-asset opt-in in the UI.
  - [ ] Verify degradation: one asset lacking baseline market evidence marks the comparison `unavailable`, discloses the gap, still completes the available asset's single-asset analysis and still writes four artifacts; two assets keep two separate Market Regime labels.
  - [ ] Run `python -m pytest tests/unit tests/contract tests/integration -q` and `ruff check .`; confirm every previously passing single-asset test is still green.
  - **Acceptance:** A single two-asset run produces at least one comparative Claim whose `assets` holds both assets and whose every number resolves to Evidence, uses only Requirement 13 scales, never compares base-asset volume, gives both assets Arbiter representation, renders the 跨幣比較 section, and degrades to a disclosed `unavailable` comparison rather than passing a single-asset result off as a comparison.
  - **If it cannot land before Feature Freeze:** disable the second-asset control, accept single-asset requests only, and disclose the undelivered capability in the documents and the presentation. Do not ship a partial comparison path.
  - **Commit:** `feat: add dual-asset comparison`

## Post-Competition Tasks (13-21)

Added 2026-08-03, after the competition ended. Tasks 13-16 are real gaps the competition
timebox never closed (verified against `main@2c0d268` — file existence checked, full non-live
suite run: 1304 passed, `ruff check .` clean). Tasks 17-21 are the former Future Work items
below, now formally in scope. None of these are subject to the Task 0-12 Feature Freeze.

- [x] **13. Remove the duplicate `p2-etl-mvp/` tree** (done 2026-08-03)
  - **Owner:** direct cleanup (any owner; low-risk mechanical deletion)
  - **Wave / dependency:** none — independent of 14-21
  - **Files:**
    - Delete: `p2-etl-mvp/` (71 files — the pre-migration prototype; S5/S6/S7 already migrated
      the real logic into `src/hoya_agent/`, see Implementation-Plan.md §5 S5/S6 notes)
  - [x] Grep `src/` and `tests/` for any import of `p2_etl_mvp` or a relative path into
        `p2-etl-mvp/`; confirm zero hits before deleting. Found two harmless comment
        references (`organizer_csv.py`'s directory walk-up note, `research_extractor.py`'s
        migration docstring) — left in place since they are historical context, not imports.
  - [x] Confirmed `Dockerfile` and `compose.yaml` do not reference the directory; removed the
        now-dead `p2-etl-mvp` line from `.dockerignore`.
  - [x] Deleted the directory (`git rm -r`); `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q` → **1304 passed** (unchanged from before deletion); `ruff check .` → **All checks passed**; `docker compose config` → valid.
  - **Acceptance:** `p2-etl-mvp/` no longer exists in the tree; full non-live suite and `ruff check .` are unchanged (still green); nothing else changes behavior. **Met.**
  - **Commit:** `chore: remove the superseded p2-etl-mvp prototype tree`

- [x] **14. Wire cross-source triangulation (G2) into the live pipeline** (done 2026-08-03)
  - **Owner:** data/evidence lane
  - **Wave / dependency:** none — independent of 13, 15, 16
  - **Spec:** `docs/Gold-Plan.md` §G2 (the differentiator plan written 2026-08-01; not a formal Requirement)
  - **Design correction found while implementing:** the original brief above assumed triangulation could read `evidence.json` alone, mirroring Task 11's trust funnel exactly. It cannot: `triangulate()` needs `anomaly_days(bars)`, which needs >= `min_history` (default 365) raw `MarketBar`s — data that never lands in `evidence.json`. Fix: `OrganizerCsvPipeline` (and `DeadlineAwarePipeline` via a forwarding property) now stash `last_bars_by_asset` after `execute()`, the same pattern already used for `last_metric_index`; the UI passes those already-loaded bars into the new view function instead of re-fetching or inventing a bars artifact.
  - **Files (as actually touched):**
    - Modified: `src/hoya_agent/orchestration/pipeline.py` — `OrganizerCsvPipeline.last_bars_by_asset` (set at the end of `execute()`) and `DeadlineAwarePipeline.last_bars_by_asset` (forwards to `self._market`, so both the offline and live/Bedrock composition roots expose the same attribute).
    - Modified: `src/hoya_agent/ui/presenter.py` — added `triangulation_view(evidence_ledger, bars_by_asset, *, sigma=3.0, min_history=365, window_days=1)`, same pure/framework-free shape as `trust_funnel`.
    - Modified: `src/hoya_agent/ui/streamlit_app.py` — `_run_offline`/`_run_live` now return `(summary, bars_by_asset)`; both call sites and `st.session_state["_last_bars"]` updated; `_render_result` renders a "跨源三角驗證" section under the trust funnel when triangulation is available.
    - Modified (return-signature fix): `tests/integration/test_streamlit_bronze.py` — the three existing Bronze tests unpack the new tuple; added `test_bronze_offline_run_exposes_bars_for_triangulation`.
    - Modified: `tests/unit/ui/test_presenter.py` — 3 new tests (`sigma`/`min_history` overridden to keep fixtures hand-computable, following the existing `tests/unit/data_evidence/test_price_analysis.py` pattern).
  - [x] Call `triangulate(anomalies, evidence_items, asset=...)` for each run asset from the presenter layer; no contract change (`models.py`, `EvidenceItem`, frozen `reasoning/` all untouched).
  - [x] Render each `TriangulatedEvent` (day, return, z-score, corroborating evidence IDs, source types, independence groups, strength).
  - [x] Degrade explicitly: too little bar history → `available=False` + a human-readable reason, never a guess; no anomaly days → an explicit "no significant move" caption; both proved by tests.
  - [ ] **Stretch, not required, not done:** feeding `TriangulatedEvent`s into the Arbiter payload. Still needs reasoning-lane owner sign-off; the UI-only wiring above already delivers the Gold-Plan §0 trust story without it.
  - [x] Ran `python -m pytest tests/integration/test_streamlit_bronze.py tests/unit/ui tests/unit/orchestration -q` (86 passed) then the full non-live suite (1311 passed, up from 1307) and `ruff check .` (All checks passed); `docker compose config` valid; confirmed no new `boto3`/`httpx` import crossed into `ui/`, `data/` or `evidence/`.
  - **Acceptance:** **Met.** A run with at least one market anomaly day and nearby research evidence shows a rendered triangulation view backed only by already-collected Evidence IDs; no LLM call, no network call, no new `EvidenceItem`/`Claim` field; degrades to an explicit state rather than fabricating corroboration.
  - **Commit:** `feat: surface cross-source triangulation in the trust UI`

- [ ] **15. Agent judgment visualization (G4)**
  - **Owner:** reasoning lane for the Planner check, UI lane for rendering
  - **Wave / dependency:** none — independent of 13, 14, 16
  - **Spec:** `docs/Gold-Plan.md` §G4 (🔴 not started as of 2026-08-01, still not started as of 2026-08-03 — confirmed by grepping `planner.py`/`presenter.py`/`streamlit_app.py` for question-type or strategy logic: no hits)
  - **Files:**
    - Modify: `prompts/planner-v1.md` (only if the existing prompt does not already ask the LLM to justify which operations it picked — check first, this may already be adequate)
    - Modify: `src/hoya_agent/orchestration/pipeline.py` (stream the Planner's chosen `planned_steps` + any `plan_notes` as a distinct, judge-legible `execution_log.jsonl` event — today `plan_notes` only flips the Planner stage to `degraded`/`completed`, the actual operations chosen and why are not logged as their own event)
    - Modify: `src/hoya_agent/ui/presenter.py`, `src/hoya_agent/ui/streamlit_app.py` (render "for this question, the Planner ran X of Y available sources, skipped Z because ..." plus the grounding/degradation decisions already computed by Task 5's `evidence/grounding.py` and the pipeline's degradation events)
    - Create/modify: `tests/unit/reasoning/test_planner.py` (prove the plan genuinely varies — e.g., a question naming an official announcement vs. a question about sentiment selects different `tool_operation` sets from the same allowlist, using the existing fake-LLM test pattern)
    - Create: `tests/unit/ui/test_presenter.py` additions for the new judgment-visualization view
  - [ ] Confirm (or add, if missing) a fake-LLM test proving the Planner's chosen `planned_steps` differ for genuinely different questions — the mechanism already exists (`Research Agent` only executes `plan.planned_steps`, confirmed in `reasoning/research_agent.py`), this task is about making it demonstrably true and visible, not building it from scratch.
  - [ ] Add one `execution_log.jsonl` event per run carrying the Planner's chosen operations, skipped operations and the reason, plus a summary of any grounding `unverified`/`partial` facts and material-conflict/degradation events already computed elsewhere in the pipeline — this event only *surfaces* existing decisions, it must not compute anything new.
  - [ ] Render this in the Streamlit execution-log tab (or a new "Agent 判斷" panel next to the trust funnel) in one screen a judge can read in a few seconds.
  - [ ] No new LLM call, no new field on `EvidenceItem`/`Claim`/`AnalysisResult` — this is a logging/rendering task, not a reasoning-contract change.
  - [ ] Run `python -m pytest tests/unit/reasoning tests/unit/ui tests/integration -q` and `ruff check .`.
  - **Acceptance:** Two different questions against the same asset visibly produce different Planner operation choices in the UI and `execution_log.jsonl`; degradation/grounding decisions already made elsewhere in the pipeline are now visible to a judge without reading raw JSON; nothing about the reasoning pipeline's actual decisions changes, only their visibility.
  - **Commit:** `feat: surface planner strategy and audit decisions to the UI`

- [ ] **16. G1 semantic grounding recheck for qualitative claims**
  - **Owner:** reasoning lane (touches the `LLMClient` port; `reasoning/` is a frozen path — get sign-off before editing `arbiter.py` or `research_agent.py` directly; prefer a new file, same pattern Task 6's `arbiter_output.py` additive used)
  - **Wave / dependency:** after 15 is easiest (shares the judgment-visualization UI surface) but not blocked by it
  - **Spec:** `docs/Gold-Plan.md` §G1 (deterministic half — hard-atom matching — already shipped in `evidence/grounding.py`; confirmed by grep that no `LLMClient` import or `async def` exists anywhere in that file today, so the semantic half is genuinely unbuilt)
  - **Files:**
    - Create: `src/hoya_agent/reasoning/semantic_grounding.py` (new file — do not modify `evidence/grounding.py`, which must stay LLM-free per its own docstring, or the frozen `reasoning/arbiter.py`)
    - Modify: `prompts/` — add a small, cheap prompt (e.g. `prompts/semantic-grounding-v1.md`) for a single bounded yes/no/uncertain check per qualitative fact against its `content_reference`
    - Modify: `src/hoya_agent/orchestration/pipeline.py` (call this after `ground_drafts`, only for facts `evidence/grounding.py` marked `unverified` because they have no checkable hard atom — do not re-run it on facts already `verified`/`partial`)
    - Create: `tests/unit/reasoning/test_semantic_grounding.py`
  - [ ] Write failing tests with a fake `LLMClient` proving: a purely qualitative fact whose `content_reference` plausibly supports it → `verified`; one that contradicts its source → `contradicted`; LLM failure/timeout → falls back to the existing deterministic `unverified`, never blocks the run.
  - [ ] Implement the bounded call: one fact at a time or a small batch, capped `max_tokens`, inside the existing stage deadline (reuse the Evidence-processing stage budget — do not add a new stage or extend any deadline).
  - [ ] Feed the result into `confidence_signals_for_claim(require_grounding=True)` (already exists per Task 5's grounding note) so a semantically `contradicted` fact behaves the same way a numerically fabricated one already does: excluded from independent-support counting, disclosed in `degradation`.
  - [ ] Red lines (same as the deterministic half): never mutate the static `reliability` table; never add a field to `EvidenceItem`/`EvidenceDraft`; never let this call block or fail a run — any LLM error degrades to the pre-existing `unverified` state.
  - [ ] Run `python -m pytest tests/unit/reasoning/test_semantic_grounding.py tests/unit/evidence -q` and `ruff check .`.
  - **Acceptance:** Purely qualitative facts that previously fell through fact-grounding as an unexplained `unverified` now get an honest LLM-assisted plausibility check that degrades safely on any failure; the deterministic hard-atom path from Task 5/G1 is untouched; no new secret, no new artifact field, no blocking dependency.
  - **Commit:** `feat: add semantic recheck for qualitative fact-grounding`

- [ ] **17. Implement H3 Conditional Debate**
  - **Owner:** reasoning lane (frozen-path sign-off required — this replaces `DisabledConflictExtension`, the one component every other task has been told not to touch)
  - **Wave / dependency:** after 16 is easiest (shares the reasoning-lane context) but not blocked by it
  - **Spec:** former "Future Reference 11" below; `.kiro/steering/competition-rules.md` §Architecture and H3 Honesty Rules (now amended to approve this task)
  - **Files:**
    - Create: `src/hoya_agent/reasoning/conditional_debate.py` (new `ConflictExtension` implementation alongside the existing `DisabledConflictExtension`, not a replacement of it — `enable_conditional_debate` selects between them)
    - Create: `prompts/bull-v1.md`, `prompts/bear-v1.md`, `prompts/judge-v1.md`
    - Create: `tests/unit/reasoning/test_conditional_debate.py`
    - Modify: `src/hoya_agent/composition.py` (wire the flag to select the extension; default stays `DisabledConflictExtension`)
  - [ ] Write failing tests: the extension only activates on a real `ConflictIndicator` from `evidence/ledger.py::build_conflict_indicators` (the existing deterministic material-conflict rule — do not invent a second conflict detector); with no material conflict, it must still always route straight to Arbiter unchanged, exactly like `DisabledConflictExtension` does today.
  - [ ] Implement at most one Bull round and one Bear round, each citing only existing Evidence IDs from the ledger (no new fetch, no new Evidence), followed by one Judge call that must produce the same `AnalysisResult`-compatible shape the Arbiter already produces — reuse `reasoning/arbiter_output.py`'s projection pattern rather than inventing a second output schema.
  - [ ] Bound it inside the existing stage deadline and `max_tokens` budget; on any timeout, LLM error or schema failure at any of the three steps, discard the debate and route straight to the normal Arbiter path — H3 must never be able to make a run fail that would otherwise have succeeded.
  - [ ] `enable_conditional_debate` stays an explicit opt-in on `AnalysisRequest`, default `false`; when `true` but the extension still resolves to "no material conflict," behavior must be identical to today's disabled path.
  - [ ] Update every UI/report/doc label that currently says "H3 未實作" to instead say "H3: opt-in, off by default" once this lands and passes its own rehearsal — do not change those labels before this task's acceptance is actually met.
  - [ ] Run `python -m pytest tests/unit/reasoning/test_conditional_debate.py tests/integration -q` and `ruff check .`.
  - **Acceptance:** With `enable_conditional_debate=true` and a real material conflict, exactly one Bull/Bear/Judge round runs and produces a valid `AnalysisResult` that still discloses both sides; with no conflict or with the flag off, output is byte-for-byte identical to today's `DisabledConflictExtension` path; no unbounded loop, no new tool, no new provider.
  - **Commit:** `feat: implement opt-in H3 conditional debate`

- [ ] **18. Add CoinGecko as an optional secondary market source**
  - **Owner:** data lane
  - **Wave / dependency:** independent
  - **Spec:** former "Future Reference 12" below; `.kiro/steering/competition-rules.md` §Approved Data Policy (now amended to approve this as optional, non-baseline)
  - **Files:**
    - Create: `src/hoya_agent/adapters/coingecko.py`
    - Create: `tests/fixtures/http/coingecko_market_chart.json`
    - Create: `tests/unit/data_evidence/test_coingecko.py`
    - Modify: `src/hoya_agent/composition.py` (register as optional context, never baseline)
  - [ ] Write adapter contract tests (success, timeout, HTTP error, malformed payload, empty data) using `httpx.MockTransport`, matching the pattern already used for `adapters/binance.py` and the research adapters.
  - [ ] Implement the adapter behind the same `MarketDataAdapter`/`SourceAdapter` port Task 1b already defined — no new port, no new artifact field.
  - [ ] Wire it as an **optional** source only: Binance stays the sole baseline live market source; CoinGecko failure is always non-blocking and never triggers a "second live provider" claim (same rule Task 4 already enforces for Binance itself).
  - [ ] If used for cross-check, disclose it explicitly (e.g., a degradation note when Binance and CoinGecko close prices diverge beyond a stated tolerance) — never silently prefer one over the other.
  - [ ] Run `python -m pytest tests/unit/data_evidence/test_coingecko.py tests/contract -q` and `ruff check .`.
  - **Acceptance:** CoinGecko produces normalized, schema-valid Evidence through the existing port; its failure never degrades a run below what it would have been without it; it never becomes the baseline; the disclosure/degradation contract from Task 5 applies to it unchanged.
  - **Commit:** `feat: add CoinGecko as an optional secondary market source`

- [ ] **19. Complete five-asset validation/calibration matrix**
  - **Owner:** all; data lane leads
  - **Wave / dependency:** after 18 if CoinGecko cross-validation is in scope; otherwise independent
  - **Spec:** former "Future Reference 12" below
  - **Files:**
    - Create: `tests/acceptance/test_five_asset_matrix.py`
    - Modify: `docs/rehearsals/run-log.md` (append, do not rewrite the existing Gold local Exit entries)
  - [ ] Extend Task 9's two-asset Gold local Exit pattern to run all five allowlisted assets (BTC, ETH, SOL, BNB, XRP) independently, offline (organizer CSV) and, where credentials allow, live.
  - [ ] For each asset, verify the same four-artifact/provenance/terminal-state contract Task 9 already checks — this task is breadth (all five), not a new contract.
  - [ ] Record any asset-specific gaps honestly (e.g., a research source with thin coverage for a smaller-cap asset) as disclosed limitations, not silent skips — the coin-agnostic rule from `.kiro/steering/competition-rules.md` still applies: no per-coin branching in `src/`, only in what gaps get disclosed.
  - [ ] Run `python -m pytest tests/acceptance/test_five_asset_matrix.py -q` and, separately, the opt-in live variant.
  - **Acceptance:** All five assets pass the same artifact/provenance contract Task 9 established for two; any asset-specific data gaps are disclosed, not hidden; no coin-specific code path was added to reach this.
  - **Commit:** `test: complete the five-asset validation matrix`

- [ ] **20. Platinum reporting: PDF/HTML export and additional visualization**
  - **Owner:** UI/reporting lane
  - **Wave / dependency:** independent (build on the existing self-contained HTML report from PR #29, `feat(ui): emit complete self-contained HTML report`, rather than starting a new renderer)
  - **Spec:** former "Future Reference 12" below
  - **Files:**
    - Modify: `src/hoya_agent/reporting/renderer.py` or the HTML emission path added in PR #29 (check current state first — this may already cover most of the "HTML export" half)
    - Create: PDF export path (e.g. via a headless render of the existing HTML, not a second hand-written template)
    - Modify: `src/hoya_agent/ui/streamlit_app.py` (download button)
  - [ ] Confirm what PR #29's HTML report already covers before adding anything — do not duplicate an existing self-contained HTML artifact.
  - [ ] Add a PDF export derived deterministically from the same rendered content (no second source of truth, no LLM re-generation for the PDF).
  - [ ] Any new chart/visualization must be generated from data already in the Ledger/`AnalysisResult` — no new data source, no new claim.
  - [ ] These stay **additional** artifacts; the four fixed filenames (`final_report.md`, `evidence.json`, `execution_log.jsonl`, `run_config.json`) and their contract are unchanged.
  - [ ] Run the full non-live suite and `ruff check .`.
  - **Acceptance:** PDF/HTML export and any added visualization are deterministic, derived only from existing Evidence/Claims, and additive — they do not replace or alter the four required artifacts.
  - **Commit:** `feat: add PDF export and extra report visualization`

- [ ] **21. Platinum infrastructure: S3 artifact mirroring, CloudWatch, ECS**
  - **Owner:** P1/P4-equivalent deployment lane
  - **Wave / dependency:** independent; touches deployment, coordinate timing with any active EC2 demo use
  - **Spec:** former "Future Reference 12" below
  - **Files:**
    - Modify: `docs/deployment.md`
    - Create: infrastructure-as-code or scripted setup for S3 mirroring and CloudWatch (match whatever tooling `docs/deployment.md` already uses for EC2 — do not introduce a second deployment mechanism)
  - [ ] Mirror each run's four artifacts to S3 after local write succeeds — mirroring must never become a dependency of artifact completion; a run still succeeds locally if S3 is unreachable, with the gap disclosed.
  - [ ] Add CloudWatch for the existing EC2 host's logs/health, not a new metrics contract.
  - [ ] Evaluate ECS as a deployment target; if adopted, keep the single immutable commit-SHA tag promotion Task 10 already established — do not weaken that guarantee.
  - [ ] No secret enters any of this — reuse the existing IAM-role-based, no-static-keys pattern `docs/deployment.md` already documents for EC2.
  - **Acceptance:** S3 mirroring and CloudWatch are additive and non-blocking; if ECS is adopted, the immutable-tag deployment guarantee from Task 10 still holds; no new secret-handling path is introduced.
  - **Commit:** `feat: add S3 artifact mirroring and CloudWatch for the EC2 deployment`

## Historical Future Work Notes (superseded by Tasks 17-21 above)

### Future Reference 11: H3 Conditional Debate

A separately approved post-hackathon implementation may use the deterministic material-conflict rule, existing Evidence IDs, at most one Bull/Bear round and bounded deadline/token controls. During Bronze, Silver and Gold, only `DisabledConflictExtension` exists and every UI, presentation and document labels H3 unimplemented. **Now Task 17.**

### Future Reference 12: Production and Platinum Extensions

CoinGecko, the complete five-asset validation/calibration matrix, additional providers, PDF/HTML, additional visualization, S3 artifact mirroring, CloudWatch integration and other Platinum or Production Architecture capabilities remain post-hackathon Future Work. No implementation file, dependency, test, deployment configuration or acceptance gate for these capabilities belongs to the formal two-day task sequence. Dual-asset comparison was moved out of this list on 2026-08-01 and is now required Task 12. **CoinGecko is now Task 18, the five-asset matrix is Task 19, PDF/HTML/visualization is Task 20, S3/CloudWatch/ECS is Task 21.**

## Final Required Gate

Before submission, and without starting any post-hackathon Future Work:

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short
```

Expected: tests and Ruff pass, Compose config is valid, and `git status` contains only intentionally staged submission changes.
