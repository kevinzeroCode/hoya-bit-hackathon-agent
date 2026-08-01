# Review Notes

## Consistency Check Results

### ✅ Consistent Across Documents

1. **Technology stack** — All documents agree on Python 3.12, Pydantic v2, httpx, pandas, boto3, Streamlit, pytest
2. **Asset list** — BTC/ETH/SOL/BNB/XRP consistently referenced as the only supported assets
3. **Run modes** — official/rehearsal/demo consistently described with same rules in all documents
4. **Deadline values** — 900s hard limit, 720s analysis stop, 780s artifact deadline consistently documented
5. **Artifact names** — `run_config.json`, `execution_log.jsonl`, `evidence.json`, `final_report.md` consistent everywhere
6. **LLM call budget** — All documents agree on exactly 1 call per reasoning stage (Planner, Research, Arbiter)
7. **Reliability policy** — Static table (high/medium/low) consistently described in components, interfaces, and data_models
8. **Module ownership rules** — architecture.md boundaries match components.md descriptions and interfaces.md signatures
9. **Error handling pattern** — Degradation-first (never crash) consistently described across workflows, components, and architecture
10. **Frozen path list** — Consistent between architecture.md and project steering documents

### ⚠️ Minor Inconsistencies Found

1. ~~**`evidence/evidence_json.py` vs `reporting/artifacts.py` — dual writer concern**~~
   **Resolved 2026-08-01 (fifth pass):** `evidence/evidence_json.py` is deleted along with
   its test. It was a P2 prototype writer whose schema (`evidence-ledger/p2-prototype-v1`)
   contradicted `evidence-contracts.md` §12, and nothing under `src/` imported it. The
   canonical writer is `reporting/artifacts.py`.

2. ~~**`_provisional_seams.py` still exists alongside real implementations**~~
   **Resolved 2026-08-01 (S8/S9/S9B):** `_provisional_seams.py` is RETIRED (deleted from
   `main`). `application.py`, `reporting/artifacts.py`, and orchestration consume the
   canonical seams in `models.py`, `ports.py`, and `clock.py`. There is no parallel
   provisional contract. The composition root is `composition.py` (live/Bedrock wiring)
   plus `application.build_research_pipeline()` (research-branch wiring).

3. **`p2-etl-mvp/` prototype tree**
   - Still present in the repo (ruff noise); being superseded by `src/hoya_agent/`.
   - **Recommendation:** Remove or `.gitignore` once all needed code has been migrated.

4. **`docs/Architecture-FileMap.md` is STALE**
   - Still shows `config.py`, `clock.py`, and `ports.py` as "planned" / not-yet-implemented.
   - **Reality:** All three are implemented and tested. Additionally `composition.py`,
     `src/calc/`, `src/skills/`, and `src/hoya_agent/ui/` are absent from the file map.
   - **Recommendation:** Update `docs/Architecture-FileMap.md` to reflect current layout
     (outside this file's ownership — see `architecture.md` for the current map).

---

## Completeness Check Results

### ✅ Well-Covered Areas

- Core domain models (canonical Pydantic contracts in `models.py`, including run/context/worker enums and the `DataMode` honesty validator)
- Pipeline execution flow (complete sequence diagram)
- Error handling and degradation paths
- External service contracts
- Adapter patterns and signatures
- Confidence cap logic (deterministic, post-LLM, in `finalize_analysis`)
- Artifact write ordering (atomic tmp+fsync+replace)
- Frozen path warnings
- Development workflow
- Deployment architecture (Docker → ECR → EC2, `docs/deploy-ec2.md`)
- Configuration parsing (`config.py` — Settings class, from_env(), sanitized_snapshot())
- Clock injection (`clock.py` — SystemClock, build_run_context with official cutoff freeze)
- Protocol interfaces (`ports.py` — all protocols with full signatures)
- Port-conforming adapters (`adapters/port_adapters.py` — CSV, Binance, RSS, CryptoPanic, F&G, official)
- Live source composition (`adapters/live_sources.py` — Binance + F&G sync callables, no key)
- Composition root (`composition.py` — `build_live_pipeline`, `MappingArbiter`, Bedrock wiring)
- Arbiter output boundary (`reasoning/arbiter_output.py` + `reasoning/mapping.py`)
- Bronze UI (`src/hoya_agent/ui/streamlit_app.py` + `presenter.py` — trust funnel G3)
- Deterministic skills surface (`src/calc/`, `src/skills/`, `scripts/analyze.py`)
- Test infrastructure (`tests/fakes.py` — FixedClock, FakeLLM, FakeSourceAdapter, FakeResearchSourceAdapter, FakeMarketDataAdapter)
- Test bootstrapping (`tests/conftest.py` — src path injection)

### ⚠️ Areas with Limited Detail

1. **Streamlit UI (`src/hoya_agent/ui/streamlit_app.py`) + presenter**
   - **Status:** Implemented (Bronze). Three modes: live `official` (real Binance +
     Fear & Greed; Arbiter when Bedrock is configured via env/EC2 IAM role), offline
     `rehearsal`, offline `demo` over the organizer CSV. `ExecutionEvent`s stream live
     into an `st.status` panel; the presenter derives a trust funnel (G3) from the run's
     own `evidence.json`.
   - **Gap:** The live UI cut runs `build_live_pipeline` with `planner=None` and
     `research_agent=None` — the Planner/Research (news extraction) branch is intentionally
     off for the first live cut and added once the Arbiter path is proven. H3 multi-agent
     debate is explicitly out of Bronze scope (caption in the UI).
   - **Recommendation:** Document the live Planner/Research enablement when wired.

2. **`orchestration/deadline.py`** — ✅ resolved 2026-08-01
   - Owns `Stage` budget milestones (planner/gather/evidence/reason/artifact) stored as
     fractions of a reference 720 s analysis window, `deadline_for`, `remaining`, `budget_for`,
     `budget_seconds`, `for_run`, and a `max(20%, min(60 s, half the run))` finalize reserve
   - Owns the fixed optional-work skip order (`OptionalWork`, `SKIP_ORDER`, `plan_optional_work`)
   - Covered by `tests/unit/orchestration/test_deadline.py` (injected fake clock)

3. **`orchestration/run_state.py`** — ✅ resolved 2026-08-01
   - Owns `RunStateMachine` (stage lifecycle + stage_start/stage_end streaming +
     `stage_durations_ms`), `stage_state_for(WorkerStatus)` (`partial -> degraded`) and
     `derive_terminal_state(states, run_cancelled=...)`
   - One cancelled branch beside a completed sibling is `degraded`; a cancelled run is `cancelled`
   - Covered by `tests/unit/orchestration/test_run_state.py`

4. **`reporting/advice_lint.py`** (was `lint.py`)
   - **Status:** Implemented as `advice_lint.py`; the renderer's `lint=advice_violations`
     hook runs it last over the finished Traditional Chinese report.
   - **Recommendation:** No longer a gap; remove from future review passes.

5. **`tests/acceptance/` directory**
   - **Status:** Does NOT exist. Planned for Day 2 with five-coin matrix, run-mode
     validation, 13-minute delivery gate.
   - **Impact:** Medium — acceptance tests are a Day 2 freeze gate requirement.
   - **Recommendation:** Create when acceptance test criteria are ready to implement.

6. **`tests/live/` directory**
   - **Status:** EXISTS. Contains `conftest.py`, `test_bedrock_access.py`,
     `test_bedrock_silver_gate.py`, `test_live_silver_pipeline.py`,
     `test_live_silver_sources.py`, `test_live_sources.py`. Opt-in via
     `RUN_LIVE_TESTS=1` and the `live` marker; manual, executed before competition.
   - **Recommendation:** Keep current; expand as live coverage grows.

7. **`ui/presenter.py`**
   - **Status:** Implemented (framework-free, unit-testable). `summary_view()` maps a
     `RunSummary` to a view dict; `trust_funnel()` distils an `evidence.json` ledger into
     the G3 trust-funnel metrics (evidence → source types → independence groups → conflicts
     + reliability mix).

---

## Code Health Observations

### Ruff Status
- The `p2-etl-mvp/` prototype tree is the main source of ruff noise; `src/` and `tests/`
  paths under the active pipeline are clean.
- **Recommendation:** Remove or exclude `p2-etl-mvp/` from lint scope.

### TODO / FIXME / HACK Scan
- A `rg "TODO|FIXME|XXX|HACK"` over `src/` returns **no matches** — the active source
  tree carries no inline debt markers. (One incidental match lives in a docs plan file,
  not source.)

### Model Completeness
- `models.py` contains the canonical domain contracts (enums + Pydantic models)
  including `RunContext`, `RunSummary`, `RunConfigSnapshot`, `RawSourceRecord`,
  `ResearchStep`/`ResearchPlan`, `WorkerStatus`, `StageState`, `TerminalState`,
  `DataMode` (with `requested_for()` and the official-can't-lie validator), and
  `Asset`. Complete for the current pipeline and all downstream consumers.

### Redundancy to Clean Up
- ~~`_provisional_seams.py` duplicates type definitions now canonically in `models.py` and `ports.py`~~ — RESOLVED: file retired.
- ~~`evidence/evidence_json.py` duplicates artifact-writing responsibility of `reporting/artifacts.py`~~ — RESOLVED: prototype writer deleted.
- `p2-etl-mvp/` remains the only outstanding redundancy.

### Known Functional Gaps (current state)
- **Triangulation (G2) is not wired into the run.** `evidence/triangulation.py`
  provides cross-source triangulation helpers but no pipeline stage calls them; they
  are produced alongside the ledger for potential Arbiter/UI use only.
- **H3 conditional debate is permanently disabled.** `reasoning/conflict_extension.py`
  always routes to the Arbiter; `OptionalWork.conditional_debate` stays in `SKIP_ORDER`
  for vocabulary continuity but is never scheduled or skipped at runtime. Material
  conflict is instead detected deterministically in `finalize_analysis` and preserved
  on the ledger regardless.
- **CryptoPanic is a low-reliability source.** It is the designated counter-signal
  search and is surrendered last in the skip order; without `CRYPTOPANIC_API_TOKEN` it
  reports `rejected` (gap disclosed, not silently absent).
- **Live UI cut has no Planner/Research branch.** `composition.build_live_pipeline`
  runs with `planner=None` and `research_agent=None`; only market (Binance) + sentiment
  (Fear & Greed) evidence plus the Arbiter run. News extraction is added once the
  Arbiter path is proven.
- **Arbiter output boundary.** `ArbiterOutput` (no frozen request context) is projected
  by `project_to_analysis_result`; the live cut uses `mapping.py`
  (`ArbiterGeneration` → `AnalysisResult`) wrapped in `MappingArbiter`, which returns
  `None` on any mapping/validation failure so the run degrades to the deterministic
  report. Arbiter `max_tokens` is capped at 3000 in the live cut to fit the 45 s call
  limit (default 8000 can overrun → `DeadlineExceeded` → fallback).

---

## Documentation Staleness

| Document | Status | Issue |
|---|---|---|
| `docs/Architecture-FileMap.md` | STALE | Shows config/clock/ports as "planned"; missing `composition.py`, `src/calc/`, `src/skills/`, `src/hoya_agent/ui/` |
| `.agents/summary/interfaces.md` | PARTIALLY STALE | Any remaining reference to `_provisional_seams.py` is now wrong — protocols are in `ports.py` and the seam file is deleted |
| `.agents/summary/components.md` | NEEDS UPDATE | Missing entries for `composition.py`, `live_sources.py`, `ui/`, `src/calc/`, `src/skills/`, `reasoning/mapping.py`, `reasoning/arbiter_output.py` |
| `.agents/summary/data_models.md` | NEEDS UPDATE | Must reflect `ArbiterOutput` boundary schema, `DataMode` validator, and any new models added since last pass |

---

## Recommendations

### High Priority
1. Update `docs/Architecture-FileMap.md` to reflect current layout (composition, ui, calc, skills).
2. Remove or `.gitignore` the `p2-etl-mvp/` prototype tree (last ruff-noise + redundancy source).
3. Update `components.md`, `interfaces.md`, and `data_models.md` to cover `composition.py`,
   `live_sources.py`, `ui/`, `src/calc/`, `src/skills/`, `reasoning/mapping.py`,
   `reasoning/arbiter_output.py`, and the `ArbiterOutput` boundary schema.

### Medium Priority
4. Create `tests/acceptance/` with the five-coin matrix, run-mode validation, and
   13-minute delivery gate (Day 2 freeze gate).
5. Wire `evidence/triangulation.py` (G2) into the run, or document explicitly that it
   stays a derived view — currently it is neither called nor surfaced in artifacts.
6. Enable the Planner/Research branch on the live UI cut once the Arbiter path is proven.
7. Document the live Planner/Research enablement in `workflows.md` / `components.md` when wired.

### Low Priority
8. Create a detailed test fixture catalog if the fixture set grows significantly.
9. Add deployment runbook details when EC2 setup is finalized (`docs/deploy-ec2.md` exists;
   verify it matches the current image/compose).
10. Keep the `p2-etl-mvp/` removal coordinated with any remaining code migration.
