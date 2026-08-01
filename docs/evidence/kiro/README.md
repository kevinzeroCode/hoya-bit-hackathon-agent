# Kiro Development Evidence

This directory records genuine Kiro-assisted development activity for the hackathon submission. Do not backfill or fabricate evidence.

Task owners send their task number, branch, exact verification command/result, commit SHA, operator, and Kiro session summary to P1. P1 appends the ledger row after the implementation commit exists; this central ownership prevents four parallel branches from editing this file at once.

## Required Records

For every Kiro-executed task, append a row after the commit exists:

| Kiro task | Commit | Operator | Verification | Notes |
|---|---|---|---|---|
| _Example: 2.1_ | _short SHA_ | _team member_ | _exact command_ | _Kiro session or decision summary_ |
| 1a | `b9f57db` | Kiro (spec-native execution) | `ruff check .` → All checks passed; `python -m pytest tests/unit tests/contract -q` → 254 passed | Executed from the spec sidebar against the eight always-included steering files, not a pasted prompt. Kiro caught two contract deviations on its own by re-reading `evidence-contracts.md` §16.2: `TrustScorecard` used a generic `count` where the contract names `distinct_groups`/`distinct_source_types`, and `DegradationEvent` was missing `source`. **Deviations from the workflow, recorded honestly:** (1) implementation preceded the tests — the "first write failing model tests" subtask is checked with an inline note, since the Red step was skipped; (2) the lint cleanup was driven by Claude Code diagnosis (ruff config `line-length = 120`, because `select = ["E", ...]` enables E501 at 88 while frozen code reaches 115 chars) with Kiro applying the edits; (3) environment setup (`uv` Python 3.12.13, `pip install -e ".[dev]"`) was done by Claude Code after Kiro stalled ~1 h on a venv that `uv venv` had created without `pip`. The contracts themselves — `pyproject.toml`, `models.py`, `tests/unit/test_models.py` — are Kiro's output. |
| 1a (corrective) | `4aef8ca` | Kiro, following Codex contract review | `python -m pytest tests/unit/test_models.py -q` → 205 passed; `python -m pytest tests/unit tests/contract -q` → 362 passed; `ruff check .` → All checks passed; invalid-payload probes → 0 failures | **Codex contract review process:** An independent Codex review of the original `b9f57db` commit returned `BLOCKING-ISSUES-FOUND` with 14 findings against `evidence-contracts.md`. Kiro produced the corrective commit addressing accepted findings. A second Codex review narrowed the gap to 6 remaining items, all deferred to explicit downstream owners. The final verification pass cleared all probes. **Frozen paths were not modified** — `src/hoya_agent/evidence/types.py`, `src/hoya_agent/evidence/policies.py`, `tests/unit/evidence/test_policies.py`, `src/hoya_agent/adapters/bedrock.py`, `src/hoya_agent/reasoning/`, `prompts/`, `tests/contract/`, and `tests/unit/reasoning/` remain untouched. **Documented deferrals (still open):** clock-freeze of official `analysis_as_of` → Task 1b; configured clock tolerance → Task 1b; ledger `published_at <= analysis_as_of` cutoff → Task 5; cross-artifact evidence-ID resolution → Task 5 / Task 8; `InvalidationCondition.threshold` equality against ledger value → Task 6; confidence caps requiring ledger/conflict inputs → Task 5 / Task 6; configured maximum `question` length → Task 1b. |

## Evidence Checklist

- [ ] `.kiro/specs/hoya-market-agent/requirements.md` reviewed by the team
- [ ] `.kiro/specs/hoya-market-agent/design.md` reviewed by the team
- [ ] `.kiro/specs/hoya-market-agent/tasks.md` reviewed and assigned
- [ ] Kiro task checkboxes updated with their implementation commits
- [ ] Representative Kiro session screenshots saved outside the source tree or under this directory with no secrets visible
- [ ] Final repository history retains task-level Kiro commits
- [ ] Submission materials explain which work Kiro generated, reviewed, or verified

Kiro artifacts describe the intended workflow; Git history, task updates, and session records demonstrate actual usage.

## Non-Kiro Attribution

CLAUDE.md reserves Task 1 and Task 2 for Kiro. Recording the converse here keeps the
submission honest about which tool produced what.

| Task | Produced by | Branch | Notes |
|---|---|---|---|
| 6 (bounded Planner / Research Agent / Arbiter) | Claude Code | `task/6-bedrock-reasoning` | Written before Task 1 existed. Schema classes are injected, so the stage logic is tested against stand-in contracts in `tests/unit/reasoning/_stubs.py`; rewiring to Kiro's `models.py` is the first item in `docs/ai/P3_HANDOFF.md` §5. Task 1 and Task 2 files were deliberately left untouched. |
| prompts (`planner-v1`, `research-extraction-v1`, `arbiter-v1`) | Claude Code | `task/6-bedrock-reasoning` | No Kiro involvement. |

Task 6 is **not** complete: it still needs the real shared contracts and one live
Bedrock run. Its checkbox in `tasks.md` stays unticked until both land.
