---
inclusion: always
---

# Work-in-Progress Guards

Short-lived coordination state. Everything here is a *current fact about this
repository*, not a design rule — the design rules live in the other steering
files. Keep this file small; it is loaded on every Kiro invocation.

Update it whenever a task is claimed, completed, or frozen. `docs/ACTIVE_WORK.md`
carries the human-readable detail; this file carries only what an agent must obey.

## Frozen paths — do not create, modify, refactor, or "improve"

These are completed and covered by passing tests. Touching them silently breaks
another owner's verified work.

```text
src/hoya_agent/adapters/bedrock.py
src/hoya_agent/reasoning/
src/hoya_agent/evidence/types.py
src/hoya_agent/evidence/policies.py
tests/unit/evidence/test_policies.py
prompts/
tests/contract/
tests/unit/reasoning/
```
If a change genuinely requires editing one of these, stop and report why instead
of editing. The owner must agree first.

**`src/hoya_agent/evidence/types.py` is deliberately redundant with `models.py`
and must survive Task 1a untouched.** It is a provisional frozen-dataclass
stand-in whose field names were chosen to match the contracts, so that the two
downstream tasks could start moving modules in before `models.py` existed.
Task 1a creates `models.py` alongside it and does **not** delete, merge or
rewrite it — a separate later task performs that swap once both halves have
landed. Deleting it now breaks the two branches currently importing
`EvidenceDraft` from it.

Package markers under `src/hoya_agent/` are intentionally empty: `__init__.py`
at the package root and under `adapters/` and `evidence/`. Leave them as they are.

## Resolved specification ambiguities

Record every resolution here so the next session does not re-litigate it.

- **Task 1a contract acceptance is COMPLETE.** The original Task 1a commit
  (`b9f57db`) landed `models.py`; a subsequent Codex contract review returned
  `BLOCKING-ISSUES-FOUND` with 14 findings. The corrective commit
  `fix: align core models with evidence contracts` on branch
  `task/1a-contracts-core` addressed the accepted findings. A second Codex
  review on 2026-08-01 cleared the corrective pass (205 model tests passed,
  362 unit+contract tests passed, ruff clean, zero invalid-payload probe
  failures).

  Deferrals recorded by the corrective commit's disposition table (still open):
  - Clock-freeze of official `analysis_as_of` → Task 1b (RunContext + Clock).
  - Configured clock tolerance for fetched-vs-published slack → Task 1b.
  - Ledger `published_at <= analysis_as_of` cutoff → Task 5 (Evidence Processor).
  - Cross-artifact evidence-ID resolution (Link/Scorecard/InvalidationCondition
    against the ledger) → Task 5 / Task 8 (integration wiring).
  - `InvalidationCondition.threshold` equality against ledger value → Task 6
    (Arbiter/Renderer).
  - Confidence caps requiring ledger/conflict inputs (material conflict,
    independence-group count, stale-cache-only) → Task 5 / Task 6.
  - Configured maximum `question` length → Task 1b (Settings).

  Downstream stand-in contracts in `tests/unit/reasoning/_stubs.py` remain
  frozen. Swapping `_stubs.py` for the real models is still a later task and
  requires the owner's agreement.

- **`invalidation_conditions` shape.** `evidence-contracts.md` §7 shows a string
  list on `Claim`; §16.4 defines a structured object. Resolution:
  `Claim.invalidation_conditions` is `list[str]`;
  `AnalysisResult.invalidation_conditions` is `list[InvalidationCondition]`.
  Rationale: §16.4 quantified thresholds are a result-level product
  (Requirement 16 AC6), while §7's example is claim-level.

## Task 1 split

Task 1 is executed as two Kiro runs, 1a then 1b, because a single run producing
~25 contract types plus ports, config, and fakes is where field-name drift
happens — and `models.py` is imported by all four owners.

- **1a** — normative data contracts (`pyproject.toml`, `models.py`, model tests).
- **1b** — runtime seams (`config.py`, `clock.py`, `ports.py`, `tests/fakes.py`,
  `tests/conftest.py`, and the remaining plumbing models).

Do not tick Task 1's parent checkbox until both halves are done.

## Task 2 (S2) landed before Task 1b — provisional seam in place

Task 2 (fixture vertical slice) is **complete** on branch
`task/2-fixture-vertical-slice`: `application.py`, `reporting/artifacts.py`,
`reporting/renderer.py`, the `tests/fixtures/vertical_slice/` pair, and the
offline four-artifact integration test. Verified on Python 3.12.13:
422 passed / 6 skipped, `ruff check .` clean.

It landed **before Task 1b**, so the four runtime seams 1b owns are stubbed in
`src/hoya_agent/_provisional_seams.py` (`ExecutionEvent`, `RunConfigSnapshot`,
`RunSummary`, `RunContext`, `Clock`, `ProgressSink`, plus Task 3's
`TerminalState` / `AnalysisPipeline` / `PipelineOutcome`). Field names are copied
verbatim from `evidence-contracts.md` §13/§14.

- **Task 1b owner: do not work around this file.** Define the real names in
  `models.py` / `ports.py` as planned. On any disagreement the contract and 1b
  win, and S2 is the side that changes.
- `tests/integration/test_s1_seam_bridge.py` skips while the real seams are
  absent and starts enforcing field-name parity the moment they exist; when every
  seam has landed it fails on purpose to demand the swap.
- The swap procedure is in `docs/ai/S2_CONTRACT_EXPECTATIONS.md` §4. It touches
  only `application.py`, `reporting/artifacts.py` and
  `tests/integration/test_vertical_slice.py`, then deletes the stand-in and the
  bridge test.
- S2 deliberately did **not** create `tests/conftest.py`, `tests/fakes.py`,
  `config.py`, `clock.py`, `ports.py` or `reporting/lint.py`. Fixture loaders sit
  in `tests/unit/reporting/conftest.py` until 1b's shared conftest exists.

**`reporting/lint.py` is still nobody's committed file.** It appears in
`structure.md` and `Implementation-Plan.md` S3 but in no `tasks.md` file list.
`renderer.render(result, ledger, lint=hook)` already accepts it; until the UI
owner lands it, the prohibited-advice check exists only in the S2 tests.

The three shapes first written to disk by S2 — the `run_config.json` snapshot,
the `execution_log.jsonl` event, and the `evidence.json` container — may gain
fields later but **must not be renamed**.

## Downstream consumer already written

`src/hoya_agent/reasoning/` (Task 6) was written before Task 1 existed. It takes
its schema classes by injection, so it compiles without `models.py`, but it
expects the names listed in `docs/ai/P3_CONTRACT_EXPECTATIONS.md`.

Treat that document as a consumer requirement to satisfy where possible. On any
conflict, `.kiro/steering/evidence-contracts.md` wins and the consumer is fixed.
