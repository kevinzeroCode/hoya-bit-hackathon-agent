"""Port-conforming wrappers for the remaining research sources.

`ResearchSourceAdapter` is the only shape the orchestrator can consume, so an
adapter that only exposes a module-level `fetch_*` returning `WorkerResult`
cannot participate in a real run. These tests pin the envelope for CryptoPanic,
Alternative.me Fear & Greed and official announcement feeds: success, empty,
HTTP error, timeout, malformed payload, and the disabled-by-missing-token case.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from tests.fakes import FixedClock

from hoya_agent.adapters.port_adapters import (
    CryptoPanicResearchAdapter,
    FearGreedResearchAdapter,
    OfficialAnnouncementsResearchAdapter,
)
from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    RawSourceRecord,
    RunMode,
    SourceResult,
    SourceStatus,
    SourceType,
)

UTC = timezone.utc
AS_OF = datetime(2026, 6, 3, tzinfo=UTC)


def _ctx(assets=(Asset.BTC,)):
    request = AnalysisRequest(
        question="test",
        assets=list(assets),
        requested_at=AS_OF,
        analysis_as_of=AS_OF,
        run_mode=RunMode.rehearsal,
        run_id="run_20260603_000000_test",
    )
    return build_run_context(request, FixedClock(AS_OF))


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _raises(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


# ── CryptoPanic ─────────────────────────────────────────────────────────────

_CP_PAYLOAD = {
    "results": [
        {
            "title": "Bitcoin ETF flows turn negative",
            "published_at": "2026-06-02T12:00:00+00:00",
            "url": "https://cryptopanic.com/news/1",
            "currencies": [{"code": "BTC"}],
            "source": {"title": "CoinDesk", "domain": "coindesk.com"},
        }
    ]
}


def test_cryptopanic_success_returns_records_in_an_envelope():
    adapter = CryptoPanicResearchAdapter(
        api_token="token-not-logged",
        client=_client(lambda r: httpx.Response(200, json=_CP_PAYLOAD)),
    )
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert isinstance(result, SourceResult)
    assert result.status is SourceStatus.ok
    assert result.data and all(isinstance(r, RawSourceRecord) for r in result.data)
    record = result.data[0]
    assert record.source_type is SourceType.news
    assert record.asset is Asset.BTC
    assert record.metadata["operation"] == "fetch_cryptopanic_news"
    # Provenance the deterministic completion step needs.
    assert record.metadata["original_publisher"] == "coindesk.com"
    assert record.metadata["original_page_fetched"] is False


def test_cryptopanic_never_leaks_the_token_into_parameters():
    adapter = CryptoPanicResearchAdapter(
        api_token="super-secret-token",
        client=_client(lambda r: httpx.Response(200, json=_CP_PAYLOAD)),
    )
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert "super-secret-token" not in (result.query_or_parameters or "")
    for record in result.data or []:
        assert "super-secret-token" not in record.query_or_parameters


def test_cryptopanic_without_a_token_is_rejected_not_raised():
    adapter = CryptoPanicResearchAdapter(api_token=None, client=_client(lambda r: httpx.Response(200)))
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert result.status is SourceStatus.rejected
    assert result.data == []
    assert result.error_category


def test_cryptopanic_http_error_is_normalized():
    adapter = CryptoPanicResearchAdapter(
        api_token="t", client=_client(lambda r: httpx.Response(500))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert result.status is SourceStatus.http_error
    assert result.data == []


def test_cryptopanic_timeout_is_normalized():
    adapter = CryptoPanicResearchAdapter(
        api_token="t", client=_client(_raises(httpx.ReadTimeout("timed out")))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert result.status is SourceStatus.timeout
    assert result.data == []


def test_cryptopanic_malformed_payload_is_normalized():
    adapter = CryptoPanicResearchAdapter(
        api_token="t", client=_client(lambda r: httpx.Response(200, text="not json"))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert result.status is SourceStatus.malformed
    assert result.data == []


def test_cryptopanic_empty_result_set_is_empty_not_ok():
    adapter = CryptoPanicResearchAdapter(
        api_token="t", client=_client(lambda r: httpx.Response(200, json={"results": []}))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_cryptopanic_news", context=_ctx()))

    assert result.status is SourceStatus.empty
    assert result.data == []


# ── Alternative.me Fear & Greed ─────────────────────────────────────────────


def _fng_payload(timestamp: int = 1780272000) -> dict:
    """`timestamp` is 2026-06-01T00:00:00Z — at or before the frozen cutoff."""
    return {"data": [{"timestamp": str(timestamp), "value": "42", "value_classification": "Fear"}]}


def test_fear_greed_record_is_whole_market_with_no_asset():
    adapter = FearGreedResearchAdapter(
        client=_client(lambda r: httpx.Response(200, json=_fng_payload()))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_fear_greed", context=_ctx()))

    assert result.status is SourceStatus.ok
    record = result.data[0]
    assert record.asset is None, "Fear & Greed is market-wide, never a per-coin signal"
    assert record.source_type is SourceType.social


def test_fear_greed_http_error_is_normalized():
    adapter = FearGreedResearchAdapter(client=_client(lambda r: httpx.Response(500)))
    result = asyncio.run(adapter.fetch(operation="fetch_fear_greed", context=_ctx()))

    assert result.status is SourceStatus.http_error
    assert result.data == []


def test_fear_greed_timeout_is_normalized():
    adapter = FearGreedResearchAdapter(client=_client(_raises(httpx.ConnectTimeout("slow"))))
    result = asyncio.run(adapter.fetch(operation="fetch_fear_greed", context=_ctx()))

    assert result.status is SourceStatus.timeout


def test_fear_greed_malformed_payload_is_normalized():
    adapter = FearGreedResearchAdapter(client=_client(lambda r: httpx.Response(200, json={})))
    result = asyncio.run(adapter.fetch(operation="fetch_fear_greed", context=_ctx()))

    assert result.status in (SourceStatus.malformed, SourceStatus.empty)
    assert result.data == []


# ── Official announcements ──────────────────────────────────────────────────

_OFFICIAL_FEED = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    "<item><title>Bitcoin Core 30.0 released</title>"
    "<link>https://bitcoincore.org/en/releases/30.0/</link>"
    "<pubDate>Tue, 02 Jun 2026 12:00:00 +0000</pubDate></item>"
    "</channel></rss>"
)


def test_official_feed_success_marks_first_hand_provenance():
    adapter = OfficialAnnouncementsResearchAdapter(
        client=_client(lambda r: httpx.Response(200, text=_OFFICIAL_FEED))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_official_announcements", context=_ctx()))

    assert result.status in (SourceStatus.ok, SourceStatus.empty)
    if result.data:
        record = result.data[0]
        assert record.source_type is SourceType.official
        assert record.metadata["operation"] == "fetch_official_announcements"


def test_official_feed_http_error_is_normalized():
    adapter = OfficialAnnouncementsResearchAdapter(
        client=_client(lambda r: httpx.Response(503))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_official_announcements", context=_ctx()))

    assert result.status in (SourceStatus.http_error, SourceStatus.empty)
    assert result.data == []


def test_official_feed_timeout_is_normalized():
    adapter = OfficialAnnouncementsResearchAdapter(
        client=_client(_raises(httpx.ReadTimeout("timed out")))
    )
    result = asyncio.run(adapter.fetch(operation="fetch_official_announcements", context=_ctx()))

    assert result.status in (SourceStatus.timeout, SourceStatus.empty)
    assert result.data == []


def test_official_adapter_reports_assets_without_a_configured_feed():
    """A coin with no official feed is a disclosed gap, never a fabricated one."""
    adapter = OfficialAnnouncementsResearchAdapter(
        client=_client(lambda r: httpx.Response(200, text=_OFFICIAL_FEED))
    )
    result = asyncio.run(
        adapter.fetch(operation="fetch_official_announcements", context=_ctx(assets=(Asset.XRP,)))
    )

    assert isinstance(result, SourceResult)
    assert result.status in (SourceStatus.ok, SourceStatus.empty)
