---
inclusion: always
---

# Work-in-Progress Guards

Current coordination state for `main@d7245e4` after PR #18. Design authority remains
in the other steering files; human-readable detail is in `docs/ACTIVE_WORK.md`.

## Status

- Complete: S1, S2, S5, S7.
- Offline-complete: S9 and S9B.
- Partial: S0, S4, S6 and S8.
- Not complete: S3, S10 and S11.
- Never describe offline S8/S9/S9B smoke as live Silver, Gold or deployment success.
- Full pytest/Ruff and GitHub CI/status checks are not currently verified.

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
- Trust Scorecard, regime/unavailable, Evidence-backed invalidation and dual-asset comparison
  are present and covered by the PR #18 offline acceptance path.
- Frozen reasoning and prompts were not changed by PR #18.

## Open work

1. S3 canonical Streamlit Bronze, prohibited-advice lint and container shell.
2. S4 fake-clock, cancellation and fork-join acceptance coverage.
3. S6 canonical baseline research acceptance and remaining normalization gaps.
4. S8 one schema-valid live Bedrock run through baseline market/research plus an independent fallback run.
5. S10 two separate single-asset Gold runs and deadline/artifact acceptance.
6. S11 CI, ECR/EC2, rollback and one timed judged-flow rehearsal.
7. Remove repository-wide Ruff debt and run the complete non-live suite.

## Hard guards

- H3 remains disabled; do not add Bull/Bear/Judge code, prompts or tests.
- Do not add new providers or artifact formats during the committed path.
- Do not treat `p2-etl-mvp/` as the canonical package tree.
- Do not claim a gate based only on file presence; record the actual executed evidence.
