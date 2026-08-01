---
inclusion: always
---

# Work-in-Progress Guards

Current coordination state for `main@21e6f14` with S8 completion on PR #26. Design authority remains
in the other steering files; human-readable detail is in `docs/ACTIVE_WORK.md`.

## Status

- Complete: S1, S2, S3, S4, S5, S7, S8.
- Offline-complete: S9 and S9B.
- Partial: S0 and S6.
- Not complete: S10 and S11.
- S8 Silver is backed by the 2026-08-02 integrated live result (`1 passed in 50.15s`); do not
  extend that claim to Gold or deployment, and never describe offline S9/S9B smoke as live
  Gold or deployment success.
- The non-live pytest suite and `ruff check .` were verified on 2026-08-01 (S6 fifth pass):
  1215 passed / 0 failed (15 subtests), Ruff clean, `scripts/verify_s8_s9_s9b.py` PASS,
  `tests/live` skipped by default. A real provider run (`RUN_LIVE_TESTS=1`) gave
  8 passed / 4 skipped with no schema drift — see `docs/rehearsals/live-source-check.md`.
  Latest S8 branch evidence is 1143 passed / 3 skipped, Ruff clean.
  GitHub CI/status checks are still not configured.

## Frozen paths

Do not modify without owner agreement and focused regression coverage:

```text
src/hoya_agent/models.py
src/hoya_agent/config.py
src/hoya_agent/clock.py
src/hoya_agent/ports.py
src/hoya_agent/adapters/bedrock.py
src/hoya_agent/reasoning/
src/hoya_agent/evidence/policies.py
prompts/
tests/contract/
tests/unit/reasoning/
```

The S9B asset/source quota is implemented in the orchestration-side Arbiter projection.
Do not move it into frozen `reasoning/arbiter.py` without that owner's approval.
The complete Evidence Ledger remains the artifact of record and must not be truncated.

## Resolved seams

- Task 1a and 1b are complete.
- `_provisional_seams.py` and `tests/integration/test_s1_seam_bridge.py` are deleted.
- Application, artifact and orchestration code use canonical `models.py` / `ports.py`.
- `DeadlineAwarePipeline`, `DeadlineManager` and run-state derivation are present.
- 2026-08-01 (S4 second pass): `DeadlineManager` carries per-stage budget milestones
  (`Stage`, `deadline_for`, `budget_for`, `budget_seconds`, `for_run`) with proportional
  scaling and a `max(20%, min(60 s, half the run))` finalize reserve; `run_state.py` carries
  `RunStateMachine` and `stage_state_for(WorkerStatus)`; the fork-join cancels unfinished
  branches and then awaits them. Covered by `tests/unit/orchestration/test_deadline.py`,
  `test_run_state.py` and `tests/integration/test_fork_join.py` (53 passed). A caller-cancelled
  run finalizes all four artifacts labelled `cancelled` and then re-raises `CancelledError`
  (`tests/integration/test_cancellation.py`).
- Trust Scorecard, regime/unavailable, Evidence-backed invalidation and dual-asset comparison
  are present and covered by the PR #18 offline acceptance path.
- Frozen reasoning and prompts were not changed by PR #18.

## Open work

1. S3 canonical Streamlit Bronze, prohibited-advice lint and container shell.
2. S4 is complete. The fixed optional-work skip order lives in
   `orchestration/deadline.py` (`OptionalWork`, `SKIP_ORDER`, `plan_optional_work`) and is
   enforced by `DeadlineAwarePipeline._apply_skip_order`, which trims skipped steps out of
   the `ResearchPlan` before the frozen Research Agent receives it. Which operations count
   as optional is declared by the composition root (`optional_operations` /
   `counter_signal_operations`, empty by default), so S6 must supply that source list when
   it assembles the live pipeline or the order will never trigger in a real run.
3. S6 canonical baseline research acceptance: the four functional gaps are closed
   (2026-08-01 second pass) — deterministic `ConflictIndicator` generation is wired into the
   run (`evidence/ledger.build_conflict_indicators` + `orchestration/pipeline.finalize_analysis`),
   multi-fact extraction lives in `src/` (`reasoning/research_extractor.py`, added without
   modifying any frozen file), the remaining research sources have port-conforming wrappers
   (`CryptoPanicResearchAdapter`, `FearGreedResearchAdapter`,
   `OfficialAnnouncementsResearchAdapter` plus `adapters/_errors.py`), and the composition root
   declares the skip-order source lists (`application.build_research_pipeline`).
   Still open: the mock-transport adapter tests live in `tests/unit/data_evidence/` rather than
   the frozen `tests/contract/`, and `p2-etl-mvp/` is still tracked.
   Closed 2026-08-01 (fifth pass): the provisional-type unification — `evidence/types.py` is
   deleted, `evidence/drafts.py::PendingEvidence` (canonical draft + provenance) is the only
   draft type, and `evidence/processor.py` is the sole assigner of reliability, independence
   group, content hash and ids. The non-canonical `evidence/evidence_json.py` writer went with
   it. Also closed: one deadline-bound retry (`fetch_with_single_retry`), one shared
   `httpx.AsyncClient` per run owned by the registry, and the adapter-level official-mode test
   (`tests/unit/data_evidence/test_official_mode_sources.py`, which scans production code for
   fixture imports and recorded-response loaders). Live provider verification ran for real:
   8 passed / 4 skipped, no schema drift — `docs/rehearsals/live-source-check.md`.
4. S8 **closed 2026-08-02**: one schema-valid live Bedrock run through baseline market/research
   plus an independent fallback run.
   **The schema blocker recorded earlier is resolved (2026-08-01, third pass):**
   `reasoning/arbiter_output.py` (new file, no frozen file modified) defines `ArbiterOutput` —
   `AnalysisResult` minus the frozen request context, with nullable time ranges, which is
   exactly the shape the frozen `_fallback()` produces — plus `project_to_analysis_result()`
   and `ledger_view()`. `pipeline._run_arbiter()` applies the projection and
   `application.build_research_pipeline()` wires the Arbiter automatically when an `llm` is
   supplied. Three silent-degradation traps are pinned by tests: the boundary schema must use
   plain strings because `apply_confidence_caps()` compares with `str()`; the Arbiter must
   receive `ledger_view()` items or `_reliability_rank()` sees `"Reliability.high"` and the
   fallback emits zero claims; `_fallback()` renders assets as `"Asset.BTC"`.
   The scaffold is in place — `tests/live/` (guarded by the `live` marker **and**
   `RUN_LIVE_TESTS=1`, skipped by default) and `scripts/live_silver_run.py --mode live|fallback`.
   The fallback half ran offline on 2026-08-01: `run_20260801_160034_s0034`, degraded, four
   artifacts present. The live half was the environment blocker (no AWS credentials on this
   machine) and was completed on 2026-08-02 in the credentialed environment:
   `tests/live/test_live_silver_pipeline.py` → `1 passed in 50.15s`, schema-valid Bedrock
   result with all four artifacts present.
5. S10 two separate single-asset Gold runs and deadline/artifact acceptance.
6. S11 CI, ECR/EC2, rollback and one timed judged-flow rehearsal.
7. Remove repository-wide Ruff debt and run the complete non-live suite.
8. Configure GitHub CI/status checks and preserve the verified non-live/Ruff baseline.

## Hard guards

- H3 remains disabled; do not add Bull/Bear/Judge code, prompts or tests.
- Do not add new providers or artifact formats during the committed path.
- Do not treat `p2-etl-mvp/` as the canonical package tree.
- Do not claim a gate based only on file presence; record the actual executed evidence.
