"""S3 Bronze presenter — pure `RunSummary` → view-model mappings.

Framework-free on purpose (🚫 no Streamlit import) so it is unit-testable and the
"business logic in a callback" gate stays satisfied; `streamlit_app.py` is only glue.
Run-mode and terminal-state each map to a distinct visual token so `official`,
`rehearsal` and `demo` are unmistakable in the UI (design.md §UI / Req 2).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from hoya_agent.data.price_analysis import anomaly_days
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.triangulation import triangulate
from hoya_agent.models import EvidenceItem

# official / rehearsal / demo must be visually distinct (Req 2).
RUN_MODE_STYLE: dict[str, tuple[str, str]] = {
    "official": ("OFFICIAL", "🔴"),
    "rehearsal": ("REHEARSAL", "🟡"),
    "demo": ("DEMO", "⚪"),
}
TERMINAL_STYLE: dict[str, tuple[str, str]] = {
    "completed": ("完成", "✅"),
    "degraded": ("完成(含降級)", "🟠"),
    "failed": ("失敗", "❌"),
    "cancelled": ("取消", "⛔"),
}


def _value(x: Any) -> str:
    return str(getattr(x, "value", x))


def run_mode_badge(run_mode: Any) -> tuple[str, str]:
    key = _value(run_mode)
    return RUN_MODE_STYLE.get(key, (key.upper(), "•"))


def terminal_badge(state: Any) -> tuple[str, str]:
    key = _value(state)
    return TERMINAL_STYLE.get(key, (key, "•"))


def trust_funnel(evidence_ledger: dict[str, Any]) -> dict[str, Any]:
    """Distil an evidence.json ledger into the trust funnel + reliability mix.

    Pure and framework-free; computed from the run's own `evidence.json` artifact
    (no schema or pipeline change). Shows how many scattered items collapse into
    how few independent voices — the visible core of "多源資訊的信任提煉".
    """
    items = evidence_ledger.get("items", []) or []
    source_types = {i.get("source_type") for i in items if i.get("source_type")}
    groups = {i.get("independence_group") for i in items if i.get("independence_group")}
    mix = {"high": 0, "medium": 0, "low": 0}
    for i in items:
        rel = i.get("reliability")
        if rel in mix:
            mix[rel] += 1
    conflicts = len(evidence_ledger.get("conflict_indicators", []) or [])
    return {
        "evidence_count": len(items),          # ledger-admitted (post-dedup) items
        "source_type_count": len(source_types),
        "source_types": sorted(t for t in source_types if t),
        "independence_group_count": len(groups),
        "reliability_mix": mix,
        "conflict_count": conflicts,
    }


def triangulation_view(
    evidence_ledger: dict[str, Any],
    bars_by_asset: dict[str, Sequence[MarketBar]],
    *,
    sigma: float = 3.0,
    min_history: int = 365,
    window_days: int = 1,
) -> dict[str, Any]:
    """Cross-source triangulation (Gold-Plan G2): does a market anomaly day line
    up with independent research evidence gathered around the same day?

    Pure and framework-free, same shape as `trust_funnel`: computed post-run from
    the run's own `evidence.json` items plus the bars the run already loaded
    (`OrganizerCsvPipeline.last_bars_by_asset` or the live pipeline's equivalent).
    No schema or pipeline change, no second network fetch, no LLM. `bars_by_asset`
    with too little history for a stable sigma (see `data.price_analysis.anomaly_days`)
    degrades that asset to `available=False` with a reason instead of guessing.
    `sigma`/`min_history` default to `anomaly_days`'s own defaults; tests may
    override `min_history` to work with a small hand-computable fixture.
    """
    items = [EvidenceItem.model_validate(raw) for raw in evidence_ledger.get("items", []) or []]
    result: dict[str, Any] = {}
    for asset, bars in bars_by_asset.items():
        try:
            anomalies = anomaly_days(bars, sigma=sigma, min_history=min_history)
        except ValueError as exc:
            result[asset] = {"available": False, "reason": str(exc), "events": []}
            continue
        events = triangulate(anomalies, items, asset=asset, window_days=window_days)
        result[asset] = {
            "available": True,
            "events": [
                {
                    "day": event.day.isoformat(),
                    "simple_return": event.simple_return,
                    "z": event.z,
                    "strength": event.strength,
                    "corroborating_evidence_ids": list(event.corroborating_evidence_ids),
                    "source_types": list(event.source_types),
                    "independence_groups": list(event.independence_groups),
                    "note": event.note,
                }
                for event in events
            ],
        }
    return result


def agent_judgment_view(execution_log_jsonl: str, evidence_ledger: dict[str, Any]) -> dict[str, Any]:
    """Surface the Planner's per-question operation choice and the pipeline's
    own grounding/conflict disclosures in one judge-legible view (Task 15 / G4).

    Pure and framework-free, same shape as `trust_funnel`. Computes nothing new:
    the Planner's decision is read from the `plan_decision` execution-log event
    `orchestration/pipeline.py` already emits, and the degradation/conflict
    counts are read from the run's own `evidence.json` ledger — both already
    exist, this only collects them into one place instead of leaving a judge to
    diff the raw JSON.
    """
    plan_message = ""
    for line in (execution_log_jsonl or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("event_type") == "plan_decision":
            plan_message = event.get("message", "")
            break

    degradation_events = evidence_ledger.get("degradation_events", []) or []
    conflicts = evidence_ledger.get("conflict_indicators", []) or []
    return {
        "plan_decision": plan_message,
        "degradation_count": len(degradation_events),
        "degradation_messages": [
            e.get("message", "") for e in degradation_events if e.get("message")
        ],
        "conflict_count": len(conflicts),
    }


def summary_view(summary: Any) -> dict[str, Any]:
    """Map a RunSummary (provisional or canonical) into a plain view dict for the UI."""
    mode_label, mode_icon = run_mode_badge(summary.run_mode)
    term_label, term_icon = terminal_badge(summary.terminal_state)
    return {
        "run_id": getattr(summary, "run_id", ""),
        "run_mode_label": mode_label,
        "run_mode_icon": mode_icon,
        "terminal_label": term_label,
        "terminal_icon": term_icon,
        "evidence_count": summary.evidence_item_count,
        "confidence": _value(summary.confidence),
        "insufficient": bool(summary.insufficient_data),
        "degradation_notes": list(summary.degradation_notes),
        "report_markdown": summary.report_markdown or "",
        "artifacts": dict(summary.artifact_paths),
        "missing_artifacts": list(summary.missing_artifacts),
        "artifact_dir": summary.artifact_dir,
    }
