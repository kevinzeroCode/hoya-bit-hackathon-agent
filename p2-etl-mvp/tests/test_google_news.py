"""Tests for the Google News search adapter (coin-agnostic news coverage)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from adapters.google_news import fetch_google_news
from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)
RECENT = (AS_OF - timedelta(days=2)).strftime("%a, %d %b %Y %H:%M:%S +0000")
OLD = (AS_OF - timedelta(days=90)).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _item(title: str, when: str, src_name: str, src_url: str) -> str:
    return (
        "<item>"
        f"<title>{title}</title>"
        "<link>https://news.google.com/rss/articles/abc</link>"
        f"<pubDate>{when}</pubDate>"
        f'<source url="{src_url}">{src_name}</source>'
        "</item>"
    )


FEED = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    + _item("Solana ETF sees inflows", RECENT, "CoinDesk", "https://www.coindesk.com")
    + _item("Solana network upgrade ships", RECENT, "The Block", "https://www.theblock.co")
    + _item("Unrelated stock market update", RECENT, "Reuters", "https://www.reuters.com")  # no SOL -> filtered
    + _item("Solana rallied last quarter", OLD, "Decrypt", "https://decrypt.co")            # out of window
    + "</channel></rss>"
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_covers_asset_with_independence_from_original_publisher():
    r = fetch_google_news("SOL", analysis_as_of=AS_OF,
                          client=_client(lambda req: httpx.Response(200, text=FEED)), lookback_days=14)
    assert isinstance(r, WorkerResult) and r.status == "completed"
    assert len(r.drafts) == 2  # 2 on-topic in-window; unrelated + old filtered
    d = r.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.source_type == "news" and d.reliability == "low"     # aggregator
    assert d.independence_group == "coindesk.com"                 # ORIGINAL publisher, not google
    assert d.asset == "SOL"


def test_query_targets_the_coin():
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, text=FEED)

    fetch_google_news("BNB", analysis_as_of=AS_OF, client=_client(handler))
    assert "binance" in captured["url"].lower()  # query is BNB-targeted


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_google_news("DOGE", analysis_as_of=AS_OF,
                          client=_client(lambda req: httpx.Response(200, text=FEED)))


def test_http_error_is_degradation():
    r = fetch_google_news("BTC", analysis_as_of=AS_OF,
                          client=_client(lambda req: httpx.Response(500)))
    assert r.drafts == [] and r.degradation
