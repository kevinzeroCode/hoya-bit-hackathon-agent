"""S4 cancellation: the one path that reaches `TerminalState.cancelled`.

Two levels, and the difference is the whole point. A branch cancelled beside a
sibling that produced evidence stays `degraded`, because that evidence still ships
(covered in `test_fork_join.py`). Cancellation becomes the *run's* terminal state
only when there is nothing left to report, or when the caller cancels the run.

An externally cancelled run must still leave four honest artifacts on disk, and
`asyncio.CancelledError` must still propagate — finalizing is not the same as
swallowing.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    RunContext,
    RunMode,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline
from hoya_agent.reporting.artifacts import DELIVERABLE_NAMES, RUN_CONFIG

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, tzinfo=UTC)


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


class HangingMarket:
    """Never finishes, so the acquisition window has to cancel it."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.cancelled = False

    async def execute(self, context: RunContext, emit) -> None:
        del context, emit
        self.entered.set()
        try:
            await asyncio.sleep(60.0)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class HangingPipeline:
    def __init__(self) -> None:
        self.entered = asyncio.Event()

    async def execute(self, context: RunContext, emit) -> None:
        del context, emit
        self.entered.set()
        await asyncio.sleep(60.0)
        raise AssertionError("the run should have been cancelled before this")


def _request(*, deadline_seconds: int = 900, suffix: str = "cn01") -> AnalysisRequest:
    return build_request(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix=suffix,
        deadline_seconds=deadline_seconds,
    )


async def test_the_hard_stop_with_no_evidence_reports_a_cancelled_run() -> None:
    # 1-second request: the ~188 ms acquisition window cancels the market branch
    # before any evidence exists, so there is nothing left to degrade to.
    market = HangingMarket()
    context = build_run_context(_request(deadline_seconds=1), Clock())
    events = []

    outcome = await DeadlineAwarePipeline(
        clock=Clock(), market_pipeline=market
    ).execute(context, events.append)

    assert market.cancelled
    assert outcome.ledger.items == []
    assert outcome.ledger.degradation_events, "an empty ledger must still say why"
    assert outcome.terminal_state is TerminalState.cancelled
    assert any("取消" in note for note in outcome.degradation_notes)
    assert any(event.event_type == "run_cancelled" for event in events)


async def test_an_externally_cancelled_run_still_delivers_four_artifacts(tmp_path) -> None:
    pipeline = HangingPipeline()
    request = _request(suffix="cn02")
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=Clock(),
        pipeline=pipeline,
        stdout=io.StringIO(),
    )

    task = asyncio.create_task(service.run(request))
    await pipeline.entered.wait()
    task.cancel()

    # Finalizing artifacts is not the same as suppressing cancellation.
    with pytest.raises(asyncio.CancelledError):
        await task

    run_dir = Path(tmp_path / "artifacts" / request.run_id)
    assert sorted(path.name for path in run_dir.iterdir()) == sorted(DELIVERABLE_NAMES)

    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    assert config["terminal_status"] == TerminalState.cancelled.value
    assert config["run_id"] == request.run_id
    assert config["missing_artifacts"] == []


async def test_a_cancelled_run_report_claims_nothing_it_cannot_support(tmp_path) -> None:
    pipeline = HangingPipeline()
    request = _request(suffix="cn03")
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=Clock(),
        pipeline=pipeline,
        stdout=io.StringIO(),
    )

    task = asyncio.create_task(service.run(request))
    await pipeline.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    run_dir = Path(tmp_path / "artifacts" / request.run_id)
    report = (run_dir / "final_report.md").read_text(encoding="utf-8")
    log = (run_dir / "execution_log.jsonl").read_text(encoding="utf-8")

    assert "目前無法可靠判定" in report
    assert report.count("\n## ") == 11, "the deterministic 11-section report still renders"
    assert '"event_type":"run_cancelled"' in log
    assert f'"status":"{TerminalState.cancelled.value}"' in log
