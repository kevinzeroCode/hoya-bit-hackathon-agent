"""Tests for the CoinGecko aggregated-snapshot adapter (2nd market source)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from adapters.coingecko import fetch_coingecko_snapshot
from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)
PAYLOAD = {"bitcoin": {"usd": 73674.4, "usd_24h_change": -1.23, "usd_24h_vol": 1.2e10}}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_medium_market_snapshot():
    result = fetch_coingecko_snapshot("BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=PAYLOAD)))
    assert isinstance(result, WorkerResult)
    assert len(result.drafts) == 1
    d = result.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.asset == "BTC"
    assert d.source_type == "market"
    assert d.reliability == "medium"  # aggregator snapshot < first-hand exchange (high)
    assert d.independence_group == "coingecko.com"
    assert d.fetched_at.tzinfo is not None


def test_id_mapping_in_request():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"ethereum": {"usd": 2000.0}})

    fetch_coingecko_snapshot("ETH", analysis_as_of=AS_OF, client=_client(handler))
    assert "ethereum" in captured["url"]


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_coingecko_snapshot("DOGE", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=PAYLOAD)))


def test_http_error_is_degradation():
    result = fetch_coingecko_snapshot("BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500)))
    assert result.drafts == []
    assert result.degradation
