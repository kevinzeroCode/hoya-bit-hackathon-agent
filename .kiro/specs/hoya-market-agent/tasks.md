# HOYA Market Agent Implementation Tasks

> Product authority: `.kiro/specs/hoya-market-agent/requirements.md`
>
> Implementation authority: `.kiro/specs/hoya-market-agent/design.md`
>
> Historical product context and ownership guidance remain in `docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md` and `docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md`.
>
> Hard limit: four junior developers, two calendar days. H2-Lite is the only committed analysis method.
>
> Platinum, the CoinGecko live adapter, the complete five-asset validation/calibration matrix, H3 implementation, S3, CloudWatch and ECS are post-hackathon Future Work and are not executable tasks during the formal two-day delivery period.

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

## Current checkpoint (2026-08-01, main@d7245e4)

- Complete: Tasks 1, 2, 4 and 6.
- Core landed but acceptance remains open: Tasks 3 and 8.
- Mostly landed but canonical baseline acceptance remains open: Task 5.
- Offline implementation complete, repository-wide gates remain open: Tasks 11 and 12.
- Not complete: Tasks 0, 7, 9 and 10.
- Full pytest/Ruff, live Silver, Gold local Exit and deployment/rehearsal must not be claimed.

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

- [ ] **5. Implement research adapters and Evidence Processor** — majority landed; canonical baseline acceptance remains
  - **Owner:** P2
  - **Wave / dependency:** Wave 3 / Tasks 1 and 4
  - **Spec:** 7.5, 9.4-9.6, 10.1, 10.3
  - **Files:**
    - Create: `src/hoya_agent/adapters/cryptopanic.py`
    - Create: `src/hoya_agent/adapters/rss.py`
    - Create: `src/hoya_agent/adapters/official.py`
    - Create: `src/hoya_agent/adapters/alternative_me.py`
    - Create: `src/hoya_agent/evidence/__init__.py`
    - Create: `src/hoya_agent/evidence/ledger.py`
    - Create: `src/hoya_agent/evidence/policies.py`
    - Create: `src/hoya_agent/evidence/processor.py`
    - Create: `tests/fixtures/http/cryptopanic_posts.json`
    - Create: `tests/fixtures/http/news_feed.xml`
    - Create: `tests/fixtures/http/alternative_me.json`
    - Create: `tests/contract/test_research_adapters.py`
    - Create: `tests/unit/evidence/test_policies.py`
    - Create: `tests/unit/evidence/test_processor.py`
  - [ ] Write adapter contract tests for success, timeout, HTTP error, malformed payload and empty data using `httpx.MockTransport`; identify one configured allowlisted adapter as the designated Silver baseline research source.
  - [ ] Treat every API, RSS and research payload as untrusted data. Test that embedded instructions or policy-like text are ignored as control input and, when retained, remain quoted source data only.
  - [ ] Reject an unallowlisted URL, host, provider or operation before an external call; reject invalid `EvidenceDraft` schema input and verify that ingestion cannot mutate the static `ToolRegistry` allowlist.
  - [ ] Implement 45-second per-call timeout and at most one deadline-bound retry; normalize missing or rejected sources into typed degradation/gap results rather than exceptions crossing the port.
  - [ ] Run optional research or context adapters only after the baseline path is stable; failure of an optional adapter cannot fail Silver.
  - [ ] Mark Fear & Greed as low-reliability, whole-market context and never as coin-specific Evidence.
  - [ ] Write failing Evidence Processor tests for source identity, source/content reference, `fetched_at`, published/source time when available, cache/stale metadata, `high|medium|low` reliability, SHA-256 exact deduplication, registered-domain/original-publisher grouping and immutable run-level `analysis_as_of`.
  - [ ] Test missing published/source time and stale/cache use as explicit limitation or degradation disclosures without fabricating timestamps or making Evidence appear fresher than its source.
  - [ ] Test that `EvidenceItem` owns no stance and `ClaimEvidenceLink` accepts only `supports|opposes|neutral`; implement deterministic material-conflict detection only for qualifying links from distinct independence groups.
  - [ ] Test official-mode cache metadata and prove that fixtures or recorded responses are rejected in official mode.
  - [ ] Run `python -m pytest tests/contract/test_research_adapters.py tests/unit/evidence -q`.
  - [x] **Additive (2026-08-01): deterministic fact-grounding** (`evidence/grounding.py`, no LLM/no network). Audits LLM-extracted facts by matching their hard atoms (percent/money/number/date) against `content_reference` to catch fabricated values; language-invariant (English source grounds a Chinese fact); emits verified/partial/unverified. Red lines: does not mutate static `reliability` and adds no `EvidenceItem`/`EvidenceDraft` field (routes into confidence caps + disclosure only). Golden tests in `tests/unit/evidence/test_grounding.py`. Pending: pipeline wiring, semantic check for purely-qualitative claims (reasoning layer, behind `LLMClient`), and `ConfidenceSignals` integration. See `docs/Gold-Plan.md` G1.
  - **Acceptance:** The designated baseline research adapter can produce normalized, schema-valid Evidence; optional-source failure is non-blocking; duplicate syndication is not independent; missing or rejected sources produce explicit gaps without inventing facts. The existing multi-source fixture may exercise diversity counting but does not become a Silver Exit Gate.
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

- [ ] **9. Pass Gold local Exit with two separate single-asset runs**
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
  - [ ] Retain BTC, ETH, SOL, BNB and XRP request-allowlist tests, but do not require the complete five-coin validation matrix or five-asset calibration.
  - [ ] For each required Gold asset run, verify the four fixed artifacts, shared `run_id`, Evidence provenance, deterministic rendering, terminal state and explicit limitations.
  - [ ] Exercise required baseline-source and Bedrock degradation cases locally and verify honest partial/degraded behavior without an unimplemented provider fallback.
  - [ ] Add a fake-clock deadline acceptance test proving nonessential calls cancel by minute 12 and deterministic artifact finalization starts before the reserved deadline.
  - [ ] Record the two run IDs, assets, modes, durations, degradation results and artifact paths in `docs/rehearsals/run-log.md`; additional asset runs are optional and non-blocking.
  - [ ] Run `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q` and `ruff check .`.
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
  - [ ] Begin Feature Freeze immediately when Gold local Exit occurs or Day 2 midday arrives, whichever occurs first. After that point, permit only bug fixes, reliability fixes, deployment, rehearsal, documentation, rollback preparation and submission verification.
  - [ ] Reject post-freeze additions of features, providers, artifact formats, PDF/HTML requirements, additional visualizations, the five-coin matrix, Platinum capabilities or H3 implementation.
  - [ ] Run the full non-live verification command from `.kiro/steering/testing.md`; fixes required by failures remain allowed under Feature Freeze.
  - [ ] After Gold local Exit, build the Docker image, verify local runtime, push a commit-SHA tag to ECR and deploy that immutable tag to one EC2 host with `docker compose`; document environment names, healthcheck and rollback command without secrets.
  - [ ] Smoke-test the public URL, healthcheck and all artifact downloads using `scripts/smoke_test.py` without counting this as an additional required rehearsal.
  - [ ] Save one complete recorded fallback run outside source control and document how `demo` exposes its original timestamp and recorded status.
  - [ ] Update README with local run, test, Docker, configuration and artifact instructions; add CI for non-live tests and Ruff.
  - [ ] Complete one full 15-minute timed judged-flow rehearsal from question entry through artifact inspection and record run ID, mode, duration, source gaps and artifact paths. Additional rehearsals are optional and must not delay deployment or submission.
  - [ ] Run a repository secret scan and inspect `git status` and `git ls-files` for `.env`, keys and credentials; verify rollback and submission evidence.
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

## Post-Hackathon Future Work — Not Executable During Two-Day Delivery

The following entries preserve architecture intent only. They are not checkable implementation tasks, have no two-day entry gate, are prohibited after Feature Freeze and cannot block Bronze, Silver, Gold, deployment, rehearsal or submission.

### Future Reference 11: H3 Conditional Debate

A separately approved post-hackathon implementation may use the deterministic material-conflict rule, existing Evidence IDs, at most one Bull/Bear round and bounded deadline/token controls. During Bronze, Silver and Gold, only `DisabledConflictExtension` exists and every UI, presentation and document labels H3 unimplemented.

### Future Reference 12: Production and Platinum Extensions

CoinGecko, the complete five-asset validation/calibration matrix, additional providers, PDF/HTML, additional visualization, S3 artifact mirroring, CloudWatch integration and other Platinum or Production Architecture capabilities remain post-hackathon Future Work. No implementation file, dependency, test, deployment configuration or acceptance gate for these capabilities belongs to the formal two-day task sequence. Dual-asset comparison was moved out of this list on 2026-08-01 and is now required Task 12.

## Final Required Gate

Before submission, and without starting any post-hackathon Future Work:

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short
```

Expected: tests and Ruff pass, Compose config is valid, and `git status` contains only intentionally staged submission changes.
