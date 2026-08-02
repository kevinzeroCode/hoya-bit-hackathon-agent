"""S10 Gold local Exit — two *different* assets, two *independent* single-asset runs.

What this gate proves is narrow and deliberate: the pipeline is coin-agnostic.
It is **not** a dual-asset comparison — that capability has its own gate
(Requirement 17, `tests/integration/test_dual_asset_run.py`) and neither may
stand in for the other. So each asset here goes through its own
`ApplicationService.run` with its own run id, its own artifact directory and its
own ledger.

The path is the offline organizer-CSV one, so this file needs no network, no
Bedrock and no AWS credentials, and is safe under `-m "not live"` in CI.
"""

from __future__ import annotations

import io
import socket
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import Asset, EvidenceLedger, Reliability, RunMode, SourceType, TerminalState
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES, EVIDENCE_LEDGER, FINAL_REPORT

pytestmark = pytest.mark.acceptance

# The organizer dataset ends 2026-05-31 UTC; the local gate replays that cutoff.
ANALYSIS_DATE = date(2026, 5, 31)
FROZEN_NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)
QUESTION = "這個資產近期的市場行為可以由哪些因素解釋？"

#: The two assets this gate requires. Additional assets are optional and
#: non-blocking; the five-coin validation matrix is explicitly *not* required.
GOLD_ASSETS = (Asset.BTC, Asset.ETH)

#: Requests must keep accepting all five supported assets even though only two
#: are validated end-to-end.
REQUEST_ALLOWLIST = (Asset.BTC, Asset.ETH, Asset.SOL, Asset.BNB, Asset.XRP)


class _FixedClock:
    def now_utc(self) -> datetime:
        return FROZEN_NOW

    def monotonic(self) -> float:
        return 1000.0


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch) -> None:
    """No network and no credentials — a local gate must stay local."""

    def no_network(*args, **kwargs):  # noqa: ANN002, ANN003 - guard signature is irrelevant
        raise AssertionError("the Gold local gate must not reach the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "BEDROCK_PRIMARY_MODEL_ID"):
        monkeypatch.delenv(name, raising=False)


async def run_single_asset(
    artifact_root: Path,
    asset: Asset,
    *,
    suffix: str,
    data_dir: Path | None = None,
):
    """One independent single-asset run through the public entry point."""
    pipeline = (
        OrganizerCsvPipeline(analysis_date=ANALYSIS_DATE)
        if data_dir is None
        else OrganizerCsvPipeline(data_dir=data_dir, analysis_date=ANALYSIS_DATE)
    )
    service = ApplicationService(
        artifact_root=artifact_root,
        clock=_FixedClock(),
        pipeline=pipeline,
        configured_sources=["public_market_data"],
        stdout=io.StringIO(),
    )
    request = build_request(
        question=QUESTION,
        assets=[asset],
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix=suffix,
        analysis_as_of=FROZEN_NOW,
    )
    return await service.run(request)


def load_ledger(summary) -> EvidenceLedger:
    return EvidenceLedger.model_validate_json(
        (Path(summary.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("asset", GOLD_ASSETS)
async def test_each_gold_asset_completes_its_own_single_asset_run(tmp_path, asset: Asset) -> None:
    summary = await run_single_asset(tmp_path / asset.value, asset, suffix=f"g{asset.value.lower()}")
    run_dir = Path(summary.artifact_dir)

    # Four fixed artifacts, nothing else in the run directory.
    assert sorted(path.name for path in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    assert summary.missing_artifacts == []

    # Evidence exists, is this asset's, and carries deterministic provenance.
    ledger = load_ledger(summary)
    assert ledger.items, "a Gold asset run must produce Evidence"
    assert {item.asset for item in ledger.items} == {asset}
    assert all(item.source_type is SourceType.market for item in ledger.items)
    assert all(item.reliability is Reliability.high for item in ledger.items)
    assert all(item.independence_group == "organizer-public-market-data" for item in ledger.items)
    assert all(item.content_hash for item in ledger.items)

    # Every Evidence ID and normalized fact is traceable in the rendered report.
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    for item in ledger.items:
        assert item.evidence_id in report
        assert item.normalized_fact in report


async def test_the_two_gold_runs_stay_independent(tmp_path) -> None:
    """Separate run ids, separate directories, no cross-asset leakage.

    A dual-asset run would share one run id and one ledger. This gate requires
    the opposite, so assert it rather than trusting the call site.
    """
    first, second = GOLD_ASSETS
    a = await run_single_asset(tmp_path / "a", first, suffix="gold1")
    b = await run_single_asset(tmp_path / "b", second, suffix="gold2")

    assert a.run_id != b.run_id
    assert Path(a.artifact_dir) != Path(b.artifact_dir)

    ledger_a, ledger_b = load_ledger(a), load_ledger(b)
    assert {item.asset for item in ledger_a.items} == {first}
    assert {item.asset for item in ledger_b.items} == {second}
    assert ledger_a.run_id == a.run_id
    assert ledger_b.run_id == b.run_id

    # Neither report may name the other asset: no comparison was requested and
    # none may be implied.
    report_a = (Path(a.artifact_dir) / FINAL_REPORT).read_text(encoding="utf-8")
    assert second.value not in report_a
    assert "\n## 12. " not in report_a, "the 跨幣比較 section belongs to dual-asset runs only"


async def test_the_report_shape_does_not_branch_per_coin(tmp_path) -> None:
    """Same 11 sections and the same prohibited-language guarantee for both."""
    shapes = set()
    for index, asset in enumerate(GOLD_ASSETS):
        summary = await run_single_asset(tmp_path / f"shape{index}", asset, suffix=f"shp{index}")
        report = (Path(summary.artifact_dir) / FINAL_REPORT).read_text(encoding="utf-8")
        shapes.add(report.count("\n## "))
        for term in ("買入", "賣出", "加倉", "減倉", "做多", "做空", "資產配置"):
            assert term not in report

    assert shapes == {11}, "both assets must render the same deterministic 11-section report"


@pytest.mark.parametrize("asset", REQUEST_ALLOWLIST)
def test_all_five_supported_assets_stay_requestable(asset: Asset) -> None:
    """The request allowlist keeps all five; only validation is limited to two."""
    request = build_request(
        question=QUESTION,
        assets=[asset],
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix="allow",
        analysis_as_of=FROZEN_NOW,
    )
    assert list(request.assets) == [asset]


def test_an_unsupported_asset_is_rejected_at_the_request_boundary() -> None:
    with pytest.raises(ValueError):
        build_request(
            question=QUESTION,
            assets=["DOGE"],  # type: ignore[list-item]
            run_mode=RunMode.rehearsal,
            now=FROZEN_NOW,
            run_id_suffix="allow",
            analysis_as_of=FROZEN_NOW,
        )


async def test_a_missing_baseline_source_degrades_honestly(tmp_path) -> None:
    """Baseline-source degradation: disclose the gap, never invent a fallback.

    There is no second live market provider in the MVP, so the honest outcome is
    a degraded run with an empty ledger and four artifacts — not a silent switch
    to an unimplemented provider.
    """
    empty = tmp_path / "no_data"
    empty.mkdir()
    summary = await run_single_asset(tmp_path / "degraded", Asset.BTC, suffix="deg1", data_dir=empty)
    run_dir = Path(summary.artifact_dir)

    assert sorted(path.name for path in run_dir.iterdir()) == sorted(ARTIFACT_NAMES)
    assert summary.terminal_state in {TerminalState.degraded, TerminalState.failed}
    assert summary.insufficient_data is True
    assert summary.confidence is Reliability.low

    ledger = load_ledger(summary)
    assert ledger.items == []
    assert ledger.degradation_events, "an empty ledger must still say why"

    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert "目前無法可靠判定" in report
    for claim_of_a_fallback in ("CoinGecko", "改用備援來源", "已切換至"):
        assert claim_of_a_fallback not in report
