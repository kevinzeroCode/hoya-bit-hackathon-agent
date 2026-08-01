"""Opt-in live gate for the designated baseline source paths."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from tests.fakes import FixedClock

from hoya_agent.adapters.port_adapters import (
    BinanceMarketAdapter,
    CsvMarketAdapter,
    RssResearchAdapter,
)
from hoya_agent.application import build_request
from hoya_agent.clock import build_run_context
from hoya_agent.models import Asset, RunMode, SourceStatus

pytestmark = pytest.mark.live

if os.getenv("RUN_LIVE_TESTS") != "1":
    pytest.skip("set RUN_LIVE_TESTS=1 to run live Silver checks", allow_module_level=True)


async def test_organizer_binance_and_baseline_research_are_live() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    clock = FixedClock(now, monotonic_value=100.0)
    request = build_request(
        question="BTC 最近市場狀態與重要事件？",
        assets=[Asset.BTC],
        run_mode=RunMode.official,
        now=now,
        run_id_suffix="live",
    )
    context = build_run_context(request, clock)

    with httpx.Client(
        headers={"User-Agent": "hoya-market-agent-silver-gate/1.0"},
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
    ) as client:
        organizer = await CsvMarketAdapter().fetch_daily_bars(
            asset=Asset.BTC,
            start=datetime(2026, 5, 1, tzinfo=UTC).date(),
            end=datetime(2026, 5, 31, tzinfo=UTC).date(),
            context=context,
        )
        live_market = await BinanceMarketAdapter(client).fetch_daily_bars(
            asset=Asset.BTC,
            start=(now - timedelta(days=14)).date(),
            end=now.date(),
            context=context,
        )
        research = await RssResearchAdapter(
            feed_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
            source_name="CoinDesk",
            publisher_domain="coindesk.com",
            client=client,
        ).fetch(
            operation="baseline_news",
            context=context,
            lookback_days=30,
        )

    assert organizer.status is SourceStatus.ok
    assert organizer.data
    assert live_market.status is SourceStatus.ok, live_market.error_category
    assert live_market.data
    assert research.status is SourceStatus.ok, research.error_category
    assert research.data
    assert all(record.fetched_at <= now + timedelta(minutes=2) for record in research.data)
