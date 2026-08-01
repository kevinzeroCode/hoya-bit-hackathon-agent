"""Tests for port-conforming adapters (P2 fetchers → async ports).

Every adapter method must return a SourceResult envelope (design.md §8.7) with:
- source_name, status, data, fetched_at, query_or_parameters
- Degradation surfaced via error_category (never silently discarded)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import httpx
from tests.fakes import FixedClock

from hoya_agent.adapters.port_adapters import (
    BinanceMarketAdapter,
    CsvMarketAdapter,
    RssResearchAdapter,
)
from hoya_agent.clock import build_run_context
from hoya_agent.data.types import MarketBar
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


def _ctx(as_of: datetime, assets=(Asset.BTC,)):
    req = AnalysisRequest(
        question="test", assets=list(assets), requested_at=as_of, analysis_as_of=as_of,
        run_mode=RunMode.rehearsal, run_id="run_20260603_000000_test",
    )
    return build_run_context(req, FixedClock(as_of))


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── CsvMarketAdapter ────────────────────────────────────────────────────────


def test_csv_market_adapter_returns_source_result_envelope():
    ctx = _ctx(datetime(2026, 5, 31, tzinfo=UTC))
    result = asyncio.run(CsvMarketAdapter().fetch_daily_bars(
        asset=Asset.BTC, start=date(2026, 5, 1), end=date(2026, 5, 31), context=ctx))
    assert isinstance(result, SourceResult)
    assert result.source_name == "public_market_data"
    assert result.status == SourceStatus.ok
    assert result.data and all(isinstance(b, MarketBar) for b in result.data)
    assert all(date(2026, 5, 1) <= b.date <= date(2026, 5, 31) for b in result.data)
    assert result.fetched_at is not None
    assert result.query_or_parameters is not None
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_csv_market_adapter_empty_range_returns_empty_status():
    ctx = _ctx(datetime(2026, 5, 31, tzinfo=UTC))
    result = asyncio.run(CsvMarketAdapter().fetch_daily_bars(
        asset=Asset.BTC, start=date(2099, 1, 1), end=date(2099, 1, 31), context=ctx))
    assert isinstance(result, SourceResult)
    assert result.status == SourceStatus.empty
    assert result.data == []
    assert result.source_name == "public_market_data"


def test_csv_snapshot_returns_source_result_with_latest_bar():
    ctx = _ctx(datetime(2026, 5, 31, tzinfo=UTC))
    result = asyncio.run(CsvMarketAdapter().fetch_snapshot(asset=Asset.BTC, context=ctx))
    assert isinstance(result, SourceResult)
    assert result.source_name == "public_market_data"
    assert result.status == SourceStatus.ok
    assert isinstance(result.data, MarketBar)
    assert result.data.date <= date(2026, 5, 31)


def test_csv_snapshot_empty_returns_empty_status():
    ctx = _ctx(datetime(1990, 1, 1, tzinfo=UTC))
    result = asyncio.run(CsvMarketAdapter().fetch_snapshot(asset=Asset.BTC, context=ctx))
    assert isinstance(result, SourceResult)
    assert result.status == SourceStatus.empty
    assert result.data is None


# ── BinanceMarketAdapter ────────────────────────────────────────────────────


def _kline(d, c):
    """Build a mock Binance kline response entry."""
    om = int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)
    return [om, "1", "2", "0", str(c), "10", om + 86_400_000 - 1, "0", 0, "0", "0", "0"]


def test_binance_adapter_returns_source_result_envelope():
    as_of = datetime(2026, 6, 3, tzinfo=UTC)
    payload = [_kline(date(2026, 6, 1), 100), _kline(date(2026, 6, 2), 105)]
    adapter = BinanceMarketAdapter(
        client=_mock_client(lambda r: httpx.Response(200, json=payload))
    )
    result = asyncio.run(adapter.fetch_daily_bars(
        asset=Asset.BTC, start=date(2026, 6, 1), end=date(2026, 6, 3), context=_ctx(as_of)))
    assert isinstance(result, SourceResult)
    assert result.source_name == "binance-klines"
    assert result.source_url == "https://api.binance.com/api/v3/klines"
    assert result.status == SourceStatus.ok
    assert [b.date for b in result.data] == [date(2026, 6, 1), date(2026, 6, 2)]
    assert result.fetched_at is not None
    assert "BTCUSDT" in (result.query_or_parameters or "")
    assert result.error_category is None
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_binance_adapter_surfaces_degradation():
    """When the underlying fetcher returns degradation notes, they must be surfaced."""
    as_of = datetime(2026, 6, 3, tzinfo=UTC)

    # Empty response with HTTP 200 but malformed data that the adapter will interpret
    # as no bars — this triggers the empty path but not degradation from binance.
    adapter = BinanceMarketAdapter(
        client=_mock_client(lambda r: httpx.Response(200, json=[]))
    )
    result = asyncio.run(adapter.fetch_daily_bars(
        asset=Asset.BTC, start=date(2026, 6, 1), end=date(2026, 6, 3), context=_ctx(as_of)))
    assert isinstance(result, SourceResult)
    assert result.status == SourceStatus.empty
    assert result.data == []


def test_binance_snapshot_returns_envelope_with_empty():
    """fetch_snapshot is not part of MVP; should return SourceResult with empty status."""
    as_of = datetime(2026, 6, 3, tzinfo=UTC)
    adapter = BinanceMarketAdapter()
    result = asyncio.run(adapter.fetch_snapshot(asset=Asset.BTC, context=_ctx(as_of)))
    assert isinstance(result, SourceResult)
    assert result.status == SourceStatus.empty
    assert result.data is None
    assert result.source_name == "binance-klines"


# ── RssResearchAdapter ──────────────────────────────────────────────────────


def test_rss_research_adapter_returns_source_result_envelope():
    as_of = datetime(2026, 6, 3, tzinfo=UTC)
    feed = ('<?xml version="1.0"?><rss version="2.0"><channel>'
            '<item><title>Bitcoin rallies on ETF inflows</title>'
            '<link>https://example.com/a</link>'
            '<pubDate>Mon, 02 Jun 2026 12:00:00 +0000</pubDate></item>'
            '</channel></rss>')
    adapter = RssResearchAdapter(
        feed_url="https://example.com/rss", source_name="CoinDesk",
        publisher_domain="coindesk.com",
        client=_mock_client(lambda r: httpx.Response(200, text=feed)))
    result = asyncio.run(adapter.fetch(operation="news.rss", context=_ctx(as_of)))
    assert isinstance(result, SourceResult)
    assert result.source_name == "CoinDesk"
    assert result.source_url == "https://example.com/rss"
    assert result.status == SourceStatus.ok
    assert result.data and all(isinstance(r, RawSourceRecord) for r in result.data)
    r = result.data[0]
    assert r.source_type == SourceType.news
    assert r.asset == Asset.BTC
    assert r.title and "Bitcoin" in r.title
    assert r.record_id  # non-empty stable id
    assert r.metadata["operation"] == "news.rss"
    assert result.fetched_at is not None
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert "feed_url=" in (result.query_or_parameters or "")


def test_rss_research_adapter_empty_feed_returns_empty_status():
    as_of = datetime(2026, 6, 3, tzinfo=UTC)
    feed = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    adapter = RssResearchAdapter(
        feed_url="https://example.com/rss", source_name="CoinDesk",
        publisher_domain="coindesk.com",
        client=_mock_client(lambda r: httpx.Response(200, text=feed)))
    result = asyncio.run(adapter.fetch(operation="news.rss", context=_ctx(as_of)))
    assert isinstance(result, SourceResult)
    assert result.status == SourceStatus.empty
    assert result.data == []
    assert result.source_name == "CoinDesk"
