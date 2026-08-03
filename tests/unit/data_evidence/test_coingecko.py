"""Contract tests for the optional CoinGecko secondary market adapter (Task 18)."""

from __future__ import annotations

from datetime import timezone

import httpx

from hoya_agent.adapters.coingecko import fetch_coingecko_price
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.drafts import PendingEvidence
from hoya_agent.evidence.policies import reliability_for

UTC = timezone.utc


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_parses_a_medium_reliability_market_draft():
    result = await fetch_coingecko_price(
        "BTC",
        client=_client(lambda r: httpx.Response(200, json={"bitcoin": {"usd": 65000.5}})),
    )
    assert isinstance(result, WorkerResult)
    assert result.status == "completed"
    assert len(result.drafts) == 1
    d = result.drafts[0]
    assert isinstance(d, PendingEvidence)
    assert d.asset == "BTC"
    assert d.source_type == "market"
    assert reliability_for(d.source_class) == "medium"  # aggregator, not first-hand exchange
    assert d.provider_id == "coingecko"
    assert d.metric is not None
    assert d.metric.metric_name == "coingecko_price_usd"
    assert d.metric.metric_value == 65000.5
    assert "65000.5" in d.normalized_fact
    assert d.published_at is not None
    assert d.fetched_at.tzinfo is not None


async def test_unsupported_asset_is_a_degradation_not_a_crash():
    result = await fetch_coingecko_price(
        "DOGE", client=_client(lambda r: httpx.Response(200, json={}))
    )
    assert result.status == "failed"
    assert result.drafts == []
    assert result.degradation


async def test_http_error_is_a_non_blocking_degradation():
    result = await fetch_coingecko_price("ETH", client=_client(lambda r: httpx.Response(500)))
    assert result.status == "failed"
    assert result.drafts == []
    assert "category=http_error" in result.degradation[0]


async def test_timeout_is_a_non_blocking_degradation():
    def _raise(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    result = await fetch_coingecko_price("SOL", client=_client(_raise))
    assert result.status == "failed"
    assert "category=timeout" in result.degradation[0]


async def test_malformed_payload_is_a_non_blocking_degradation():
    result = await fetch_coingecko_price(
        "BNB", client=_client(lambda r: httpx.Response(200, json={"binancecoin": {}}))
    )
    assert result.status == "failed"
    assert result.drafts == []
    assert result.degradation


async def test_empty_payload_is_a_non_blocking_degradation():
    result = await fetch_coingecko_price("XRP", client=_client(lambda r: httpx.Response(200, json={})))
    assert result.status == "failed"
    assert result.drafts == []
    assert result.degradation
