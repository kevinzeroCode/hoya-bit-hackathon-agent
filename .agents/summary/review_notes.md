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

2. **`_provisional_seams.py` placement**
   - `interfaces.md` describes Protocols as living in `_provisional_seams.py` (will move to `ports.py`)
   - `architecture.md` references `ports.py` in the dependency direction diagram
   - **Reality:** `ports.py` does not yet exist. `_provisional_seams.py` is the current location.
   - **Recommendation:** Both docs are accurate — they note the future target. No correction needed.

3. **`p2-etl-mvp/` prototype tree**
   - Listed in `codebase_info.md` project layout but not deeply documented elsewhere
   - **Rationale:** It's a parallel prototype being superseded by `src/hoya_agent/`. Intentionally light documentation — the canonical code is in `src/`.

---

## Completeness Check Results

### ✅ Well-Covered Areas

- Core domain models (all 29 Pydantic models documented)
- Pipeline execution flow (complete sequence diagram)
- Error handling and degradation paths
- External service contracts
- Adapter patterns and signatures
- Confidence cap logic
- Artifact write ordering
- Frozen path warnings
- Development workflow
- Deployment architecture

### ⚠️ Areas with Limited Detail

1. **Streamlit UI (`streamlit_app.py`)**
   - **Gap:** Not yet implemented; no UI component documentation
   - **Impact:** Low — documented as not-yet-built. Will need a UI section when implemented
   - **Recommendation:** Add to components.md when `streamlit_app.py` is created

2. **`config.py` / `Settings`**
   - **Gap:** Planned but not yet implemented (Task 1b). Settings parsing documented only via env vars in dependencies.md
   - **Impact:** Medium — developers need to know how configuration flows
   - **Recommendation:** Update interfaces.md when `config.py` lands

3. **`orchestration/deadline.py` and `orchestration/run_state.py`**
   - **Gap:** Planned files that don't exist yet. Deadline logic is described conceptually in workflows/architecture but no implementation details
   - **Impact:** Medium — deadline management is critical for competition
   - **Recommendation:** Add to components.md when these files land

4. **`reporting/lint.py`**
   - **Gap:** Planned in structure.md but unowned. Referenced by renderer's `lint=hook` parameter. No implementation documented
   - **Impact:** Low — the lint hook protocol is documented in interfaces.md

5. **Test fixture structure**
   - **Gap:** Only mentions `tests/fixtures/vertical_slice/` with 2 files. No detailed fixture catalog
   - **Impact:** Low — fixtures are implementation artifacts, not architectural
   - **Recommendation:** Add fixture documentation if more fixtures are added

6. **`ui/presenter.py`**
   - **Gap:** Planned domain-to-Streamlit view model layer, not yet implemented
   - **Impact:** Low — UI is a later task

7. **P2-ETL-MVP detailed documentation**
   - **Gap:** The parallel prototype tree (`p2-etl-mvp/`) has significant code but is intentionally under-documented in these docs
   - **Rationale:** It's being superseded by `src/hoya_agent/`. Documenting it in detail would create confusion about which code is canonical
   - **Recommendation:** If any prototype code is still needed, document the specific migration path rather than the prototype itself

### 🔴 Documentation Gaps That Could Affect Development

1. **Full pipeline wiring (Task 3 completion)**
   - The documented pipeline is CSV-only (`OrganizerCsvPipeline`). The full pipeline with Market Worker fork-join, Research Agent, and Arbiter wiring is not yet implemented.
   - All workflow diagrams show the PLANNED flow, which is architecturally correct but not yet matching running code.
   - **Recommendation:** Mark clearly that workflows.md shows the target architecture, not just current state.

2. **Cross-artifact validation**
   - Evidence-ID resolution across artifacts, confidence caps requiring ledger inputs, and threshold equality validation are documented as deferred to Tasks 5/6/8.
   - These are well-documented as deferred but represent significant validation logic not yet in code.

3. **`metric_name` / `metric_value` on EvidenceItem**
   - `data_models.md` documents `EvidenceItem` with 16 fields matching `models.py`
   - The `evidence/types.py` dataclass has `metric_name`/`metric_value` fields that `models.EvidenceItem` lacks
   - The pipeline uses `MappedLedger.metric_index` as a workaround
   - **Recommendation:** This discrepancy is documented in work-in-progress steering. Once resolved, update data_models.md.

---

## Recommendations

### High Priority
1. Update documentation when Task 1b (`config.py`, `clock.py`, `ports.py`) lands
2. Update when the full pipeline wiring (Task 3 completion) is done
3. Add Streamlit UI documentation when `streamlit_app.py` is created

### Medium Priority
4. Document the prototype → canonical migration status more explicitly
5. Add a "current vs planned" indicator to workflow diagrams
6. Document the `lint.py` implementation when owned and written

### Low Priority
7. Create a detailed test fixture catalog if the fixture set grows significantly
8. Add deployment runbook details when EC2 setup is finalized
9. Document Dockerfile and docker-compose.yml when created
