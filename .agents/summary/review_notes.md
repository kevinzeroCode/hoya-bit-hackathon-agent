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

1. **`evidence/evidence_json.py` vs `reporting/artifacts.py` — dual writer concern**
   - `components.md` lists `evidence_json.py` in the evidence layer
   - `architecture.md` assigns artifact writing to `reporting/artifacts.py`
   - **Reality:** Both exist. `evidence_json.py` is a P2 prototype writer with a different schema (`schema: "evidence-ledger/p2-prototype-v1"`). The canonical writer is `reporting/artifacts.py`. This is documented in the work-in-progress steering but represents an unresolved code duplication.
   - **Recommendation:** Documentation accurately reflects current state; this is an implementation cleanup task, not a doc error.

2. **`_provisional_seams.py` still exists alongside real implementations**
   - `interfaces.md` originally described Protocols as living in `_provisional_seams.py` (will move to `ports.py`)
   - **Reality:** `ports.py` NOW EXISTS with the canonical Protocol definitions (Clock, LLMClient, SourceAdapter, MarketDataAdapter, ResearchSourceAdapter, ProgressSink, ArtifactStore, PersistencePort, ToolRegistry, StaticToolRegistry). However, `_provisional_seams.py` has NOT been removed. The provisional file coexists with the real seams, creating import-path ambiguity.
   - **Action needed:** The swap procedure (documented in `docs/ai/S2_CONTRACT_EXPECTATIONS.md` §4) should be executed to remove `_provisional_seams.py` and update imports in `application.py`, `reporting/artifacts.py`, and integration tests.

3. **`p2-etl-mvp/` prototype tree**
   - Listed in `codebase_info.md` project layout but not deeply documented elsewhere
   - **Reality:** Still present in the repo with 76 ruff errors. Being superseded by `src/hoya_agent/`.
   - **Recommendation:** Should be removed or .gitignored once all needed code has been migrated.

4. **`docs/Architecture-FileMap.md` is STALE**
   - Still shows `config.py`, `clock.py`, and `ports.py` as "planned" / not-yet-implemented.
   - **Reality:** All three files are now implemented and tested. The file map should be updated to reflect this.
   - **Recommendation:** Update `docs/Architecture-FileMap.md` to show these as implemented.

---

## Completeness Check Results

### ✅ Well-Covered Areas

- Core domain models (all 40 Pydantic models/classes documented, up from 29 in initial pass)
- Pipeline execution flow (complete sequence diagram)
- Error handling and degradation paths
- External service contracts
- Adapter patterns and signatures
- Confidence cap logic
- Artifact write ordering
- Frozen path warnings
- Development workflow
- Deployment architecture
- Configuration parsing (`config.py` — Settings class, from_env(), sanitized_snapshot())
- Clock injection (`clock.py` — SystemClock, build_run_context with official cutoff freeze)
- Protocol interfaces (`ports.py` — all 8+ protocols with full signatures)
- Port-conforming adapters (`adapters/port_adapters.py` — CsvMarketAdapter, BinanceMarketAdapter, RssResearchAdapter)
- Test infrastructure (`tests/fakes.py` — FixedClock, FakeLLM, FakeSourceAdapter, FakeResearchSourceAdapter, FakeMarketDataAdapter)
- Test bootstrapping (`tests/conftest.py` — src path injection)

### ⚠️ Areas with Limited Detail

1. **Streamlit UI (`streamlit_app.py`)**
   - **Gap:** Not yet implemented; no UI component documentation
   - **Impact:** Low — documented as not-yet-built. Will need a UI section when implemented
   - **Recommendation:** Add to components.md when `streamlit_app.py` is created

2. **`orchestration/deadline.py`**
   - **Gap:** Planned file that doesn't exist yet. Deadline logic is described conceptually in workflows/architecture but no implementation
   - **Impact:** Medium — deadline management is critical for competition
   - **Recommendation:** Add to components.md and interfaces.md when this file lands

3. **`orchestration/run_state.py`**
   - **Gap:** Planned file that doesn't exist yet. Run state tracking is conceptual only
   - **Impact:** Medium — needed for full pipeline wiring
   - **Recommendation:** Add to components.md when this file lands

4. **`reporting/lint.py`**
   - **Gap:** Planned in structure.md but unowned. Referenced by renderer's `lint=hook` parameter. No implementation exists
   - **Impact:** Low — the lint hook protocol is documented in interfaces.md; the test suite validates the concept

5. **`tests/acceptance/` directory**
   - **Gap:** Does not exist yet. Planned for Day 2 with five-coin matrix, run-mode validation, 13-minute delivery gate
   - **Impact:** Medium — acceptance tests are a Day 2 freeze gate requirement
   - **Recommendation:** Create when acceptance test criteria are ready to implement

6. **`tests/live/` directory**
   - **Gap:** Does not exist yet. For manual opt-in live rehearsal tests
   - **Impact:** Low — these are opt-in and executed manually before competition
   - **Recommendation:** Create before first live rehearsal

7. **`ui/presenter.py`**
   - **Gap:** Planned domain-to-Streamlit view model layer, not yet implemented
   - **Impact:** Low — UI is a later task dependent on streamlit_app.py

---

## Code Health Observations

### Ruff Status
- **87 errors on `main`** — 76 in the `p2-etl-mvp/` prototype tree and ~11 inside `src/`/`tests/` from integration merges
- S2 and S1 paths themselves are clean; errors are from the unremoved prototype and cross-PR integration
- **Recommendation:** Remove or exclude `p2-etl-mvp/` from lint scope and fix remaining src/tests errors

### Model Completeness
- `models.py` now contains **40 classes** (12 enums + 28 model/dataclass definitions), properly covering all S1 contracts including:
  - Research planning: `ResearchStep`, `ResearchPlan`
  - Runtime context: `RunContext`, `RunSummary`, `RunConfigSnapshot`
  - Source records: `RawSourceRecord`
  - Worker/pipeline: `WorkerResult`, `WorkerStatus`, `StageState`, `TerminalState`
- This is complete for S1 and sufficient for all downstream consumers

### Redundancy to Clean Up
- `_provisional_seams.py` duplicates type definitions now canonically in `models.py` and `ports.py`
- `evidence/evidence_json.py` duplicates artifact-writing responsibility of `reporting/artifacts.py`
- Both are documented technical debt awaiting the swap procedure

---

## Documentation Staleness

| Document | Status | Issue |
|---|---|---|
| `docs/Architecture-FileMap.md` | 🔴 STALE | Shows config.py, clock.py, ports.py as "planned" — all are now implemented |
| `.agents/summary/interfaces.md` | ⚠️ PARTIALLY STALE | Still says protocols are in `_provisional_seams.py (will move to ports.py)` — they are now IN `ports.py` |
| `.agents/summary/components.md` | ⚠️ NEEDS UPDATE | Missing entries for config.py, clock.py, ports.py, port_adapters.py components |
| `.agents/summary/data_models.md` | ⚠️ NEEDS UPDATE | Documents 29 models but models.py now has 40; missing RunContext, RunSummary, RawSourceRecord, ResearchStep, ResearchPlan, WorkerStatus, StageState, TerminalState and Settings |

---

## Recommendations

### High Priority (before next task starts)
1. ~~Update documentation when Task 1b (`config.py`, `clock.py`, `ports.py`) lands~~ → **LANDED.** Now need to update `components.md`, `interfaces.md`, and `data_models.md` to reflect their content
2. Update `docs/Architecture-FileMap.md` to show config/clock/ports as implemented
3. Execute the `_provisional_seams.py` swap procedure (remove file, update imports)
4. Fix or exclude `p2-etl-mvp/` ruff errors (remove tree or add to ruff exclude)

### Medium Priority
5. Update when the full pipeline wiring (Task 3 completion) is done
6. Add Streamlit UI documentation when `streamlit_app.py` is created
7. Create `tests/acceptance/` and `tests/live/` directories with initial structure
8. Document `orchestration/deadline.py` and `orchestration/run_state.py` when implemented
9. Document the `lint.py` implementation when owned and written

### Low Priority
10. Create a detailed test fixture catalog if the fixture set grows significantly
11. Add deployment runbook details when EC2 setup is finalized
12. Document Dockerfile and docker-compose.yml when created
