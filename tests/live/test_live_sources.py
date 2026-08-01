"""Live research and market sources: provider-schema drift detection.

The failure this catches is the quiet one — a provider renames a field, the adapter
parses nothing, and the run reports a source gap that looks like ordinary bad luck.
Every assertion here is about *shape*, never about a particular price or headline.

Manual only:

    $env:RUN_LIVE_TESTS = "1"
    python -m pytest tests/live -m live -vv -s
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
import pytest

from hoya_agent.adapters.binance import fetch_binance_daily
from hoya_agent.adapters.port_adapters import (
    FearGreedResearchAdapter,
    OfficialAnnouncementsResearchAdapter,
    RssResearchAdapter,
)
from hoya_agent.application import DEFAULT_NEWS_FEEDS
from hoya_agent.models import Asset, SourceStatus, SourceType

pytestmark = pytest.mark.live

NOW = datetime.now(UTC)
CRYPTOPANIC_TOKEN = os.environ.get("CRYPTOPANIC_API_TOKEN")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": "hoya-market-agent/0.1 (live rehearsal)"},
        follow_redirects=True,
        timeout=30.0,
    )


@pytest.mark.parametrize("asset", [Asset.BTC, Asset.ETH, Asset.SOL, Asset.BNB, Asset.XRP])
async def test_binance_daily_bars_keep_their_shape_for_every_asset(asset: Asset) -> None:
    """Coin-agnostic by symbol: one code path, five assets."""
    async with _client() as client:
        bars, degradation = await fetch_binance_daily(
            asset.value, analysis_as_of=NOW, client=client, limit=30
        )

    assert bars, f"a live baseline market source returning nothing is drift: {degradation}"
    for bar in bars:
        assert bar.date <= NOW.date()
        assert bar.high >= bar.low
        assert bar.close > 0
        assert bar.volume >= 0
    # Completed daily candles only, and strictly ordered.
    assert [b.date for b in bars] == sorted(b.date for b in bars)


async def test_baseline_research_feed_still_parses() -> None:
    """The designated baseline research source (first-party outlet RSS)."""
    feed = DEFAULT_NEWS_FEEDS[0]
    adapter = RssResearchAdapter(
        feed_url=feed.feed_url,
        source_name=feed.source_name,
        publisher_domain=feed.publisher_domain,
        client=_client(),
    )

    result = await adapter.fetch(
        operation="fetch_rss_news", assets=[Asset.BTC], analysis_as_of=NOW
    )

    assert result.status in (SourceStatus.ok, SourceStatus.empty), result.error_category
    if result.status is SourceStatus.empty:
        pytest.skip("feed parsed but no BTC item inside the lookback window")
    for record in result.data or []:
        assert record.source_type is SourceType.news
        assert record.published_at is not None or record.fetched_at is not None
        assert record.metadata["original_publisher"] == feed.publisher_domain


async def test_fear_greed_is_whole_market_and_never_per_coin() -> None:
    adapter = FearGreedResearchAdapter(client=_client())

    result = await adapter.fetch(operation="fetch_fear_greed", analysis_as_of=NOW)

    assert result.status in (SourceStatus.ok, SourceStatus.empty), result.error_category
    for record in result.data or []:
        assert record.asset is None, "Fear & Greed must never be attributed to one coin"


async def test_official_feeds_are_best_effort_not_blocking() -> None:
    """A missing or moved official feed is a disclosed gap, never a hard failure."""
    adapter = OfficialAnnouncementsResearchAdapter(client=_client())

    result = await adapter.fetch(
        operation="fetch_official_announcements",
        assets=[Asset.BTC, Asset.ETH],
        analysis_as_of=NOW,
    )

    assert result.status in (
        SourceStatus.ok,
        SourceStatus.empty,
        SourceStatus.http_error,
        SourceStatus.timeout,
    )
    for record in result.data or []:
        assert record.source_type is SourceType.official


@pytest.mark.skipif(not CRYPTOPANIC_TOKEN, reason="CRYPTOPANIC_API_TOKEN is not configured")
async def test_cryptopanic_records_carry_original_publisher_provenance() -> None:
    from hoya_agent.adapters.port_adapters import CryptoPanicResearchAdapter

    adapter = CryptoPanicResearchAdapter(api_token=CRYPTOPANIC_TOKEN, client=_client())

    result = await adapter.fetch(
        operation="fetch_cryptopanic_news", assets=[Asset.BTC], analysis_as_of=NOW
    )

    assert result.status in (SourceStatus.ok, SourceStatus.empty), result.error_category
    assert CRYPTOPANIC_TOKEN not in (result.query_or_parameters or "")
    for record in result.data or []:
        # Aggregator records stay `low`; the group belongs to the original publisher.
        assert record.metadata["original_page_fetched"] is False
