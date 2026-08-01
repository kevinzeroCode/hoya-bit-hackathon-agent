"""Tests for the RSS news adapter (first-party outlet feed)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from adapters.rss import fetch_rss_news
from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft

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


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _feed(asset: str, client) -> WorkerResult:
    return fetch_rss_news(
        asset, analysis_as_of=AS_OF, client=client,
        feed_url="https://www.coindesk.com/rss", source_name="CoinDesk", publisher_domain="coindesk.com",
    )


def test_parses_btc_items_into_medium_news_drafts():
    result = _feed("BTC", _client(lambda r: httpx.Response(200, text=RSS)))
    assert isinstance(result, WorkerResult)
    titles = [d.normalized_fact for d in result.drafts]
    assert "Bitcoin ETF sees record inflows" in titles
    assert "Ethereum upgrade goes live" not in titles       # other coin filtered
    assert "Bitcoin rally continues next week" not in titles  # future filtered
    d = result.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.source_type == "news"
    assert d.reliability == "medium"  # first-party outlet feed w/ URL + timestamp
    assert d.independence_group == "coindesk.com"


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        _feed("DOGE", _client(lambda r: httpx.Response(200, text=RSS)))


def test_http_error_is_degradation():
    result = _feed("BTC", _client(lambda r: httpx.Response(500)))
    assert result.drafts == []
    assert result.degradation
