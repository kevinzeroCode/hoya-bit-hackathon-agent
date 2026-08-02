"""Opt-in end-to-end Silver gate through one ApplicationService run."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings
from hoya_agent.adapters.port_adapters import (
    BinanceMarketAdapter,
    CsvMarketAdapter,
    RssResearchAdapter,
)
from hoya_agent.application import ApplicationService, build_request
from hoya_agent.clock import build_run_context
from hoya_agent.composition import MappingArbiter
from hoya_agent.data.market_series import merge_with_cutover
from hoya_agent.models import (
    Asset,
    DataMode,
    ResearchPlan,
    ResearchStep,
    RunMode,
    SourceStatus,
    SourceType,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, OrganizerCsvPipeline
from hoya_agent.ports import StaticToolRegistry
from hoya_agent.reasoning.arbiter import Arbiter
from hoya_agent.reasoning.research_agent import ResearchAgent
from hoya_agent.reasoning.schemas import ArbiterGeneration, DraftBatch

pytestmark = pytest.mark.live

if os.getenv("RUN_LIVE_TESTS") != "1":
    pytest.skip("set RUN_LIVE_TESTS=1 to run live Silver checks", allow_module_level=True)


class LiveClock:
    """Freeze the official wall-clock cutoff while keeping real deadline time."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now_utc(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return time.monotonic()


class BaselinePlanner:
    async def run(self, *, request, deadline):
        del deadline
        return (
            ResearchPlan(
                assets=[Asset(asset) for asset in request.assets],
                question_summary=request.question,
                lookback_days=30,
                required_evidence_types=[SourceType.news],
                planned_steps=[
                    ResearchStep(
                        step_id="baseline_01",
                        tool_operation="baseline_news",
                        rationale="Silver designated baseline research source",
                    )
                ],
            ),
            [],
        )


async def test_single_live_run_uses_both_baselines_bedrock_and_four_artifacts(
    tmp_path,
) -> None:
    model_id = os.environ.get("BEDROCK_PRIMARY_MODEL_ID", "").strip()
    if not model_id:
        pytest.fail("BEDROCK_PRIMARY_MODEL_ID is required for the Silver live gate")
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-west-2"
    )
    now = datetime.now(UTC).replace(microsecond=0)
    clock = LiveClock(now)
    request = build_request(
        question="BTC 過去一個月的市場證據與主要新聞透露什麼風險？",
        assets=[Asset.BTC],
        run_mode=RunMode.official,
        now=now,
        run_id_suffix="silver",
        deadline_seconds=300,
    )
    source_context = build_run_context(request, clock)

    with httpx.Client(
        headers={"User-Agent": "hoya-market-agent-silver-gate/1.0"},
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
    ) as http_client:
        organizer = await CsvMarketAdapter().fetch_daily_bars(
            asset=Asset.BTC,
            start=date(2021, 1, 1),
            end=now.date(),
            context=source_context,
        )
        live_market = await BinanceMarketAdapter(http_client).fetch_daily_bars(
            asset=Asset.BTC,
            start=(now - timedelta(days=1000)).date(),
            end=now.date(),
            context=source_context,
        )
        assert organizer.status is SourceStatus.ok and organizer.data
        assert live_market.status is SourceStatus.ok and live_market.data
        merged_bars, _ = merge_with_cutover(organizer.data, live_market.data)
        assert merged_bars and merged_bars[-1].date >= (now - timedelta(days=2)).date()

        rss = RssResearchAdapter(
            feed_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
            source_name="CoinDesk",
            publisher_domain="coindesk.com",
            client=http_client,
        )

        async def baseline_news(**params):
            result = await rss.fetch(
                operation="baseline_news",
                context=source_context,
                lookback_days=params.get("lookback_days", 30),
            )
            if result.status is not SourceStatus.ok or not result.data:
                raise RuntimeError(result.error_category or "baseline RSS returned no records")
            return result.data

        registry = StaticToolRegistry({"baseline_news": baseline_news})
        llm = BedrockLLMClient(
            BedrockSettings(
                region=region,
                primary_model_id=model_id,
                fallback_model_id=os.environ.get("BEDROCK_FALLBACK_MODEL_ID") or None,
                call_timeout_seconds=45.0,
            )
        )
        pipeline = DeadlineAwarePipeline(
            clock=clock,
            market_pipeline=OrganizerCsvPipeline(
                load_bars=lambda asset: merged_bars,
                analysis_date=now.date(),
                market_source_name="binance_spot",
                market_independence_group="binance",
                market_source_url="https://api.binance.com/api/v3/klines",
            ),
            planner=BaselinePlanner(),
            research_agent=ResearchAgent(
                llm=llm,
                draft_schema=DraftBatch,
                tool_registry=registry,
            ),
            arbiter=MappingArbiter(
                inner=Arbiter(llm=llm, result_schema=ArbiterGeneration)
            ),
        )
        summary = await ApplicationService(
            artifact_root=tmp_path,
            clock=clock,
            pipeline=pipeline,
            configured_sources=["organizer_csv", "binance_klines", "coindesk_rss"],
        ).run(request)

    assert summary.effective_data_mode is DataMode.live
    assert summary.insufficient_data is False
    assert summary.missing_artifacts == []
    assert {Path(value).name for value in summary.artifact_paths.values()} == {
        "run_config.json",
        "execution_log.jsonl",
        "evidence.json",
        "final_report.md",
        "final_report.html",
    }

    evidence_path = tmp_path / summary.run_id / "evidence.json"
    ledger = json.loads(evidence_path.read_text(encoding="utf-8"))
    source_types = {item["source_type"] for item in ledger["items"]}
    assert {"market", "news"}.issubset(source_types)
    assert all(
        item["evidence_id"] in summary.report_markdown
        for item in ledger["items"]
        if item["source_type"] == "news"
    )

    events = llm.drain_events()
    successful_operations = {event.operation for event in events if event.status == "ok"}
    assert {"research_extraction", "arbiter"}.issubset(successful_operations)

