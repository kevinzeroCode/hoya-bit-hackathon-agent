"""Tests for the Reddit r/CryptoCurrency adapter (community/social via Atom feed)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from adapters.reddit import fetch_reddit_posts
from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)
RECENT = (AS_OF - timedelta(days=1)).isoformat()
FUTURE = (AS_OF + timedelta(days=3)).isoformat()


def _entry(title: str, when: str = RECENT) -> str:
    return (
        "<entry>"
        "<author><name>/u/tester</name></author>"
        f"<title>{title}</title>"
        '<link href="https://www.reddit.com/r/CryptoCurrency/comments/x/"/>'
        f"<updated>{when}</updated>"
        "</entry>"
    )


FEED = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
    + _entry("Bitcoin discussion megathread: is BTC bottoming?")
    + _entry("Ethereum staking rewards thread")   # not BTC -> filtered
    + _entry("General weekend chat")               # no asset mention -> filtered
    + _entry("Bitcoin to the moon soon", FUTURE)   # future -> filtered
    + "</feed>"
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_relevant_posts_into_social_low_drafts():
    result = fetch_reddit_posts(
        "BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, text=FEED))
    )
    assert isinstance(result, WorkerResult)
    titles = [d.normalized_fact for d in result.drafts]
    assert "Bitcoin discussion megathread: is BTC bottoming?" in titles
    assert len(result.drafts) == 1  # only the relevant, in-window BTC post
    d = result.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.source_type == "social"
    assert d.reliability == "low"
    assert d.independence_group == "reddit.com"
    assert d.asset == "BTC"


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_reddit_posts(
            "DOGE", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, text=FEED))
        )


def test_http_error_is_degradation():
    result = fetch_reddit_posts(
        "BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500))
    )
    assert result.drafts == []
    assert result.degradation


def test_malformed_feed_is_degradation():
    result = fetch_reddit_posts(
        "BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, text="not xml"))
    )
    assert result.drafts == []
    assert result.degradation
