"""Run/data-mode honesty at the ApplicationService boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import (
    Asset,
    DataMode,
    DegradationEvent,
    EvidenceLedger,
    RunMode,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import PipelineOutcome
from tests.fakes import FixedClock

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 1, 8, tzinfo=UTC)


class ModePipeline:
    def __init__(self, effective_data_mode: DataMode) -> None:
        self.effective_data_mode = effective_data_mode

    async def execute(self, context, emit):
        del emit
        return PipelineOutcome(
            ledger=EvidenceLedger(
                run_id=context.run_id,
                analysis_as_of=context.analysis_as_of,
                run_mode=context.run_mode,
                degradation_events=[
                    DegradationEvent(
                        stage="gather",
                        event_type="fixture_or_fallback",
                        source="mode-test",
                        message=f"effective data mode: {self.effective_data_mode.value}",
                        timestamp=NOW,
                    )
                ],
            ),
            result=None,
            terminal_state=TerminalState.degraded,
            degradation_notes=["mode-test intentionally produced no evidence"],
            effective_data_mode=self.effective_data_mode,
        )


async def _run(tmp_path, run_mode: RunMode, data_mode: DataMode):
    clock = FixedClock(NOW, monotonic_value=10.0)
    request = build_request(
        question="BTC 市場狀態？",
        assets=[Asset.BTC],
        run_mode=run_mode,
        now=NOW,
        run_id_suffix=f"m{run_mode.value[:2]}",
    )
    service = ApplicationService(
        artifact_root=tmp_path,
        clock=clock,
        pipeline=ModePipeline(data_mode),
    )
    summary = await service.run(request)
    payload = json.loads(
        (tmp_path / request.run_id / "run_config.json").read_text(encoding="utf-8")
    )
    return summary, payload


async def test_rehearsal_fixture_is_explicit_in_summary_and_run_config(tmp_path) -> None:
    summary, payload = await _run(tmp_path, RunMode.rehearsal, DataMode.fixture)

    assert summary.effective_data_mode is DataMode.fixture
    assert payload["requested_data_mode"] == "fixture"
    assert payload["effective_data_mode"] == "fixture"


async def test_demo_recorded_fallback_is_explicit_in_summary_and_run_config(tmp_path) -> None:
    summary, payload = await _run(
        tmp_path, RunMode.demo, DataMode.recorded_fallback
    )

    assert summary.effective_data_mode is DataMode.recorded_fallback
    assert payload["requested_data_mode"] == "live"
    assert payload["effective_data_mode"] == "recorded_fallback"


async def test_official_rejects_non_live_effective_data_mode(tmp_path) -> None:
    with pytest.raises(ValidationError, match="official"):
        await _run(tmp_path, RunMode.official, DataMode.fixture)


def test_official_cutoff_cannot_be_caller_supplied() -> None:
    with pytest.raises(ValueError, match="freezes analysis_as_of"):
        build_request(
            question="BTC 市場狀態？",
            assets=[Asset.BTC],
            run_mode=RunMode.official,
            now=NOW,
            analysis_as_of=NOW,
            run_id_suffix="cutoff",
        )
