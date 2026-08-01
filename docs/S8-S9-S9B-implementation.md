# S8 / S9 / S9B implementation note

## Delivered offline behavior

- `DeadlineAwarePipeline` fixes the six-stage order and uses a 720-second
  monotonic analysis hard stop, leaving the 780/900-second artifact and
  competition windows to `ApplicationService` finalization.
- Planner runs before a Market/Research fork-join. Branch timeout or provider
  failure becomes an explicit degradation note; the available branch and the
  four fixed artifacts are preserved.
- The S1↔S2 provisional runtime seam is retired. Application, artifacts and
  orchestration use canonical `models.py` and `ports.py` contracts.
- `evidence/trust.py` builds ordinal per-conclusion Trust Scorecards from the
  ledger, links and conflict indicators. It performs no I/O and creates no
  synthetic probability.
- Market regime classification has a canonical `unavailable` result. Regime
  evidence and thresholds are deterministic and derived from each asset's own
  history.
- A two-asset request remains one run with one cutoff and one complete ledger.
  Cross-asset calculations use intersecting UTC dates only, never forward-fill,
  and never compare different assets' base volume.
- The Arbiter receives a bounded, asset/source-balanced projection; the full
  ledger artifact is never truncated. The frozen `reasoning/arbiter.py` remains
  unchanged.
- A dual-asset report adds section 12, cites comparison Evidence IDs, renders a
  comparative Claim containing both assets, and keeps each asset's regime label
  separate.

## Verification performed

`scripts/verify_s8_s9_s9b.py` passed offline on Python 3.12 with the organizer
BTC/ETH dataset. It verifies one run/cutoff/ledger, four fixed artifacts,
Planner/Research progress events, Trust Scorecard, Market Regime, a comparative
Claim and the dual-only report section. Focused trust, regime, aligned comparison
and Arbiter-budget unit smokes also passed.

## Gate that remains external

This implementation does not claim Silver Exit yet. The full pytest/Ruff tools
were absent from the available offline package cache, and the required live
Bedrock + baseline market + baseline research acceptance needs AWS credentials
and network access. Run the repository's standard non-live suite first, then the
opt-in live tests in that environment. A fallback-only run never counts as the
Silver live success.
