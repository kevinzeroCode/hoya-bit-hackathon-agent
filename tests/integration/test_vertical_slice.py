"""S2 vertical slice: one offline rehearsal request through the real ApplicationService.

No network, no Bedrock, no AWS credentials. The only stubbed collaborator is the
analysis pipeline (Task 3), which here replays the committed fixtures.
"""

from __future__ import annotations

import io
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import build_settings

from hoya_agent.application import ApplicationService, build_request, make_run_id
from hoya_agent.models import (
    AnalysisResult,
    Asset,
    EvidenceLedger,
    ExecutionEvent,
    RunContext,
    RunMode,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import (
    AnalysisPipeline,
    EventEmitter,
    PipelineOutcome,
)
from hoya_agent.reporting.artifacts import (
    ARTIFACT_NAMES,
    EVIDENCE_LEDGER,
    EXECUTION_LOG,
    FINAL_REPORT,
    RUN_CONFIG,
)

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "vertical_slice"
FROZEN_NOW = datetime(2026, 5, 31, 0, 0, 0, tzinfo=UTC)
QUESTION = "BTC 近期市場行為可以由哪些因素解釋？"


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now
        self._monotonic = 1000.0

    def now_utc(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic


class RecordingProgress:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)


class FixturePipeline:
    """Stands in for Task 3's DeadlineAwarePipeline using committed fixtures."""

    def __init__(
        self,
        *,
        drop_analysis: bool = False,
        terminal_state: TerminalState = TerminalState.completed,
        observer=None,
    ) -> None:
        self.drop_analysis = drop_analysis
        self.terminal_state = terminal_state
        self.observer = observer
        self.contexts: list[RunContext] = []

    async def execute(self, context: RunContext, emit: EventEmitter) -> PipelineOutcome:
        self.contexts.append(context)
        if self.observer is not None:
            self.observer(context)
        ledger = _load_ledger(context.run_id)
        emit(
            ExecutionEvent(
                timestamp=FROZEN_NOW,
                run_id=context.run_id,
                run_mode=context.request.run_mode,
                stage="evidence_processor",
                event_type="stage_end",
                status="ok",
                output_count=len(ledger.items),
                message="fixture ledger ready",
            )
        )
        result = None if self.drop_analysis else _load_result(context.run_id)
        return PipelineOutcome(
            ledger=ledger,
            result=result,
            terminal_state=self.terminal_state,
            degradation_notes=[] if result else ["Arbiter 未產出可驗證結果（fixture 注入）。"],
            stage_durations_ms={"acquisition": 120, "evidence_processor": 30},
        )


def _load_ledger(run_id: str) -> EvidenceLedger:
    payload = json.loads((FIXTURE_DIR / "evidence.json").read_text(encoding="utf-8"))
    payload["run_id"] = run_id
    return EvidenceLedger.model_validate(payload)


def _load_result(run_id: str) -> AnalysisResult:
    payload = json.loads((FIXTURE_DIR / "analysis_result.json").read_text(encoding="utf-8"))
    payload["run_id"] = run_id
    return AnalysisResult.model_validate(payload)


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch) -> None:
    """Prove the slice needs neither network nor AWS credentials.

    `socket.socket` itself stays intact because the Windows asyncio event loop
    needs a local socket pair; blocking name resolution and outbound connects is
    what proves no provider call happens.
    """

    def no_network(*args, **kwargs):  # noqa: ANN002, ANN003 - guard signature is irrelevant
        raise AssertionError("the fixture vertical slice must not reach the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "BEDROCK_PRIMARY_MODEL_ID",
        "CRYPTOPANIC_API_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def _service(tmp_path: Path, pipeline: AnalysisPipeline, stdout: io.StringIO | None = None):
    return ApplicationService(
        settings=build_settings(tmp_path / "artifacts"),
        clock=FixedClock(FROZEN_NOW),
        pipeline=pipeline,
        stdout=stdout if stdout is not None else io.StringIO(),
    )


def _run_dir(summary) -> Path:
    """`RunSummary` records artifact paths, so the directory is derived, not stored."""
    return Path(next(iter(summary.artifact_paths.values()))).parent


def _missing(summary) -> list[str]:
    """What is absent from `artifact_paths` is exactly what failed to land."""
    return [name for name in ARTIFACT_NAMES if name not in summary.artifact_paths]


def _rehearsal_request(assets=(Asset.BTC,), question: str = QUESTION):
    return build_request(
        question=question,
        assets=list(assets),
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix="fx01",
        analysis_as_of=FROZEN_NOW,
    )


async def test_offline_rehearsal_run_writes_four_parseable_artifacts(tmp_path) -> None:
    progress = RecordingProgress()
    service = _service(tmp_path, FixturePipeline())

    summary = await service.run(_rehearsal_request(), progress=progress)

    run_dir = _run_dir(summary)
    assert sorted(p.name for p in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    assert _missing(summary) == []
    assert summary.terminal_state is TerminalState.completed
    assert summary.effective_run_mode is RunMode.rehearsal

    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    log_lines = [
        json.loads(line)
        for line in (run_dir / EXECUTION_LOG).read_text(encoding="utf-8").splitlines()
    ]

    # One run_id across all four artifacts and the UI summary.
    assert config["run_id"] == summary.run_id == ledger.run_id
    assert summary.run_id in report
    assert {line["run_id"] for line in log_lines if "run_id" in line} == {summary.run_id}

    assert config["effective_run_mode"] == "rehearsal"
    assert config["terminal_status"] == "completed"
    # run_config.json cannot checksum itself; the other three must all be recorded.
    assert set(config["artifact_checksums"]) == {EXECUTION_LOG, EVIDENCE_LEDGER, FINAL_REPORT}
    assert all(len(digest) == 64 for digest in config["artifact_checksums"].values())
    assert report.count("\n## ") == 11
    assert progress.events, "the UI must receive streamed events"
    assert {"run_start", "run_end"} <= {event.event_type for event in progress.events}


async def test_run_config_is_written_before_the_pipeline_starts(tmp_path) -> None:
    seen: list[bool] = []

    def observer(context: RunContext) -> None:
        run_dir = tmp_path / "artifacts" / context.run_id
        seen.append((run_dir / RUN_CONFIG).exists())

    await _service(tmp_path, FixturePipeline(observer=observer)).run(_rehearsal_request())
    assert seen == [True], "run_config.json must exist before any analysis work begins"


async def test_execution_log_streams_during_the_run(tmp_path) -> None:
    lines_seen: list[int] = []

    def observer(context: RunContext) -> None:
        log = tmp_path / "artifacts" / context.run_id / EXECUTION_LOG
        lines_seen.append(len(log.read_text(encoding="utf-8").splitlines()))

    await _service(tmp_path, FixturePipeline(observer=observer)).run(_rehearsal_request())
    assert lines_seen and lines_seen[0] >= 1, "events must be flushed while the run is in flight"


async def test_evidence_is_persisted_even_when_analysis_is_missing(tmp_path) -> None:
    service = _service(
        tmp_path,
        FixturePipeline(drop_analysis=True, terminal_state=TerminalState.degraded),
    )

    summary = await service.run(_rehearsal_request())
    run_dir = _run_dir(summary)

    assert sorted(p.name for p in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    assert summary.terminal_state is TerminalState.degraded
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert "| 資料是否不足 | 是 |" in report
    assert "deterministic insufficient-data fallback" in report

    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    assert len(ledger.items) == 5, "traceability survives an Arbiter failure"

    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert "目前無法可靠判定" in report
    assert report.count("\n## ") == 11
    for item in ledger.items:
        assert item.evidence_id in report

    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    assert config["terminal_status"] == "degraded"


async def test_report_states_no_fact_absent_from_the_fixtures(tmp_path) -> None:
    summary = await _service(tmp_path, FixturePipeline()).run(_rehearsal_request())
    report = (_run_dir(summary) / FINAL_REPORT).read_text(encoding="utf-8")
    fixture_text = (FIXTURE_DIR / "evidence.json").read_text(encoding="utf-8") + (
        FIXTURE_DIR / "analysis_result.json"
    ).read_text(encoding="utf-8")

    for claim_text in ("14 日報酬為 -4.88%", "z-score 為 +1.80"):
        assert claim_text in report and claim_text in fixture_text
    for term in ("買入", "賣出", "加倉", "減倉", "做多", "做空", "資產配置"):
        assert term not in report


async def test_rehearsal_run_is_never_labelled_official(tmp_path) -> None:
    summary = await _service(tmp_path, FixturePipeline()).run(_rehearsal_request())
    run_dir = _run_dir(summary)
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))

    assert "rehearsal" in report
    # The only permitted mention of official is the disclaimer that this is not one.
    assert "official（live 來源）" not in report
    assert "非 live official 結果" in report
    assert config["requested_run_mode"] == config["effective_run_mode"] == "rehearsal"
    for line in (run_dir / EXECUTION_LOG).read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        assert payload.get("run_mode", "rehearsal") == "rehearsal"


async def test_single_artifact_failure_is_disclosed_by_exact_filename(tmp_path) -> None:
    stdout = io.StringIO()
    run_id = make_run_id(FROZEN_NOW, "fx01")
    blocked = tmp_path / "artifacts" / run_id / FINAL_REPORT
    blocked.mkdir(parents=True)

    summary = await _service(tmp_path, FixturePipeline(), stdout=stdout).run(_rehearsal_request())

    assert _missing(summary) == [FINAL_REPORT]
    assert summary.terminal_state is TerminalState.degraded
    assert FINAL_REPORT in stdout.getvalue()

    run_dir = _run_dir(summary)
    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    assert FINAL_REPORT not in config["artifact_checksums"]
    log_text = (run_dir / EXECUTION_LOG).read_text(encoding="utf-8")
    assert FINAL_REPORT in log_text, "the failed write must be disclosed in the execution log"
    assert FINAL_REPORT not in config["artifact_checksums"]
    assert FINAL_REPORT in (run_dir / EXECUTION_LOG).read_text(encoding="utf-8")


async def test_unwritable_directory_discloses_all_four_filenames(tmp_path) -> None:
    stdout = io.StringIO()
    (tmp_path / "artifacts").write_text("this path is a file, not a directory", encoding="utf-8")

    summary = await _service(tmp_path, FixturePipeline(), stdout=stdout).run(_rehearsal_request())

    disclosure = stdout.getvalue()
    for name in ARTIFACT_NAMES:
        assert name in disclosure
    assert _missing(summary) == list(ARTIFACT_NAMES)
    assert summary.terminal_state is TerminalState.failed
    assert summary.artifact_paths == {}, "nothing landed, so no path may be recorded"


async def test_official_mode_freezes_the_cutoff_to_the_injected_clock(tmp_path) -> None:
    pipeline = FixturePipeline()
    service = _service(tmp_path, pipeline)
    request = build_request(
        question=QUESTION,
        assets=[Asset.BTC],
        run_mode=RunMode.official,
        now=FROZEN_NOW,
        run_id_suffix="fx01",
    )

    await service.run(request)

    assert pipeline.contexts[0].analysis_as_of == FROZEN_NOW


def test_official_mode_rejects_a_caller_supplied_cutoff() -> None:
    with pytest.raises(ValueError, match="analysis_as_of"):
        build_request(
            question=QUESTION,
            assets=[Asset.BTC],
            run_mode=RunMode.official,
            now=FROZEN_NOW,
            run_id_suffix="fx01",
            analysis_as_of=datetime(2026, 5, 1, tzinfo=UTC),
        )


async def test_question_asset_mismatch_logs_a_warning_and_keeps_assets(tmp_path) -> None:
    pipeline = FixturePipeline()
    summary = await _service(tmp_path, pipeline).run(
        _rehearsal_request(question="ETH 與 SOL 的走勢如何？")
    )

    assert tuple(pipeline.contexts[0].request.assets) == (Asset.BTC,)
    log_text = (_run_dir(summary) / EXECUTION_LOG).read_text(encoding="utf-8")
    assert "request_asset_mismatch" in log_text


async def test_run_id_and_report_are_deterministic_for_one_fixture_run(tmp_path) -> None:
    first = await _service(tmp_path / "a", FixturePipeline()).run(_rehearsal_request())
    second = await _service(tmp_path / "b", FixturePipeline()).run(_rehearsal_request())

    assert first.run_id == second.run_id == "run_20260531_000000_fx01"
    assert (
        (_run_dir(first) / FINAL_REPORT).read_text(encoding="utf-8")
        == (_run_dir(second) / FINAL_REPORT).read_text(encoding="utf-8")
    )
