---
inclusion: always
---

# Development Workflow

## Source of Truth

- Treat `docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md` as the approved product boundary.
- Treat `.kiro/specs/hoya-market-agent/requirements.md`, `design.md`, and `tasks.md` as the executable implementation contract.
- Do not expand the MVP to H3 debate, S3, CloudWatch, extra adapters, or additional agent loops.

## Task Execution

1. Work on one unchecked required task or one dependency-safe parallel wave at a time.
2. Write or update a focused failing test before implementation.
3. Run the test and record the expected failure.
4. Implement only enough code to satisfy the requirement.
5. Run the focused test, then the relevant regression suite.
6. Update the corresponding checkbox in `tasks.md` in the same commit.
7. Commit a small, reviewable change with no secrets or generated runtime artifacts.

## Hard Gates

- Never claim a test passed without running it in the current workspace.
- Never silently replace live evidence with rehearsal fixtures in `official` mode.
- Never add unbounded loops, autonomous tool recursion, or retries outside the stage deadline.
- Never commit `.env`, AWS credentials, API keys, cached production responses, or participant secrets.
- Stop implementation at the Day 2 feature freeze; prioritize passing acceptance tests and demo recovery.

## Commit Evidence

Use conventional commit subjects such as `feat:`, `fix:`, `test:`, `docs:`, and `chore:`. Preserve task-level commits instead of squashing the entire Kiro implementation into one commit. Record Kiro task-to-commit mapping in `docs/evidence/kiro/README.md` as work is completed.
