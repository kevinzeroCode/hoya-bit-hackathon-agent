# HOYA Market Agent Implementation Tasks

> Source of truth: `docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md`
>
> Hard limit: four junior developers, two calendar days. H2-Lite is the only committed product. H3, S3, CloudWatch and ECS are optional and must never delay or destabilize the MVP.

## Execution Rules

- Execute waves in order. Tasks inside the same wave may run in parallel only after their dependencies are green.
- Every required behavior follows Red -> Green -> Refactor and `.kiro/steering/testing.md`.
- Do not use Kiro `Run All Tasks`. Start with the fixture vertical slice, then dispatch by owner.
- Commit after every numbered task. Do not combine unrelated owners' work in one commit.
- P1 owns shared contracts and integration decisions. Contract changes require all affected owners to acknowledge before merge.
- Follow `docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md` for file ownership, task branches and handoffs.
- P1 and P4 co-own Docker/ECR/EC2 deployment; P4 never carries deployment or shared-contract risk alone.
- Day 2 afternoon is feature freeze. After freeze, only fixes, deployment, rehearsal, documentation and submission checks are allowed.
- Optional tasks stay unchecked unless every required acceptance gate through Task 10 passes.

## Wave Map

| Wave | Time box | Required tasks | Parallel owners | Exit gate |
|---|---:|---|---|---|
| 0 | Day 1, first 45 min | 0, 1 | P1 + P4, all review | Environment checked; schemas and ports frozen |
| 1 | Day 1 morning, 90 min | 2 | P1 + P3, P2/P4 review | Fixture request produces four artifacts |
| 2 | Day 1 remainder | 3, 4, 6, 7 | P1/P2/P3/P4 | Each owner passes unit and contract tests |
| 3 | Day 1 late afternoon | 5, then 8 | P2; then all | First complete H2-Lite run passes locally |
| 4 | Day 2 morning | 9 | All | Five-coin and resilience acceptance gates pass |
| 5 | Day 2 afternoon | 10 | P1 + P4 lead, all rehearse | EC2 demo, recorded fallback and submission checks pass |
| Optional | Only after Wave 5 | 11, 12 | Explicitly reassigned | Never blocks MVP |

## Required Tasks

- [ ] **0. Verify external access and lock the two-day scope**
  - **Owner:** P4, reviewed by all
  - **Wave / dependency:** Wave 0 / none
  - **Spec:** 5.1-5.4, 14, 17
  - **Files:**
    - Modify: `.env.example`
    - Create: `docs/rehearsals/service-access-check.md`
  - [ ] Add names only, never values, for AWS region, Bedrock primary/fallback model IDs, CryptoPanic token and artifact root to `.env.example`.
  - [ ] From the target AWS account and region, invoke both configured Bedrock model IDs with a minimal non-sensitive prompt; record timestamp, region, model IDs and pass/fail only.
  - [ ] Register and test the CryptoPanic token; record endpoint and pass/fail without recording the token or response headers.
  - [ ] Confirm Python 3.12, Docker and AWS CLI versions and record them in `docs/rehearsals/service-access-check.md`.
  - [ ] Reconfirm in the same document that H3, S3, CloudWatch and ECS are outside the required scope.
  - **Acceptance:** Both Bedrock model paths and CryptoPanic access have a redacted result; no credential appears in tracked files; blocked services have an explicit fixture/fallback path and do not block Task 1.
  - **Commit:** `chore: record service access preflight`

- [ ] **1. Scaffold the package and freeze shared contracts**
  - **Owner:** P1, reviewed by P2/P3/P4
  - **Wave / dependency:** Wave 0 / Task 0 may run concurrently
  - **Spec:** 6, 7, 10.3, 13, 14
  - **Files:**
    - Create: `pyproject.toml`
    - Create: `src/hoya_agent/__init__.py`
    - Create: `src/hoya_agent/models.py`
    - Create: `src/hoya_agent/config.py`
    - Create: `src/hoya_agent/clock.py`
    - Create: `src/hoya_agent/ports.py`
    - Create: `tests/conftest.py`
    - Create: `tests/fakes.py`
    - Create: `tests/unit/test_models.py`
    - Create: `tests/unit/test_config.py`
  - [ ] Configure Python 3.12 and runtime dependencies `pydantic`, `httpx`, `pandas`, `boto3`, `streamlit`; configure dev dependencies `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff` and pytest markers `integration`, `acceptance`, `live`.
  - [ ] First write failing model tests for `AnalysisRequest`, `EvidenceItem`, `Claim`, `ClaimEvidenceLink`, `AnalysisResult`, `RunMode`, `Reliability`, `Stance` and timezone-aware UTC validation.
  - [ ] Implement the approved schema fields exactly, including 1-2 allowed assets, official-mode time freezing, cache/stale fields and `enable_conditional_debate=false`.
  - [ ] First write failing port tests, then define thin protocols for `Clock`, `LLMClient`, `MarketSource`, `ResearchSource`, `ProgressSink` and `ArtifactStore`; ports expose typed values rather than framework objects.
  - [ ] Add reusable fixed clock, fake LLM, fake adapters and in-memory progress sink under `tests/fakes.py`.
  - [ ] Run `python -m pytest tests/unit/test_models.py tests/unit/test_config.py -q` and `ruff check .`.
  - **Acceptance:** Invalid assets, naive datetimes and malformed evidence fail validation; official mode ignores user-supplied analysis time and uses injected UTC clock; all owners can implement against ports without importing Streamlit, boto3 or concrete adapters.
  - **Commit:** `feat: define shared analysis contracts`

- [ ] **2. Deliver the fixture vertical slice and incremental artifact contract**
  - **Owner:** P1 with P3; P2 and P4 review the interface
  - **Wave / dependency:** Wave 1 / Task 1
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
  - [ ] Write a failing integration test that passes one BTC rehearsal request, fixture evidence and fixture `AnalysisResult` through the application service.
  - [ ] Implement the smallest application flow that writes `run_config.json` first, streams `execution_log.jsonl`, writes `evidence.json`, then renders `final_report.md`.
  - [ ] Write renderer tests for all 11 required Traditional Chinese report sections, evidence IDs, high/medium/low confidence, limitations, invalidation conditions and prohibited-advice lint.
  - [ ] Implement deterministic Markdown rendering and a deterministic insufficient-data fallback; neither path may call an LLM.
  - [ ] Verify the exact artifact names and shared run ID with `python -m pytest tests/unit/reporting tests/integration/test_vertical_slice.py -q`.
  - **Acceptance:** A network-free BTC fixture run produces four parseable artifacts in order; the report contains all 11 sections and no facts absent from the fixture; failure to provide an `AnalysisResult` produces the fallback report instead of aborting.
  - **Commit:** `feat: add fixture artifact vertical slice`

- [ ] **3. Implement deadline-aware fork-join orchestration**
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
    - Create: `tests/integration/test_fork_join.py`
  - [ ] Write failing tests for shared run deadline, stage budgets, cancellation and skip order `H3 -> optional context -> counter-signal second search` using a fake clock/sleeper.
  - [ ] Implement `DeadlineManager` with remaining-time calculation and stage-scoped `asyncio.wait_for`; no real-time sleeps in tests.
  - [ ] Write a failing fork-join test proving Market Worker and Research Agent overlap in time and `asyncio.gather(..., return_exceptions=True)` preserves the successful result.
  - [ ] Implement run state events for queued/running/degraded/completed/failed, source success/failure and remaining stages.
  - [ ] Stream tool/agent start, end, status and summary events to JSONL; log prompt/schema version references only.
  - [ ] Run `python -m pytest tests/unit/orchestration tests/integration/test_fork_join.py -q`.
  - **Acceptance:** One branch timeout still reaches Renderer with partial evidence; stage deadline cancels pending calls; execution events are append-only and secret-free; artifact completion remains the highest-priority terminal path.
  - **Commit:** `feat: add deadline aware orchestration`

- [ ] **4. Implement deterministic OHLCV market evidence**
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
    - Create: `src/hoya_agent/adapters/coingecko.py`
    - Create: `tests/fixtures/ohlcv/mini_daily.csv`
    - Create: `tests/fixtures/http/binance_klines.json`
    - Create: `tests/fixtures/http/coingecko_market_chart.json`
    - Create: `tests/unit/data/test_market_series.py`
    - Create: `tests/unit/data/test_indicators.py`
    - Create: `tests/unit/data/test_market_worker.py`
    - Create: `tests/contract/test_market_adapters.py`
  - [ ] Write golden tests for return, realized volatility, maximum drawdown, volume change, rolling z-score and relative change using hand-computable fixture values.
  - [ ] Implement UTC parsing and reject incomplete daily candles from historical calculations; represent the current candle separately as an intraday snapshot.
  - [ ] Implement Binance klines as canonical live source and CoinGecko as fallback with endpoint, pair, parameters, UTC range and fetched time captured in evidence metadata.
  - [ ] Implement Market Worker without any LLM dependency and convert each metric into a high-reliability, reproducible `EvidenceItem`.
  - [ ] Add a failing cross-asset test that rejects direct base-volume comparison and permits quote volume, return, volatility, relative change or each asset's z-score.
  - [ ] Run `python -m pytest tests/unit/data tests/contract/test_market_adapters.py -q`.
  - **Acceptance:** Golden values and UTC cutoffs pass; Binance failure uses CoinGecko or returns a typed gap; CSV/live source switch is explicitly represented; Market Worker has no import or call path to `LLMClient`.
  - **Commit:** `feat: add deterministic market evidence`

- [ ] **5. Implement research adapters and Evidence Processor**
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
  - [ ] Write adapter contract tests for success, timeout, HTTP error, malformed payload and empty data using `httpx.MockTransport`.
  - [ ] Implement 45-second per-call timeout and at most one deadline-bound retry; normalize missing sources into typed gaps rather than exceptions crossing the port.
  - [ ] Mark Fear & Greed as low-reliability, whole-market context and never as coin-specific evidence.
  - [ ] Write failing Evidence Processor tests for required fields, SHA-256 exact deduplication, registered-domain/original-publisher grouping, staleness, static reliability and source diversity counts.
  - [ ] Implement material-conflict detection only when both stances are at least medium reliability and use distinct independence groups.
  - [ ] Test official mode cache metadata and prove that fixtures/recorded reports are rejected in official mode.
  - [ ] Run `python -m pytest tests/contract/test_research_adapters.py tests/unit/evidence -q`.
  - **Acceptance:** Duplicate syndication is not counted as independent evidence; normal fixture Ledger has at least three source types, three independence groups and one first-hand source; missing sources produce explicit gaps without inventing facts.
  - **Commit:** `feat: normalize research evidence ledger`

- [ ] **6. Implement bounded Planner, Research Agent and Arbiter**
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
  - [ ] Write Planner tests for bounded research steps, time range, evidence types and asset/question mismatch warning; Planner must not produce a market conclusion.
  - [ ] Implement a thin Bedrock Converse wrapper with configured primary/fallback model IDs, `max_tokens`, stage deadline and structured JSON parsing.
  - [ ] Implement Research Agent as a bounded executor over provided tools; prohibit free loops and facts without returned Evidence IDs.
  - [ ] Write Arbiter tests for reliability/time sorting, truncation to configurable 20-30 evidence items, a single primary generation, one schema repair attempt and deterministic fallback signal.
  - [ ] Validate fact -> inference -> conclusion dependencies, claim-evidence links, confidence rubric, limitations, invalidation conditions and absence of Ledger-external facts.
  - [ ] Implement `ConflictDetector` interface with default stub returning no material conflict whenever H3 is disabled.
  - [ ] Run `python -m pytest tests/contract/test_bedrock_client.py tests/unit/reasoning -q`.
  - **Acceptance:** Arbiter emits valid `AnalysisResult` from a fake LLM; malformed output is repaired once within the same deadline then falls back; prompt/schema versions are exposed for run config; default H3 path performs no Bull/Bear/Judge call.
  - **Commit:** `feat: add bounded bedrock reasoning`

- [ ] **7. Build the Streamlit and container shell against the vertical slice**
  - **Owner:** P4
  - **Wave / dependency:** Wave 2 / Task 2
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
  - [ ] Write presenter tests for stage progress, successful/failed sources, degradation notes, run mode labels and recorded-fallback warning.
  - [ ] Build one Streamlit screen for question, one asset selection, run mode, progress, report/evidence/log tabs and four artifact download controls; call `application.py` in the same process.
  - [ ] Keep the internal 1-2 asset contract but do not add complex multi-asset UI.
  - [ ] Ensure official/rehearsal/demo are visibly distinct and no trading controls or investment-advice copy exists.
  - [ ] Containerize the same process with a non-root user, environment-based secrets and a Streamlit healthcheck; do not add FastAPI.
  - [ ] Run `python -m pytest tests/unit/ui tests/integration/test_ui_application_contract.py -q` and `docker compose config`.
  - **Acceptance:** UI renders fixture vertical slice, displays partial failures and downloads all artifacts; recorded demo cannot look live; Docker config contains no secrets and starts the same Streamlit application.
  - **Commit:** `feat: add streamlit demo shell`

- [ ] **8. Integrate the complete H2-Lite core and degradation paths**
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
  - [ ] First add a failing end-to-end fixture test for Planner -> parallel Market/Research -> Processor -> Arbiter -> Renderer.
  - [ ] Wire only typed ports; preserve incremental artifacts and publish progress after every stage.
  - [ ] Add failure-injection tests for Market timeout, Research timeout, all external sources down, Arbiter invalid schema twice and time-based optional-stage skipping.
  - [ ] Add provenance tests requiring all report market numbers and conclusion links to resolve to Ledger evidence and all inference/conclusion dependencies to resolve to fact.
  - [ ] Add run-mode tests rejecting fixtures in official, allowing deterministic fixtures in rehearsal and visibly marking recorded runs in demo.
  - [ ] Run `python -m pytest tests/unit tests/contract tests/integration -q` and `ruff check .`.
  - **Acceptance:** Complete fixture H2-Lite works locally; every failure injection still emits four artifacts; conclusion coverage is 100% or explicitly insufficient; no prompt text, key or credential appears in logs/artifacts.
  - **Commit:** `feat: integrate resilient h2 lite pipeline`

- [ ] **9. Pass five-coin, deadline and live-source acceptance gates**
  - **Owner:** All; P1 owns the gate
  - **Wave / dependency:** Wave 4 / Task 8
  - **Spec:** 10.1, 17 Day 2 morning, 18.1-18.4
  - **Files:**
    - Create: `tests/acceptance/test_coin_matrix.py`
    - Create: `tests/acceptance/test_deadline_budget.py`
    - Create: `tests/acceptance/test_artifact_contract.py`
    - Create: `tests/live/test_live_sources.py`
    - Create: `tests/live/test_bedrock_access.py`
    - Create: `scripts/run_acceptance.py`
    - Create: `scripts/calibrate_live_source.py`
    - Create: `docs/rehearsals/live-source-calibration.md`
    - Create: `docs/rehearsals/run-log.md`
  - [ ] Add fixture questions for BTC, ETH, SOL, BNB and XRP, plus one 2-asset contract case; assert four artifacts, provenance and report contract for each.
  - [ ] Add a fake-clock deadline acceptance test proving nonessential calls cancel by minute 12 and artifacts complete by minute 13.
  - [ ] Implement an opt-in live test gate and run Binance, CryptoPanic/RSS, Fear & Greed and Bedrock checks without saving secrets.
  - [ ] Run the 2026-05-01 through 2026-05-31 Binance/CSV overlap calibration for all five assets; record method, UTC range and differences without claiming shared provenance.
  - [ ] Complete three timed live-source rehearsals; record run ID, mode, duration, source gaps, artifact paths and result in `docs/rehearsals/run-log.md`.
  - [ ] Run `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q` and `ruff check .`.
  - **Acceptance:** Offline suite passes all five assets; three rehearsals finish all artifacts before minute 13 or document a fixed blocker before freeze; calibration record exists for five assets; all required resilience scenarios pass.
  - **Commit:** `test: verify five coin acceptance matrix`

- [ ] **10. Freeze, deploy and prepare verifiable submission evidence**
  - **Owner:** P1 and P4 co-lead; all participate
  - **Wave / dependency:** Wave 5 / Task 9
  - **Spec:** 17 Day 2 afternoon, 18.5-18.6
  - **Files:**
    - Create: `.github/workflows/ci.yml`
    - Create: `docs/deployment.md`
    - Create: `docs/demo-runbook.md`
    - Create: `docs/architecture.md`
    - Create: `scripts/smoke_test.py`
    - Modify: `README.md`
  - [ ] Freeze features and run the full non-live CI command from `.kiro/steering/testing.md`.
  - [ ] Build the Docker image, push a commit-SHA tag to ECR and deploy that immutable tag to one EC2 host with `docker compose`; document exact environment names, healthcheck and rollback command without secrets.
  - [ ] Smoke-test the public URL, one rehearsal run and all artifact downloads using `scripts/smoke_test.py`.
  - [ ] Save one complete recorded fallback run outside source control, then document how demo mode exposes its original timestamp and recorded status.
  - [ ] Update README with local run, test, Docker, config and artifact instructions; add CI for non-live tests and Ruff.
  - [ ] Run a 15-minute judged-flow rehearsal from question entry through artifact inspection, then run a repository secret scan and inspect `git status`/`git ls-files` for `.env`, keys and credentials.
  - **Acceptance:** EC2 URL is reachable; Docker tag maps to a commit; CI is green; demo runbook covers live failure and recorded fallback truthfully; repository contains source, config example, Kiro evidence and no secrets; H3 is labelled unimplemented extension unless its optional gate passed.
  - **Commit:** `docs: finalize deploy and demo runbook`

## Optional Tasks: Never Block MVP

- [ ] **11. Optional H3 one-round conditional debate**
  - **Entry gate:** Tasks 0-10 all accepted, three timed rehearsals passed, feature freeze owner explicitly approves remaining time.
  - **Owner:** P3; P1 reviews deadline isolation
  - **Files:**
    - Modify: `src/hoya_agent/reasoning/conflict_extension.py`
    - Create: `src/hoya_agent/reasoning/debate.py`
    - Create: `tests/unit/reasoning/test_debate.py`
    - Create: `tests/integration/test_optional_h3.py`
  - [ ] First test the exact material-conflict rule, shared Evidence IDs, one Bull/Bear round, Judge schema and immediate fallback to Arbiter on timeout/error.
  - [ ] Keep `enable_conditional_debate=false` as default and enforce the approved skip order/deadline.
  - **Acceptance:** Disabling or failing H3 produces byte-equivalent H2-Lite core artifacts for the same fixtures; no debate agent introduces new evidence; recorded rehearsal is clearly labelled.
  - **Commit:** `feat: add optional bounded conflict debate`

- [ ] **12. Optional S3 artifact mirror and CloudWatch logs**
  - **Entry gate:** Tasks 0-10 all accepted; local artifact and stdout paths remain the source of fallback behavior.
  - **Owner:** P4
  - **Files:**
    - Create: `src/hoya_agent/optional/__init__.py`
    - Create: `src/hoya_agent/optional/s3_artifacts.py`
    - Create: `src/hoya_agent/optional/cloudwatch_logs.py`
    - Create: `tests/contract/test_optional_aws_sinks.py`
    - Modify: `docs/deployment.md`
  - [ ] First test AWS sink failure, timeout, key naming, redaction and local fallback using botocore `Stubber`.
  - [ ] Guard both integrations behind disabled-by-default settings and short deadlines.
  - **Acceptance:** S3/CloudWatch unavailability cannot fail a run or delay local artifacts; credentials and prompt bodies are never emitted; disabling both restores required behavior without code changes.
  - **Commit:** `feat: add optional aws artifact sinks`

## Final Required Gate

Before any optional task or submission:

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short
```

Expected: tests and Ruff pass, Compose config is valid, and `git status` contains only intentionally staged submission changes.
