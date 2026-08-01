"""Serialize the Evidence Ledger to the competition's fixed `evidence.json` artifact.

Real, traceable, secrets-free (drafts already strip credentials via
`query_or_parameters`). `run_mode` defaults to "rehearsal": real data, but NOT
the official judged run — never write "official" unless it is the actual judged
run on Bedrock. Datetimes are emitted as ISO-8601 UTC strings.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from evidence.types import EvidenceLedger

UTC = timezone.utc
_RUN_MODES = ("official", "rehearsal", "demo")


def _json_default(o: object) -> str:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    raise TypeError(f"not JSON-serializable: {type(o).__name__}")


def _isoify(d: dict) -> dict:
    """Convert any datetime/date values in an evidence dict to ISO strings."""
    return {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in d.items()}


def build_evidence_payload(
    ledger: EvidenceLedger,
    *,
    asset: str,
    analysis_as_of: date,
    run_id: str,
    run_mode: str = "rehearsal",
    llm_provider: str = "none",
) -> dict:
    if run_mode not in _RUN_MODES:
        raise ValueError(f"run_mode must be one of {_RUN_MODES}")
    return {
        "schema": "evidence-ledger/p2-prototype-v1",
        "run_id": run_id,
        "run_mode": run_mode,
        "asset": asset,
        "analysis_as_of": analysis_as_of.isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "llm_provider": llm_provider,
        "summary": {
            "evidence_count": len(ledger.items),
            "dropped_duplicates": ledger.dropped_duplicates,
            "source_type_count": ledger.source_type_count,
            "independence_group_count": ledger.independence_group_count,
        },
        "evidence": [_isoify(asdict(item)) for item in ledger.items],
    }


def dump_evidence_json(ledger: EvidenceLedger, path: str | Path, **kwargs) -> dict:
    payload = build_evidence_payload(ledger, **kwargs)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return payload
