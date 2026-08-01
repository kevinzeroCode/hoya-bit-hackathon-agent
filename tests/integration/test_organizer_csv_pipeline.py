"""The S2 vertical slice running on the deterministic market evidence that is on `main`.

This is the offline join between S2 (`ApplicationService` + artifacts + renderer)
and the data/evidence layer (`adapters/organizer_csv`, `data/market_worker`,
`evidence/processor`). It uses the organizer CSV only, so it needs no network, no
Bedrock and no AWS credentials, and every market number in the report traces back
to a deterministic tool output with an Evidence ID.

There is no Arbiter in this path yet, so the run is honestly `degraded` and the
report is the deterministic insufficient-data report over real evidence.
"""

from __future__ import annotations

import io
import json
import socket
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from hoya_agent._provisional_seams import ExecutionEvent, TerminalState
from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import Asset, EvidenceLedger, Reliability, RunMode, SourceType
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES, EVIDENCE_LEDGER, FINAL_REPORT

pytestmark = pytest.mark.integration

# The organizer dataset ends on 2026-05-31 UTC.
ANALYSIS_DATE = date(2026, 5, 31)
FROZEN_NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)
QUESTION = "這個資產近期的市場行為可以由哪些因素解釋？"


class FixedClock:
    def now_utc(self) -> datetime:
        return FROZEN_NOW

    def monotonic(self) -> float:
        return 1000.0


class RecordingProgress:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    def emit(self, event: ExecutionEvent) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch) -> None:
    def no_network(*args, **kwargs):  # noqa: ANN002, ANN003 - guard signature is irrelevant
        raise AssertionError("the organizer CSV path must not reach the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "BEDROCK_PRIMARY_MODEL_ID"):
        monkeypatch.delenv(name, raising=False)


def _run(tmp_path: Path, assets: list[Asset], stdout: io.StringIO | None = None):
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(),
        pipeline=OrganizerCsvPipeline(analysis_date=ANALYSIS_DATE),
        configured_sources=["public_market_data"],
        stdout=stdout if stdout is not None else io.StringIO(),
    )
    request = build_request(
        question=QUESTION,
        assets=assets,
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix="csv1",
        analysis_as_of=FROZEN_NOW,
    )
    progress = RecordingProgress()
    return service, request, progress


async def test_real_market_evidence_flows_into_the_four_artifacts(tmp_path) -> None:
    service, request, progress = _run(tmp_path, [Asset.BTC])

    summary = await service.run(request, progress=progress)
    run_dir = Path(summary.artifact_dir)

    assert sorted(p.name for p in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    assert summary.missing_artifacts == []
    assert summary.evidence_item_count > 0

    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    assert ledger.run_id == summary.run_id
    assert all(item.source_type is SourceType.market for item in ledger.items)
    assert all(item.reliability is Reliability.high for item in ledger.items)
    assert all(item.asset is Asset.BTC for item in ledger.items)
    assert all(item.independence_group == "organizer-public-market-data" for item in ledger.items)
    assert all(item.source_name == "public_market_data" for item in ledger.items)

    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    for item in ledger.items:
        assert item.evidence_id in report
        assert item.normalized_fact in report


async def test_no_arbiter_yet_is_reported_honestly(tmp_path) -> None:
    service, request, _ = _run(tmp_path, [Asset.BTC])
    summary = await service.run(request)
    run_dir = Path(summary.artifact_dir)

    assert summary.terminal_state is TerminalState.degraded
    assert summary.insufficient_data is True
    assert summary.confidence is Reliability.low

    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert "目前無法可靠判定" in report
    assert report.count("\n## ") == 11
    for term in ("買入", "賣出", "加倉", "減倉", "做多", "做空", "資產配置"):
        assert term not in report

    config = json.loads((run_dir / RUN_CONFIG_NAME).read_text(encoding="utf-8"))
    assert config["terminal_status"] == "degraded"
    assert config["configured_sources"] == ["public_market_data"]


RUN_CONFIG_NAME = "run_config.json"


@pytest.mark.parametrize("asset", [Asset.ETH, Asset.SOL])
async def test_pipeline_is_coin_agnostic(tmp_path, asset: Asset) -> None:
    """Two different single-asset runs prove the path has no per-coin branch."""
    service, request, _ = _run(tmp_path / asset.value, [asset])
    summary = await service.run(request)

    ledger = EvidenceLedger.model_validate_json(
        (Path(summary.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    )
    assert ledger.items
    assert {item.asset for item in ledger.items} == {asset}


async def test_dual_asset_run_keeps_evidence_for_both_assets(tmp_path) -> None:
    service, request, _ = _run(tmp_path, [Asset.BTC, Asset.ETH])
    summary = await service.run(request)

    ledger = EvidenceLedger.model_validate_json(
        (Path(summary.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    )
    assert {item.asset for item in ledger.items} == {Asset.BTC, Asset.ETH}


async def test_metric_values_survive_for_quantified_thresholds(tmp_path) -> None:
    """§16.4 needs the numeric value behind an Evidence ID, not just its prose."""
    pipeline = OrganizerCsvPipeline(analysis_date=ANALYSIS_DATE)
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(),
        pipeline=pipeline,
        stdout=io.StringIO(),
    )
    request = build_request(
        question=QUESTION,
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix="csv1",
        analysis_as_of=FROZEN_NOW,
    )
    await service.run(request)

    index = pipeline.last_metric_index
    assert index, "the metric index must be available to downstream reasoning"
    assert any(entry.metric_name == "return_14d" for entry in index.values())
    assert all(isinstance(entry.metric_value, float) for entry in index.values())


async def test_missing_csv_degrades_honestly_instead_of_crashing(tmp_path) -> None:
    empty_dir = tmp_path / "no_data"
    empty_dir.mkdir()
    service = ApplicationService(
        artifact_root=tmp_path / "artifacts",
        clock=FixedClock(),
        pipeline=OrganizerCsvPipeline(data_dir=empty_dir, analysis_date=ANALYSIS_DATE),
        stdout=io.StringIO(),
    )
    request = build_request(
        question=QUESTION,
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix="csv1",
        analysis_as_of=FROZEN_NOW,
    )

    summary = await service.run(request)
    run_dir = Path(summary.artifact_dir)

    # Still four artifacts, still schema-valid, and the gap is stated.
    assert sorted(p.name for p in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    assert ledger.items == []
    assert ledger.degradation_events
    assert summary.terminal_state in {TerminalState.degraded, TerminalState.failed}
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert "目前無法可靠判定" in report
