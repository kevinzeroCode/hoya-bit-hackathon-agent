# S8 / S9 / S9B runtime addendum

- Runtime seam: canonical `models.py` / `ports.py`; `_provisional_seams.py` is deleted.
- Orchestration: `DeadlineAwarePipeline`, `DeadlineManager`, 720-second analysis
  hard stop, Market/Research fork-join, honest branch degradation.
- Orchestration (2026-08-01 second pass): `DeadlineManager` carries per-stage
  budget milestones with proportional scaling and a finalize reserve;
  `RunStateMachine` owns the stage lifecycle and `WorkerStatus -> StageState`
  mapping; the fork-join cancels unfinished branches and then awaits them.
  The fixed optional-work skip order is enforced by trimming the `ResearchPlan`;
  the composition root declares which operations are optional, so S6 supplies
  that list before it can trigger in a live run.
- Models: execution-log and run-config shapes match the artifact contract;
  `RunContext` retains the immutable request and exposes convenience properties.
- Evidence: `build_trust_scorecards()` is deterministic and conclusion-only.
- Data: `classify_market_regime()` returns a canonical unavailable state;
  `build_comparison_evidence()` aligns UTC dates and stores numeric metric values.
- Dual asset: the orchestration projection balances asset/source buckets before
  the frozen Arbiter; the artifact ledger remains complete.
- Reporting: Trust/Regime/quantified invalidation plus dual-only section 12.
- Verification: see `scripts/verify_s8_s9_s9b.py` and
  `docs/S8-S9-S9B-implementation.md`. Silver live acceptance remains external.
