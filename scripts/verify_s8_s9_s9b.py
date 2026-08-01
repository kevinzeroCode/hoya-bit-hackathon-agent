"""Offline acceptance smoke for S8/S9/S9B (no pytest or network required)."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import Asset, EvidenceLedger, Reliability, RunMode, SourceType
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, OrganizerCsvPipeline
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES


class FixedClock:
    def now_utc(self) -> datetime:
        return datetime(2026, 5, 31, 6, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1000.0


class FakePlanner:
    async def run(self, *, request, deadline):
        assert request.assets == ("BTC", "ETH")
        assert request.run_id.startswith("run_")
        del deadline
        return object(), []


class EmptyResearchAgent:
    async def run(self, *, plan, request, deadline):
        assert request.assets == ("BTC", "ETH")
        del plan, deadline
        draft = SimpleNamespace(
            asset=Asset.BTC,
            source_type=SourceType.news,
            source_name="official_project_feed",
            source_url="https://example.test/news/1",
            published_at=datetime(2026, 5, 31, tzinfo=UTC),
            fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
            query_or_parameters="asset=BTC",
            content_reference="record-1",
            normalized_fact="A schema-valid research fact.",
            reliability=Reliability.high,
            independence_group="official-project-feed",
            is_cached=False,
            cache_time=None,
            is_stale=False,
        )
        return type("Outcome", (), {"drafts": [draft], "degradation_events": []})()


async def verify() -> None:
    with tempfile.TemporaryDirectory(prefix="hoya-s8-") as root:
        clock = FixedClock()
        pipeline = DeadlineAwarePipeline(
            clock=clock,
            market_pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
            planner=FakePlanner(),
            research_agent=EmptyResearchAgent(),
        )
        service = ApplicationService(
            artifact_root=Path(root),
            clock=clock,
            pipeline=pipeline,
            configured_sources=["organizer_csv"],
        )
        request = build_request(
            question="BTC 與 ETH 近期市場表現相比如何？",
            assets=[Asset.BTC, Asset.ETH],
            run_mode=RunMode.rehearsal,
            now=FixedClock().now_utc(),
            analysis_as_of=FixedClock().now_utc(),
            run_id_suffix="s899b",
        )
        summary = await service.run(request)
        run_dir = Path(summary.artifact_dir)
        names = {path.name for path in run_dir.iterdir()}
        assert names == set(ARTIFACT_NAMES), names
        ledger = EvidenceLedger.model_validate_json(
            (run_dir / "evidence.json").read_text(encoding="utf-8")
        )
        assert ledger.run_id == request.run_id
        assert {item.asset for item in ledger.items} >= {Asset.BTC, Asset.ETH}
        assert any(item.source_type is SourceType.news for item in ledger.items)
        report = (run_dir / "final_report.md").read_text(encoding="utf-8")
        assert "## 12. 跨幣比較" in report
        assert "Trust Scorecard" in report
        assert "Market Regime" in report
        # The actual comparison claim is rendered with its ID and both assets.
        assert "比較型 Claim `cl_002`" in report
        assert summary.insufficient_data is False
        execution_log = (run_dir / "execution_log.jsonl").read_text(encoding="utf-8")
        assert '"stage":"planner"' in execution_log
        assert '"stage":"research_agent"' in execution_log


if __name__ == "__main__":
    asyncio.run(verify())
    print("S8/S9/S9B offline acceptance smoke: PASS")

