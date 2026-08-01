# Kiro Development Evidence

This directory records genuine Kiro-assisted development activity for the hackathon submission. Do not backfill or fabricate evidence.

Task owners send their task number, branch, exact verification command/result, commit SHA, operator, and Kiro session summary to P1. P1 appends the ledger row after the implementation commit exists; this central ownership prevents four parallel branches from editing this file at once.

## Required Records

For every Kiro-executed task, append a row after the commit exists:

| Kiro task | Commit | Operator | Verification | Notes |
|---|---|---|---|---|
| _Example: 2.1_ | _short SHA_ | _team member_ | _exact command_ | _Kiro session or decision summary_ |

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
