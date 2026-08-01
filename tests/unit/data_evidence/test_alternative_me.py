"""Tests for the Alternative.me Fear & Greed adapter (whole-market sentiment)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from hoya_agent.adapters.alternative_me import fetch_fear_greed
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.drafts import PendingEvidence
from hoya_agent.evidence.policies import reliability_for

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)
RECENT_TS = int((AS_OF - timedelta(days=1)).timestamp())


def _payload(ts: int = RECENT_TS, value: str = "28", cls: str = "Fear") -> dict:
    return {
        "name": "Fear and Greed Index",
        "data": [{"value": value, "value_classification": cls, "timestamp": str(ts)}],
        "metadata": {"error": None},
    }


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_parses_whole_market_social_low_draft():
    result = await fetch_fear_greed(
        analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=_payload()))
    )
    assert isinstance(result, WorkerResult)
    assert len(result.drafts) == 1
    d = result.drafts[0]
    assert isinstance(d, PendingEvidence)
    assert d.asset is None  # whole-market, NOT a coin-specific signal
    assert d.source_type == "social"
    assert reliability_for(d.source_class) == "low"
    # Whole-market provider, so the group comes from the configured provider id.
    assert d.provider_id == "alternative.me"
    assert "28" in d.normalized_fact
    assert "非單一幣種" in d.normalized_fact  # disclosure it isn't coin-specific
    assert d.published_at is not None
    assert d.fetched_at.tzinfo is not None


async def test_future_data_excluded():
    fut = int((AS_OF + timedelta(days=5)).timestamp())
    result = await fetch_fear_greed(
        analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=_payload(ts=fut)))
    )
    assert result.drafts == []
    assert result.degradation


async def test_http_error_is_degradation():
    result = await fetch_fear_greed(analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500)))
    assert result.drafts == []
    assert result.degradation


async def test_malformed_is_degradation():
    result = await fetch_fear_greed(
        analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json={"data": [{}]}))
    )
    assert result.drafts == []
    assert result.degradation
