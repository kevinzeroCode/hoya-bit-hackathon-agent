# HOYA Market Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在兩天內由四位 junior 完成可部署、可追溯、遇到來源或 LLM 失敗仍交付四項 artifacts 的 H2-Lite 原型。

**Architecture:** Streamlit 同進程呼叫 `ApplicationService`；Planner 後以 plain `asyncio` 並行 Market Worker 與 Research Agent，再經 deterministic Evidence Processor、單次受限 Arbiter 與 deterministic Renderer。外部 I/O 全部走 ports，run 從開始增量落盤；H3 預設只保留 disabled stub。

**Tech Stack:** Python 3.12, Pydantic v2, asyncio, httpx, pandas, Amazon Bedrock Converse, Streamlit, pytest, Ruff, Docker, ECR, EC2 Compose

---

## Worktree And Ownership

在專用 worktree 執行。P1：contracts/integration；P2：data/evidence；P3：reasoning/report；P4：UI/AWS/demo。完整細節以 `.kiro/specs/hoya-market-agent/tasks.md` 為準。

```text
src/hoya_agent/
  models.py config.py clock.py ports.py application.py
  orchestration/{deadline,run_state,pipeline}.py
  data/{market_series,indicators,market_worker}.py
  adapters/{organizer_csv,binance,coingecko,cryptopanic,rss,official,alternative_me,bedrock}.py
  evidence/{processor,ledger,policies}.py
  reasoning/{planner,research_agent,arbiter,conflict_extension}.py
  reporting/{renderer,artifacts,lint}.py
  ui/presenter.py
prompts/{planner-v1,research-extraction-v1,arbiter-v1}.md
streamlit_app.py
```

## Task 1: Preflight And Contracts

**Files:** Create `pyproject.toml`, `src/hoya_agent/{__init__,models,config,clock,ports}.py`, `tests/{conftest,fakes}.py`, `tests/unit/{test_models,test_config}.py`; modify `.env.example`; create `docs/rehearsals/service-access-check.md`.

- [ ] P4 verifies Bedrock primary/fallback and CryptoPanic access, recording only region/model IDs/time/pass-fail.
- [ ] P1 writes failing tests for approved schemas, 1-2 assets, aware UTC, official time freeze and sanitized config.
- [ ] Run `python -m pytest tests/unit/test_models.py tests/unit/test_config.py -vv`; expected FAIL on missing contracts.
- [ ] Implement exact Pydantic models and thin ports; provide fixed clock and fakes.
- [ ] Run `python -m pytest tests/unit/test_models.py tests/unit/test_config.py -q && ruff check .`; expected PASS.
- [ ] All owners review names, then commit:

```bash
git add pyproject.toml .env.example src/hoya_agent tests/conftest.py tests/fakes.py tests/unit/test_models.py tests/unit/test_config.py docs/rehearsals/service-access-check.md
git commit -m "feat: freeze analysis contracts"
```

## Task 2: Fixture Vertical Slice

**Files:** Create `src/hoya_agent/application.py`, `src/hoya_agent/reporting/{__init__,renderer,artifacts,lint}.py`, `tests/unit/reporting/`, `tests/integration/test_vertical_slice.py`, `tests/fixtures/vertical_slice/`.

- [ ] Write a failing BTC rehearsal test; assert artifact order and one shared run ID.
- [ ] Run `python -m pytest tests/integration/test_vertical_slice.py -vv`; expected FAIL.
- [ ] Implement minimal deterministic 11-section renderer, advice lint, incremental artifacts and insufficient-data fallback.
- [ ] Run `python -m pytest tests/unit/reporting tests/integration/test_vertical_slice.py -q`; expected PASS with four fixed filenames.
- [ ] Commit:

```bash
git add src/hoya_agent/application.py src/hoya_agent/reporting tests/unit/reporting tests/integration/test_vertical_slice.py tests/fixtures/vertical_slice
git commit -m "feat: add artifact vertical slice"
```

## Task 3: Four-Way Parallel Core

Start only after Task 2 passes.

### P1 Deadline Pipeline

**Files:** `src/hoya_agent/orchestration/{__init__,deadline,run_state,pipeline}.py`, `tests/unit/orchestration/`, `tests/integration/test_fork_join.py`; modify `reporting/artifacts.py`.

- [ ] Test fake-clock budgets, minute-12 cancellation, skip order and one-branch timeout.
- [ ] Run `python -m pytest tests/unit/orchestration tests/integration/test_fork_join.py -vv`; expected FAIL.
- [ ] Implement `wait_for` plus `gather(return_exceptions=True)`, progress and JSONL events; rerun expecting PASS.
- [ ] Commit `feat: add deadline aware pipeline` with only P1 paths.

### P2 Data And Evidence

**Files:** `src/hoya_agent/data/`, flat `src/hoya_agent/adapters/{organizer_csv,binance,coingecko,cryptopanic,rss,official,alternative_me}.py`, `src/hoya_agent/evidence/`, matching unit/contract tests and fixtures.

- [ ] Test hand-computable indicators, UTC candles, cross-asset volume rule and every adapter's success/timeout/malformed/empty cases.
- [ ] Test exact dedup, independence groups, static reliability, stale state and material conflict.
- [ ] Run `python -m pytest tests/unit/data tests/unit/evidence tests/contract/test_market_adapters.py tests/contract/test_research_adapters.py -vv`; expected FAIL.
- [ ] Implement deterministic Market Worker, adapters and Ledger; rerun expecting PASS.
- [ ] Commit `feat: add deterministic evidence pipeline` with only P2 paths.

### P3 Bounded Reasoning

**Files:** `src/hoya_agent/adapters/bedrock.py`, `src/hoya_agent/reasoning/`, `prompts/{planner-v1,research-extraction-v1,arbiter-v1}.md`, reasoning unit tests, Bedrock contract tests and fixtures.

- [ ] Test bounded plan, asset warning, top-30 evidence, one repair, claim DAG, confidence rubric and Ledger-only facts.
- [ ] Test disabled `conflict_extension.py` never invokes debate agents.
- [ ] Run `python -m pytest tests/unit/reasoning tests/contract/test_bedrock_client.py -vv`; expected FAIL.
- [ ] Implement Bedrock wrapper, Planner, Research Agent and Arbiter; rerun expecting PASS.
- [ ] Commit `feat: add bounded bedrock reasoning` with only P3 paths.

### P4 UI And Container

**Files:** `src/hoya_agent/ui/{__init__,presenter}.py`, `streamlit_app.py`, `Dockerfile`, `.dockerignore`, `compose.yaml`, UI tests.

- [ ] Test progress, source failures, mode and recorded-demo warning against fake `ApplicationService`.
- [ ] Run `python -m pytest tests/unit/ui tests/integration/test_ui_application_contract.py -vv`; expected FAIL.
- [ ] Implement one Streamlit screen, four downloads and same-process service call; do not add FastAPI.
- [ ] Run `python -m pytest tests/unit/ui tests/integration/test_ui_application_contract.py -q && docker compose config`; expected PASS.
- [ ] Commit `feat: add streamlit demo shell` with only P4 paths.

## Task 4: Integrate H2-Lite

**Files:** Modify `src/hoya_agent/{application.py,orchestration/pipeline.py,reporting/artifacts.py}`; create `tests/integration/{test_h2_lite_pipeline,test_degradation,test_run_modes,test_provenance}.py`.

- [ ] First test full fixture flow, either branch timeout, all sources down and Arbiter invalid twice.
- [ ] Assert official rejects fixtures, rehearsal accepts them, demo labels recorded runs, and all paths write four artifacts.
- [ ] Wire frozen ports and publish progress after every stage.
- [ ] Run `python -m pytest tests/unit tests/contract tests/integration -q && ruff check .`; expected PASS.
- [ ] Commit:

```bash
git add src/hoya_agent/application.py src/hoya_agent/orchestration/pipeline.py src/hoya_agent/reporting/artifacts.py tests/integration
git commit -m "feat: integrate resilient h2 lite pipeline"
```

## Task 5: Acceptance And Rehearsal

**Files:** Create `tests/acceptance/`, `tests/live/`, `scripts/{run_acceptance,calibrate_live_source}.py`, `docs/rehearsals/{live-source-calibration,run-log}.md`.

- [ ] Add BTC/ETH/SOL/BNB/XRP fixtures and one two-asset contract case.
- [ ] Run `python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q`; expected PASS.
- [ ] Run opt-in live checks and five-asset 2026-05-01 through 2026-05-31 Binance/CSV calibration without claiming shared provenance.
- [ ] Complete three timed rehearsals; record run ID, gaps, artifacts and duration, targeting minute 13.
- [ ] Commit `test: verify five coin acceptance matrix` with tests/scripts/records.

## Task 6: Freeze, Deploy And Submit

**Files:** Create `.github/workflows/ci.yml`, `docs/{deployment,demo-runbook,architecture}.md`, `scripts/smoke_test.py`; modify `README.md`.

- [ ] Freeze features and run all non-live tests plus Ruff.
- [ ] Push a commit-SHA image to ECR, deploy it on EC2 via Compose and pass Streamlit healthcheck.
- [ ] Smoke-test one run and four downloads; prepare one clearly labelled recorded fallback outside source control.
- [ ] Run a 15-minute judged-flow rehearsal and secret scan; inspect `git status --short` and `git ls-files`.
- [ ] Commit `docs: finalize deploy and demo runbook`.

## Optional Work

- [ ] Only after Tasks 1-6 and three rehearsals pass, P3 may implement one-round H3; disabled/failed H3 must preserve H2-Lite.
- [ ] Only after Tasks 1-6 pass, P4 may add disabled S3/CloudWatch sinks; sink failure must not delay local artifacts.
- [ ] Do not start ECS, on-chain, macro or social adapters during the two-day build.

## Final Verification

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short
```

Expected: required tests pass, Ruff and Compose are clean, four artifacts are reproducible, and only intended changes remain.
