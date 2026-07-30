"""Tests for the Alternative.me Fear & Greed adapter (whole-market sentiment)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from adapters.alternative_me import fetch_fear_greed
from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft

UTC = timezone.utc
AS_OF = datetime(2026, 5, 31, tzinfo=UTC)
RECENT_TS = int((AS_OF - timedelta(days=1)).timestamp())


def _payload(ts: int = RECENT_TS, value: str = "28", cls: str = "Fear") -> dict:
    return {
        "name": "Fear and Greed Index",
        "data": [{"value": value, "value_classification": cls, "timestamp": str(ts)}],
        "metadata": {"error": None},
    }


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_whole_market_social_low_draft():
    result = fetch_fear_greed(analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=_payload())))
    assert isinstance(result, WorkerResult)
    assert len(result.drafts) == 1
    d = result.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.asset is None  # whole-market, NOT a coin-specific signal
    assert d.source_type == "social"
    assert d.reliability == "low"
    assert d.independence_group == "alternative.me"
    assert "28" in d.normalized_fact
    assert "非單一幣種" in d.normalized_fact  # disclosure it isn't coin-specific
    assert d.published_at is not None
    assert d.fetched_at.tzinfo is not None


def test_future_data_excluded():
    fut = int((AS_OF + timedelta(days=5)).timestamp())
    result = fetch_fear_greed(
        analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=_payload(ts=fut)))
    )
    assert result.drafts == []
    assert result.degradation


def test_http_error_is_degradation():
    result = fetch_fear_greed(analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500)))
    assert result.drafts == []
    assert result.degradation


def test_malformed_is_degradation():
    result = fetch_fear_greed(
        analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json={"data": [{}]}))
    )
    assert result.drafts == []
    assert result.degradation
