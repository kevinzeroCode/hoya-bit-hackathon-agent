# Gold local Exit run log

Date: 2026-08-02  
Mode: `rehearsal`  
Path: deterministic Organizer CSV market evidence; no network, AWS credentials, or Bedrock.

| Asset | Run ID | Duration | Terminal state | Evidence | Missing artifacts | Artifact directory |
|---|---|---:|---|---:|---|---|
| BTC | `run_20260531_060000_btc` | < 1 s | `degraded` (deterministic no-Arbiter disclosure) | 5 | none | `artifacts/gold-local/run_20260531_060000_btc` |
| ETH | `run_20260531_060000_eth` | < 1 s | `degraded` (deterministic no-Arbiter disclosure) | 5 | none | `artifacts/gold-local/run_20260531_060000_eth` |

Both runs were independent single-asset requests. Each produced the complete tracked
artifact set (`run_config.json`, `execution_log.jsonl`, `evidence.json`,
`evidence_list.json`, and `final_report.md`), with one run ID shared across its
configuration, ledger, log, and report. The degraded state is intentional: this local
Gold path validates deterministic market evidence and artifact honesty; schema-valid
live Bedrock remains covered by the separate Silver gate.

Verification:

- `PYTHONPATH=src python scripts/run_acceptance.py` → BTC and ETH runs above.
- `PYTHONPATH=src python -m pytest tests/acceptance -m "not live" -q` → `6 passed`.
- `ruff check tests/acceptance scripts/run_acceptance.py` → `All checks passed!`.
