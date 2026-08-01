"""Tests for the Binance funding-rate (derivatives) adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from hoya_agent.adapters.derivatives import fetch_funding_rate
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.types import EvidenceDraft

UTC = timezone.utc
AS_OF = datetime(2026, 6, 3, tzinfo=UTC)
RECENT_MS = int((AS_OF - timedelta(hours=1)).timestamp() * 1000)
FUTURE_MS = int((AS_OF + timedelta(days=2)).timestamp() * 1000)


def _payload(rate: str, t: int = RECENT_MS) -> dict:
    return {"symbol": "BTCUSDT", "markPrice": "63000.0", "indexPrice": "62990.0",
            "lastFundingRate": rate, "time": t}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_positive_funding_rate_into_market_high_draft():
    r = fetch_funding_rate("BTC", analysis_as_of=AS_OF,
                           client=_client(lambda req: httpx.Response(200, json=_payload("0.0000569"))))
    assert isinstance(r, WorkerResult) and r.status == "completed"
    d = r.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.source_type == "market" and d.reliability == "high"
    assert d.independence_group == "binance.com"
    assert d.metric_name == "funding_rate"
    assert "多頭付費給空頭" in d.normalized_fact


def test_symbol_mapping_in_request():
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json=_payload("0.0"))

    fetch_funding_rate("ETH", analysis_as_of=AS_OF, client=_client(handler))
    assert "ETHUSDT" in captured["url"]


def test_snapshot_after_cutoff_is_degradation():
    r = fetch_funding_rate("BTC", analysis_as_of=AS_OF,
                           client=_client(lambda req: httpx.Response(200, json=_payload("0.01", FUTURE_MS))))
    assert r.drafts == [] and r.degradation


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_funding_rate("DOGE", analysis_as_of=AS_OF,
                           client=_client(lambda req: httpx.Response(200, json=_payload("0.0"))))


def test_http_error_is_degradation():
    r = fetch_funding_rate("BTC", analysis_as_of=AS_OF,
                           client=_client(lambda req: httpx.Response(500)))
    assert r.drafts == [] and r.degradation
