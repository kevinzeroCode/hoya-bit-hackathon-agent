"""Gold local Exit: two independent, coin-agnostic single-asset runs."""

from __future__ import annotations

import io
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import Asset, EvidenceLedger, RunMode, SourceType, TerminalState
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES, EVIDENCE_LEDGER, FINAL_REPORT, HTML_REPORT, RUN_CONFIG

pytestmark = pytest.mark.acceptance

ANALYSIS_DATE = date(2026, 5, 31)
FROZEN_NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)
QUESTION = "請分析近期市場結構、波動與主要風險，所有數字必須有 Evidence。"


class FixedClock:
    def now_utc(self) -> datetime:
        return FROZEN_NOW

    def monotonic(self) -> float:
        return 1000.0


@pytest.mark.parametrize("asset", [Asset.BTC, Asset.ETH])
async def test_gold_asset_run_has_complete_traceable_artifacts(tmp_path: Path, asset: Asset) -> None:
    """Each asset is run separately; no dual-asset result can mask a missing path."""
    pipeline = OrganizerCsvPipeline(analysis_date=ANALYSIS_DATE)
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(),
        pipeline=pipeline,
        configured_sources=["public_market_data"],
        stdout=io.StringIO(),
    )
    request = build_request(
        question=QUESTION,
        assets=[asset],
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        analysis_as_of=FROZEN_NOW,
        run_id_suffix=asset.value.lower(),
    )

    summary = await service.run(request)
    run_dir = Path(summary.artifact_dir)
    assert {path.name for path in run_dir.iterdir()} == {*ARTIFACT_NAMES, HTML_REPORT}
    assert summary.missing_artifacts == []
    assert summary.terminal_state is TerminalState.degraded
    assert summary.evidence_item_count > 0

    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    html_report = (run_dir / HTML_REPORT).read_text(encoding="utf-8")

    assert config["run_id"] == summary.run_id == ledger.run_id
    assert config["terminal_status"] == "degraded"
    assert config["missing_artifacts"] == []
    assert config["effective_run_mode"] == "rehearsal"
    assert {item.asset for item in ledger.items} == {asset}
    assert all(item.source_type is SourceType.market for item in ledger.items)
    assert all(item.source_name == "public_market_data" for item in ledger.items)
    assert all(item.content_reference for item in ledger.items)
    assert all(item.evidence_id in report for item in ledger.items)
    assert html_report.startswith("<!doctype html>")
    assert summary.run_id in html_report


def test_supported_gold_assets_are_explicitly_allowlisted() -> None:
    assert {asset.value for asset in Asset} == {"BTC", "ETH", "SOL", "BNB", "XRP"}
