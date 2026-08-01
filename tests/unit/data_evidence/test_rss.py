"""Tests for the RSS news adapter (first-party outlet feed)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from hoya_agent.adapters.rss import fetch_rss_news
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.drafts import PendingEvidence
from hoya_agent.evidence.policies import reliability_for

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
 <item><title>Bitcoin ETF sees record inflows</title>
   <link>https://www.coindesk.com/a</link>
   <pubDate>Sat, 30 May 2026 12:00:00 GMT</pubDate></item>
 <item><title>Ethereum upgrade goes live</title>
   <link>https://www.coindesk.com/b</link>
   <pubDate>Fri, 29 May 2026 12:00:00 GMT</pubDate></item>
 <item><title>Bitcoin rally continues next week</title>
   <link>https://www.coindesk.com/c</link>
   <pubDate>Fri, 05 Jun 2026 12:00:00 GMT</pubDate></item>
</channel></rss>"""


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _feed(asset: str, client) -> WorkerResult:
    return await fetch_rss_news(
        asset, analysis_as_of=AS_OF, client=client,
        feed_url="https://www.coindesk.com/rss", source_name="CoinDesk", publisher_domain="coindesk.com",
    )


async def test_parses_btc_items_into_medium_news_drafts():
    result = await _feed("BTC", _client(lambda r: httpx.Response(200, text=RSS)))
    assert isinstance(result, WorkerResult)
    titles = [d.normalized_fact for d in result.drafts]
    assert "Bitcoin ETF sees record inflows" in titles
    assert "Ethereum upgrade goes live" not in titles       # other coin filtered
    assert "Bitcoin rally continues next week" not in titles  # future filtered
    d = result.drafts[0]
    assert isinstance(d, PendingEvidence)
    assert d.source_type == "news"
    assert reliability_for(d.source_class) == "medium"  # first-party outlet feed w/ URL + timestamp
    assert d.original_publisher == "coindesk.com"


async def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        await _feed("DOGE", _client(lambda r: httpx.Response(200, text=RSS)))


async def test_http_error_is_degradation():
    result = await _feed("BTC", _client(lambda r: httpx.Response(500)))
    assert result.drafts == []
    assert result.degradation
