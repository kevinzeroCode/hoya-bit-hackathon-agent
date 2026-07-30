"""Tests for the Reddit r/CryptoCurrency adapter (community/social source)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from adapters.reddit import fetch_reddit_posts
from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)
RECENT = int((AS_OF - timedelta(days=1)).timestamp())
FUTURE = int((AS_OF + timedelta(days=3)).timestamp())


def _post(title: str, created: int = RECENT) -> dict:
    return {"data": {"title": title, "created_utc": created, "permalink": "/r/CryptoCurrency/1/"}}


PAYLOAD = {"data": {"children": [
    _post("Bitcoin discussion megathread — is BTC bottoming?"),
    _post("Ethereum staking rewards thread"),          # not BTC -> filtered
    _post("General weekend chat"),                     # no asset mention -> filtered
    _post("Bitcoin to the moon soon", created=FUTURE),  # future -> filtered
]}}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_relevant_posts_into_social_low_drafts():
    result = fetch_reddit_posts("BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=PAYLOAD)))
    assert isinstance(result, WorkerResult)
    titles = [d.normalized_fact for d in result.drafts]
    assert "Bitcoin discussion megathread — is BTC bottoming?" in titles
    assert len(result.drafts) == 1  # only the relevant, in-window BTC post
    d = result.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.source_type == "social"
    assert d.reliability == "low"
    assert d.independence_group == "reddit.com"
    assert d.asset == "BTC"


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_reddit_posts("DOGE", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=PAYLOAD)))


def test_http_error_is_degradation():
    result = fetch_reddit_posts("BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500)))
    assert result.drafts == []
    assert result.degradation
