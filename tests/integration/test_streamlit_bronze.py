"""S3 Bronze — the offline UI path end to end (no Streamlit rendering).

Exercises exactly what the Streamlit button does: real ApplicationService +
deterministic OrganizerCsvPipeline, offline, producing the four fixed artifacts,
then the presenter view. No live HTTP / Bedrock / AWS.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hoya_agent.models import Asset, RunMode
from hoya_agent.reporting.advice_lint import advice_violations
from hoya_agent.ui.presenter import summary_view
from hoya_agent.ui.streamlit_app import ARTIFACT_ORDER, _run_offline

pytestmark = pytest.mark.integration


def test_bronze_offline_run_produces_four_artifacts_and_view():
    summary = _run_offline([Asset.BTC], "BTC 過去兩週表現?", RunMode.rehearsal)
    view = summary_view(summary)

    # four fixed artifacts exist on disk
    run_dir = Path(view["artifact_dir"])
    for name in ARTIFACT_ORDER:
        assert (run_dir / name).exists(), f"missing artifact {name}"

    assert view["run_mode_label"] == "REHEARSAL"
    assert view["evidence_count"] > 0            # real organizer-CSV evidence
    assert view["insufficient"] is True          # no Arbiter in this increment
    assert view["report_markdown"]               # deterministic report rendered
    assert not view["missing_artifacts"]


def test_bronze_is_coin_agnostic():
    summary = _run_offline([Asset.XRP], "XRP?", RunMode.demo)
    view = summary_view(summary)
    assert view["run_mode_label"] == "DEMO"
    assert view["evidence_count"] > 0


def test_bronze_ui_output_contains_no_investment_advice():
    """The exact text shown/downloaded in the UI must pass the advice lint.

    Belt-and-suspenders on top of the Renderer's own lint: assert at the UI
    surface that nothing prescriptive reaches the judge for every asset.
    """
    for asset in (Asset.BTC, Asset.ETH, Asset.SOL, Asset.BNB, Asset.XRP):
        view = summary_view(_run_offline([asset], "市場狀況?", RunMode.rehearsal))
        report = view["report_markdown"]
        assert report
        violations = advice_violations(report)
        assert violations == (), f"{asset.value} report leaked advice terms: {violations}"
