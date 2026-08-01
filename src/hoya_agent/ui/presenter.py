"""S3 Bronze presenter — pure `RunSummary` → view-model mappings.

Framework-free on purpose (🚫 no Streamlit import) so it is unit-testable and the
"business logic in a callback" gate stays satisfied; `streamlit_app.py` is only glue.
Run-mode and terminal-state each map to a distinct visual token so `official`,
`rehearsal` and `demo` are unmistakable in the UI (design.md §UI / Req 2).
"""

from __future__ import annotations

from typing import Any

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
