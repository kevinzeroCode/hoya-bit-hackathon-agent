"""Unit tests for the S3 Bronze presenter (pure, no Streamlit)."""

from __future__ import annotations

from types import SimpleNamespace

from hoya_agent.models import Reliability, RunMode
from hoya_agent.ui.presenter import run_mode_badge, summary_view, terminal_badge, trust_funnel


def test_three_run_modes_are_visually_distinct():
    labels = {run_mode_badge(m)[0] for m in (RunMode.official, RunMode.rehearsal, RunMode.demo)}
    icons = {run_mode_badge(m)[1] for m in (RunMode.official, RunMode.rehearsal, RunMode.demo)}
    assert labels == {"OFFICIAL", "REHEARSAL", "DEMO"}
    assert len(icons) == 3  # each mode a distinct icon


def test_terminal_badge_maps_states():
    assert terminal_badge(SimpleNamespace(value="completed"))[0] == "完成"
    assert terminal_badge(SimpleNamespace(value="degraded"))[0].startswith("完成")
    assert terminal_badge(SimpleNamespace(value="failed"))[1] == "❌"


def test_summary_view_maps_all_fields():
    summary = SimpleNamespace(
        run_id="run_20260531_000000_ui",
        run_mode=RunMode.rehearsal,
        terminal_state=SimpleNamespace(value="degraded"),
        evidence_item_count=6,
        confidence=Reliability.low,
        insufficient_data=True,
        degradation_notes=["no arbiter in this increment"],
        report_markdown="# report",
        artifact_paths={"evidence.json": "/tmp/x/evidence.json"},
        missing_artifacts=[],
        artifact_dir="/tmp/x",
    )
    view = summary_view(summary)
    assert view["run_mode_label"] == "REHEARSAL"
    assert view["evidence_count"] == 6
    assert view["confidence"] == "low"
    assert view["insufficient"] is True
    assert view["report_markdown"] == "# report"
    assert "evidence.json" in view["artifacts"]
    assert view["degradation_notes"] == ["no arbiter in this increment"]


def test_trust_funnel_distils_ledger():
    ledger = {
        "items": [
            {"source_type": "news", "reliability": "medium", "independence_group": "coindesk.com"},
            {"source_type": "news", "reliability": "medium", "independence_group": "coindesk.com"},  # repost
            {"source_type": "market", "reliability": "high", "independence_group": "organizer"},
            {"source_type": "social", "reliability": "low", "independence_group": "reddit.com"},
        ],
        "conflict_indicators": [{"claim": "x"}],
    }
    f = trust_funnel(ledger)
    assert f["evidence_count"] == 4
    assert f["source_type_count"] == 3            # news, market, social
    assert f["independence_group_count"] == 3     # two coindesk items collapse to one group
    assert f["reliability_mix"] == {"high": 1, "medium": 2, "low": 1}
    assert f["conflict_count"] == 1


def test_trust_funnel_handles_empty_ledger():
    f = trust_funnel({})
    assert f["evidence_count"] == 0
    assert f["reliability_mix"] == {"high": 0, "medium": 0, "low": 0}
