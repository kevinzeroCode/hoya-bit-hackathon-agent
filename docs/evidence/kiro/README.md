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
