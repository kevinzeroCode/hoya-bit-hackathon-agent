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

## Downstream consumer already written

`src/hoya_agent/reasoning/` (Task 6) was written before Task 1 existed. It takes
its schema classes by injection, so it compiles without `models.py`, but it
expects the names listed in `docs/ai/P3_CONTRACT_EXPECTATIONS.md`.

Treat that document as a consumer requirement to satisfy where possible. On any
conflict, `.kiro/steering/evidence-contracts.md` wins and the consumer is fixed.
