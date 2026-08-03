---
inclusion: always
---

# Development Workflow

## Source of Truth

- Treat `docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md` as the approved product boundary.
- Follow `docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md` for role ownership, task branches, pairing, handoffs, and feature freeze.
- Follow `docs/kiro-team-playbook.md` for each person's exact branch, Kiro prompt, start gate, task closeout, and evidence handoff.
- Treat `.kiro/specs/hoya-market-agent/requirements.md`, `design.md`, and `tasks.md` as the executable implementation contract.
- **Competition ended 2026-08-02; Gold local Exit, deployment and CD all passed.** The Day 2
  feature freeze and the "do not expand the MVP" rule below applied only to Tasks 0-12, which
  stay frozen as shipped (do not re-touch them without a reason tied to a real bug). Tasks 13
  and up in `tasks.md` are approved post-competition scope — H3, CoinGecko, the five-asset
  matrix and Platinum/production extensions are explicitly in scope for those tasks. Every
  other rule on this page (TDD, status-block honesty, no secrets, no unbounded loops) still
  applies unchanged.
- ~~Do not expand the MVP to H3 debate, S3, CloudWatch, extra adapters, or additional agent loops.~~ Applied only through Task 12; see above.

## Task Execution

1. Work on one unchecked required task or one dependency-safe parallel wave at a time.
2. Write or update a focused failing test before implementation.
3. Run the test and record the expected failure.
4. Implement only enough code to satisfy the requirement.
5. Run the focused test, then the relevant regression suite.
6. Update the corresponding checkbox in `tasks.md` in the same commit.
7. Update your stage's status in `docs/Implementation-Plan.md` in the same commit — both the
   §1.1 snapshot row and the stage's own status block. Required for any change to `src/`,
   `tests/`, or artifact behaviour.
8. Commit a small, reviewable change with no secrets or generated runtime artifacts.

## Hard Gates

- Never claim a test passed without running it in the current workspace.
- Never push a change to `src/`, `tests/`, or artifact behaviour while
  `docs/Implementation-Plan.md` still describes the old state. On 2026-08-01 that file went
  stale twice within half a day — once still calling Bedrock unverified after it had been
  proven working, once still calling S2 the blocking critical path after it had merged.
  Either one costs another owner half a day of redone or blocked work, because a status
  table that is present but wrong gets believed, whereas an absent one makes people check.
  Status blocks record what was actually run — real test counts, the `ruff` result, and the
  traps hit along the way — not what is planned.
- Never silently replace live evidence with rehearsal fixtures in `official` mode.
- Never add unbounded loops, autonomous tool recursion, or retries outside the stage deadline.
- Never commit `.env`, AWS credentials, API keys, cached production responses, or participant secrets.
- ~~Stop implementation at the Day 2 feature freeze; prioritize passing acceptance tests and demo recovery.~~ The Day 2 freeze applied only to Tasks 0-12 (the competition MVP, already shipped). Tasks 13+ are post-competition work and are not subject to it.

## Commit Evidence

Use conventional commit subjects such as `feat:`, `fix:`, `test:`, `docs:`, and `chore:`. Preserve task-level commits instead of squashing the entire Kiro implementation into one commit. Record Kiro task-to-commit mapping in `docs/evidence/kiro/README.md` as work is completed.

Task owners send their task number, branch, verification command/result, commit SHA, and Kiro session summary to P1. P1 updates the shared evidence ledger after merge or at a checkpoint so parallel branches do not conflict on the same file.
