"""A model safety-lint hit must degrade, not abort artifact finalization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.fakes import FixedClock

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import AnalysisResult, Asset, EvidenceLedger, RunMode, TerminalState
from hoya_agent.orchestration.pipeline import PipelineOutcome
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES, HTML_REPORT

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "vertical_slice"


class UnsafePipeline:
    async def execute(self, context, emit) -> PipelineOutcome:
        ledger = EvidenceLedger.model_validate(
            json.loads((FIXTURE_DIR / "evidence.json").read_text(encoding="utf-8"))
        ).model_copy(update={"run_id": context.run_id})
        result = AnalysisResult.model_validate(
            json.loads((FIXTURE_DIR / "analysis_result.json").read_text(encoding="utf-8"))
        ).model_copy(update={"run_id": context.run_id, "direct_answer": "建議減倉以控制風險"})
        return PipelineOutcome(
            ledger=ledger,
            result=result,
            terminal_state=TerminalState.completed,
        )


async def test_advice_lint_failure_falls_back_and_writes_all_artifacts(tmp_path: Path) -> None:
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(NOW),
        pipeline=UnsafePipeline(),
    )
    request = build_request(
        question="ETH 過去兩週表現與主要風險?",
        assets=[Asset.ETH],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix="lint01",
    )

    summary = await service.run(request)
    run_dir = Path(summary.artifact_dir)
    assert summary.terminal_state is TerminalState.degraded
    assert summary.insufficient_data is True
    assert set(ARTIFACT_NAMES) | {HTML_REPORT} == {path.name for path in run_dir.iterdir()}
    assert "減倉" not in (run_dir / "final_report.md").read_text(encoding="utf-8")
    assert "減倉" not in (run_dir / HTML_REPORT).read_text(encoding="utf-8")
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    assert config["missing_artifacts"] == []
