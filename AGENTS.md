# AGENTS.md

> Evidence-first crypto market analysis agent. Python 3.12, Pydantic v2, Amazon Bedrock, bounded H2-Lite pipeline.

## Project Context

Two-day hackathon competition prototype that receives a question + asset(s) and produces a traceable Traditional Chinese analysis report within 15 minutes. The system prioritizes honest degradation over prediction — it always ships 4 valid artifacts even when external services fail.

**Supported assets:** BTC, ETH, SOL, BNB, XRP (coin-agnostic — all pipeline stages take `asset` as parameter, no per-coin branching).

**Run modes:** `official` (live only, cutoff frozen), `rehearsal` (fixtures), `demo` (recorded fallback).

## Directory Map

```
src/hoya_agent/
├── models.py              # 40 Pydantic domain models — the canonical contract
├── config.py              # Typed Settings from env; sanitized snapshots; hard caps
├── clock.py               # SystemClock + build_run_context (official cutoff freeze)
├── ports.py               # All Protocol interfaces + StaticToolRegistry
├── application.py         # Entry point: run identity, artifact ordering, terminal state
├── _provisional_seams.py  # Temp runtime types (coexists with ports.py/clock.py until swap)
├── adapters/              # All external I/O (flat, one file per provider)
│   ├── bedrock.py         # AWS Bedrock Converse — structured output via tool use
│   ├── binance.py         # Daily UTC klines → MarketBar
│   ├── cryptopanic.py     # News aggregation (low reliability)
│   ├── organizer_csv.py   # Competition OHLCV benchmark data
│   ├── alternative_me.py  # Fear & Greed (low, market-wide, asset=None)
│   ├── rss.py             # Original publisher feeds (medium reliability)
│   └── port_adapters.py   # Port-conforming async wrappers (CSV, Binance, RSS)
├── data/                  # Deterministic computation — no LLM, no network
│   ├── indicators.py      # return, volatility, drawdown, volume z-score
│   ├── market_worker.py   # OHLCV bars → high-reliability EvidenceDrafts
│   ├── market_series.py   # bars_asof, merge_with_cutover (CSV/live cutover)
│   ├── regime.py          # Market state classification (first-match rule)
│   └── price_analysis.py  # Cross-asset: anomaly, attribution, comparison
├── evidence/              # Ledger assembly — no LLM, no network
│   ├── processor.py       # Rank, SHA-256 dedup, stable ID assignment
│   ├── policies.py        # Static reliability, independence group, confidence caps
│   └── types.py           # FROZEN — provisional dataclasses (do not modify)
├── reasoning/             # FROZEN — LLM interaction (exactly 1 call per stage)
│   ├── planner.py         # Bounded plan generation (max 8 steps, allowlist only)
│   ├── research_agent.py  # Adapter execution + 1 LLM extraction call
│   ├── arbiter.py         # Claims (fact→inference→conclusion) + structural validation
│   ├── prompt_library.py  # Versioned prompt loading (only version IDs reach logs)
│   └── conflict_extension.py  # H3 stub — always disabled, routes to Arbiter
├── reporting/             # Deterministic output — no LLM
│   ├── renderer.py        # 11-section zh-Hant report (+ dual-only section 12)
│   └── artifacts.py       # Atomic writes (tmp+fsync+replace) for 4 fixed files
└── orchestration/
    ├── pipeline.py        # Deadline-aware H2-Lite + cancel-then-await fork-join + dual-asset projection
    ├── deadline.py        # Stage budget milestones, proportional scaling, finalize reserve
    └── run_state.py       # Stage lifecycle, WorkerStatus mapping, terminal-state derivation
prompts/                   # planner-v1.md, research-extraction-v1.md, arbiter-v1.md
tests/                     # unit/ contract/ integration/ acceptance/ live/ fixtures/
```

## Pipeline Architecture

Six fixed stages, single pass:

1. **Plan** (Planner, 1 LLM call) → allowlisted operation list or deterministic default
2. **Gather** (Market Worker ‖ Research Agent) → parallel, independent timeout
3. **Process** (Evidence Processor) → rank, dedup, assign `ev_001`..`ev_NNN`
4. **Reason** (Arbiter, 1 LLM call) → fact/inference/conclusion claims + confidence caps
5. **Render** (Renderer) → 11-section report + prohibited-language lint
6. **Finalize** (Artifacts) → 4 atomic files: `run_config.json`, `execution_log.jsonl`, `evidence.json`, `final_report.md`

**Invariant:** Pipeline ALWAYS produces 4 valid artifacts, even on total external failure.

## Key Patterns That Deviate from Defaults

- **`extra="forbid"` on all Pydantic models** — undeclared fields are rejected, not silently accepted
- **No exceptions from adapters** — all return `WorkerResult(status, drafts, notes)` or `(data, notes)` tuples; failures become degradation disclosures
- **Confidence caps are deterministic and post-LLM** — the model's self-assessed confidence is lowered by policy rules, never loosened
- **Evidence items have no stance** — stance (`supports`/`opposes`/`neutral`) lives only on `ClaimEvidenceLink`, not on the evidence itself
- **Atomic artifact writes** — every file write uses tmp → fsync → `os.replace`; no partial content on crash
- **Single `httpx.AsyncClient`** per run, shared across adapters; explicit connect/read/write/pool timeouts
- **Prompt bodies never logged** — only version identifiers (e.g., `arbiter-v1`) reach execution logs or `run_config.json`
- **Frozen paths** — several modules (see below) are complete and must not be modified without owner agreement

## Frozen Paths (Do Not Modify)

```
src/hoya_agent/adapters/bedrock.py
src/hoya_agent/reasoning/         (entire package)
src/hoya_agent/evidence/types.py
src/hoya_agent/evidence/policies.py
tests/unit/evidence/test_policies.py
prompts/
tests/contract/
tests/unit/reasoning/
```

## Deadlines

| Milestone | Seconds | Rule |
|---|---|---|
| Analysis hard stop | 720 | Cancel all external/LLM calls |
| Artifact deadline | 780 | All 4 files must be on disk |
| Competition limit | 900 | Run terminates |
| Per-call timeout | ≤45 | Max 1 retry within stage budget |
| Schema repair | 1 attempt | Shares original stage deadline |

**Skip order on time pressure:** H3 → optional context adapters → counter-signal search.

## Configuration

Environment variables (via `config.py`):

| Variable | Required | Notes |
|---|---|---|
| `BEDROCK_PRIMARY_MODEL_ID` | Yes | Primary Bedrock model |
| `BEDROCK_FALLBACK_MODEL_ID` | No | Throttling fallback |
| `CRYPTOPANIC_API_TOKEN` | No | Degrades without |
| `HOYA_DATA_DIR` | No | Override dataset path |

`run_config.json` records key presence (bool), never values. No secrets in artifacts, logs, or images.

## Testing

```bash
# Install
python -m pip install -e ".[dev]"

# Default suite (no network)
python -m pytest tests/unit tests/contract tests/integration -q

# Lint
ruff check .

# Live tests (manual, opt-in)
$env:RUN_LIVE_TESTS = "1"
python -m pytest tests/live -m live -vv -s
```

- `asyncio_mode = "auto"` — async test functions auto-detected
- Tests use injected `FixedClock` and `FakeLLM` — no real sleeps or API calls
- `tests/fakes.py` provides shared test doubles: `FixedClock`, `FakeLLM`, `FakeSourceAdapter`, etc.
- Golden fixtures with `pytest.approx` for indicator calculations
- Markers: `integration`, `acceptance`, `live`
- `tests/acceptance/` and `tests/live/` directories do not exist yet; planned for Day 2

## Detailed Documentation

For deeper information, see `.agents/summary/index.md` which routes to:

| File | Content |
|---|---|
| `codebase_info.md` | Project identity, layout, key decisions |
| `architecture.md` | System diagrams, layer rules, deployment |
| `components.md` | All modules with responsibilities and constraints |
| `interfaces.md` | Protocols, signatures, API contracts |
| `data_models.md` | Every Pydantic model, field, and validation rule |
| `workflows.md` | Execution flows, error handling, confidence caps |
| `dependencies.md` | Packages, services, env vars, exclusions |
| `review_notes.md` | Known gaps and recommendations |

## Custom Instructions
<!-- This section is for human and agent-maintained operational knowledge.
     Add repo-specific conventions, gotchas, and workflow rules here.
     This section is preserved exactly as-is when re-running codebase-summary. -->

### Documentation Maintenance Rule

When making code changes that affect architecture, interfaces, data models, workflows, or dependencies, you MUST also update the corresponding documentation file(s) in `.agents/summary/` AND `docs/`:

**`.agents/summary/` (AI agent context):**

| Change type | Update |
|---|---|
| New/renamed module or file | `codebase_info.md`, `components.md`, directory map in this file |
| New/changed Protocol or function signature | `interfaces.md` |
| New/changed Pydantic model or field | `data_models.md` |
| New/changed execution flow or error path | `workflows.md` |
| New/changed dependency or env var | `dependencies.md` |
| Structural or layer change | `architecture.md` |
| Any of the above | `index.md` (update summary if scope changed) |

**`docs/` (team documentation):**

| Change type | Update |
|---|---|
| Module added/moved/renamed, file ownership changed | `docs/Architecture-FileMap.md` |
| Pipeline stage, adapter, or system boundary changed | `docs/system-design.md` |
| Task completed, ownership changed, or path frozen/unfrozen | `docs/ACTIVE_WORK.md` |
| New dependency, tech decision, or deployment change | `docs/Tech-Stack-Plan.md` |
| Requirement completed or acceptance criteria updated | `docs/Features.md` |
| **Any change to `src/`, `tests/`, or artifact behaviour** | **`docs/Implementation-Plan.md` — required before pushing, see below** |
| Kiro task finished with commit evidence | `docs/evidence/kiro/README.md` |

This keeps both AI assistants and human teammates from working with stale context.

### Stage Status Rule (hard requirement)

**Before pushing any change to `src/`, `tests/`, or artifact behaviour, update
`docs/Implementation-Plan.md` in the same commit.** Two places, not one:

1. the §1.1 snapshot row for your stage;
2. your stage's own **現況** block.

Status blocks record **what was actually run** — real test counts (`X passed, Y failed`),
the `ruff` result, and the traps hit along the way. Not what is planned.

The "traps hit" part earns its keep. S0 wrote down three Bedrock failures — the retired
`claude-3-5-haiku-20241022` model id, the `us.` inference-profile prefix, and model output
arriving wrapped in markdown fences — and nobody after had to rediscover them.

**Why this is a hard rule rather than a nicety:** on 2026-08-01 this file went stale twice
within half a day. Once it still called Bedrock unverified after it had been proven working;
once it still called S2 the blocking critical path after S2 had merged. Either one sends
someone to redo finished work or to wait on a blocker that no longer exists. With four
people working in parallel, **a status table that is present but wrong is worse than none at
all** — an absent one makes people go and check, a wrong one gets believed.

If you are unsure whether your change warrants an update, update it. Three minutes of your
time against half a day of someone else's.

## 2026-08-01 S8 / S9 / S9B integration

- `_provisional_seams.py` is retired; application, artifacts, and orchestration use canonical models/ports.
- `orchestration/deadline.py`, `orchestration/run_state.py`, and `DeadlineAwarePipeline` implement the 720-second analysis hard stop and Market/Research fork-join.
- 2026-08-01 (second pass): `deadline.py` gained per-stage budget milestones (`Stage`, `deadline_for`, `budget_for`, `budget_seconds`, `for_run`) with proportional scaling and a `max(20%, min(60 s, half the run))` finalize reserve; `run_state.py` gained `RunStateMachine` plus `stage_state_for(WorkerStatus)`; the fork-join now cancels unfinished branches and then awaits them. A caller-cancelled run finalizes all four artifacts labelled `cancelled` and then re-raises `CancelledError` — that finalize path is deliberately await-free, because a further await inside a cancelled task raises before the writes finish. The fixed optional-work skip order (`OptionalWork`, `SKIP_ORDER`, `plan_optional_work` in `deadline.py`) is enforced by `_apply_skip_order`, which trims skipped steps out of the `ResearchPlan`; the composition root declares which operations are optional via `optional_operations` / `counter_signal_operations` (empty by default, so S6 supplies the list).
- `evidence/trust.py` provides deterministic conclusion-only Trust Scorecards.
- Dual-asset runs keep one run/cutoff/ledger and add report section 12; the frozen reasoning package remains unchanged.
- Detailed implementation and verification: `docs/S8-S9-S9B-implementation.md` and `.agents/summary/s8-s9-s9b.md`.
