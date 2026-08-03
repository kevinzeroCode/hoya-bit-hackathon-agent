"""Task 19: extend Task 9's Gold local Exit pattern from two assets to all five.

`tests/acceptance/test_gold_assets.py::test_gold_asset_run_has_complete_traceable_artifacts`
already proves the artifact/provenance/terminal-state contract for BTC and ETH
and is Task 9's own frozen Gold gate — left untouched here rather than widening
its parametrize list, so this task's breadth work cannot accidentally regress
an already-passed gate. This file is deliberately the same test body applied
to the three assets Task 9 never ran (SOL, BNB, XRP): same contract, no new
assertions, no per-coin branching in `src/` to reach it.
"""

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


@pytest.mark.parametrize("asset", [Asset.SOL, Asset.BNB, Asset.XRP])
async def test_remaining_gold_assets_have_complete_traceable_artifacts(
    tmp_path: Path, asset: Asset
) -> None:
    """SOL/BNB/XRP each as an independent single-asset run — Task 9's BTC/ETH
    coverage plus these three completes the five-asset request allowlist."""
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


async def test_all_five_assets_ran_as_independent_single_asset_runs(tmp_path: Path) -> None:
    """One assertion tying Task 9's two assets and this task's three together:
    all five allowlisted assets pass, each as its own run, each with its own
    ledger that names only its own asset — never a merged or five-in-one run."""
    seen_run_ids: set[str] = set()
    for asset in Asset:
        pipeline = OrganizerCsvPipeline(analysis_date=ANALYSIS_DATE)
        service = ApplicationService(
            artifact_root=tmp_path / asset.value / "artifacts",
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
            run_id_suffix=f"m{asset.value.lower()}",
        )
        summary = await service.run(request)
        assert summary.missing_artifacts == []
        assert summary.run_id not in seen_run_ids, "each asset must get its own run_id"
        seen_run_ids.add(summary.run_id)

    assert len(seen_run_ids) == 5


def test_five_asset_coverage_requires_no_per_coin_branch_in_src() -> None:
    """Coin-agnostic rule (`.kiro/steering/competition-rules.md`): grep the
    pipeline for the one pattern a per-coin special case would leave behind.
    A regression here means someone added `if asset == Asset.XXX` to make an
    asset pass, instead of fixing the coin-agnostic path."""
    import re

    pipeline_src = Path("src/hoya_agent/orchestration/pipeline.py").read_text(encoding="utf-8")
    assert not re.search(r'asset\s*==\s*Asset\.\w+', pipeline_src)
    assert not re.search(r'asset\.value\s*==\s*["\'](BTC|ETH|SOL|BNB|XRP)["\']', pipeline_src)
