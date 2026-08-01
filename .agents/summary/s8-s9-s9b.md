# S8 / S9 / S9B runtime addendum

- Runtime seam: canonical `models.py` / `ports.py`; `_provisional_seams.py` is deleted.
- Orchestration: `DeadlineAwarePipeline`, `DeadlineManager`, 720-second analysis
  hard stop, Market/Research fork-join, honest branch degradation.
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
