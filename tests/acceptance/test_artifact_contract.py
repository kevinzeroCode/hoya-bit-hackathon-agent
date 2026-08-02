"""Deterministic artifact and degradation checks for the Gold local gate."""

from __future__ import annotations

import io
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import Asset, EvidenceLedger, RunMode, TerminalState
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from hoya_agent.reporting.artifacts import (
    ARTIFACT_NAMES,
    EVIDENCE_LEDGER,
    EVIDENCE_LIST,
    EXECUTION_LOG,
    FINAL_REPORT,
    HTML_REPORT,
)

pytestmark = pytest.mark.acceptance

NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)


class FixedClock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


def _request(asset: Asset = Asset.BTC):
    return build_request(
        question="請提供可追溯的市場分析與限制說明。",
        assets=[asset],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix="contract",
    )


async def test_every_fixed_artifact_is_parseable_and_checksumed(tmp_path: Path) -> None:
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(),
        pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        stdout=io.StringIO(),
    )
    summary = await service.run(_request())
    run_dir = Path(summary.artifact_dir)
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))

    assert {path.name for path in run_dir.iterdir()} == {*ARTIFACT_NAMES, HTML_REPORT}
    assert config["run_id"] == summary.run_id
    assert config["missing_artifacts"] == []
    assert set(config["artifact_checksums"]) == {*ARTIFACT_NAMES, HTML_REPORT} - {"run_config.json"}
    assert all(len(value) == 64 for value in config["artifact_checksums"].values())
    EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    assert isinstance(json.loads((run_dir / EVIDENCE_LIST).read_text(encoding="utf-8")), list)
    assert (run_dir / EXECUTION_LOG).read_text(encoding="utf-8").strip()
    assert (run_dir / FINAL_REPORT).read_text(encoding="utf-8").count("\n## ") == 11
    assert (run_dir / HTML_REPORT).read_text(encoding="utf-8").startswith("<!doctype html>")


async def test_missing_baseline_market_data_is_an_explicit_degraded_run(tmp_path: Path) -> None:
    empty_data = tmp_path / "empty-data"
    empty_data.mkdir()
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(),
        pipeline=OrganizerCsvPipeline(data_dir=empty_data, analysis_date=date(2026, 5, 31)),
        configured_sources=["public_market_data"],
        stdout=io.StringIO(),
    )

    summary = await service.run(_request())
    run_dir = Path(summary.artifact_dir)
    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))

    assert {path.name for path in run_dir.iterdir()} == {*ARTIFACT_NAMES, HTML_REPORT}
    assert summary.terminal_state in {TerminalState.degraded, TerminalState.failed}
    assert ledger.items == []
    assert ledger.degradation_events
    assert "insufficient" in (run_dir / FINAL_REPORT).read_text(encoding="utf-8").lower()
