"""Tests for port-conforming adapters (P2 fetchers → async ports)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import httpx

from hoya_agent.adapters.port_adapters import (
    BinanceMarketAdapter,
    CsvMarketAdapter,
    RssResearchAdapter,
)
from hoya_agent.clock import build_run_context
from hoya_agent.data.types import MarketBar
from hoya_agent.models import AnalysisRequest, Asset, RawSourceRecord, RunMode, SourceType
from tests.fakes import FixedClock

UTC = timezone.utc


def _ctx(as_of: datetime, assets=(Asset.BTC,)):
    req = AnalysisRequest(
        question="test", assets=list(assets), requested_at=as_of, analysis_as_of=as_of,
        run_mode=RunMode.rehearsal, run_id="run_20260603_000000_test",
    )
    return build_run_context(req, FixedClock(as_of))


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_csv_market_adapter_returns_bars_in_range():
    ctx = _ctx(datetime(2026, 5, 31, tzinfo=UTC))
    bars = asyncio.run(CsvMarketAdapter().fetch_daily_bars(
        asset=Asset.BTC, start=date(2026, 5, 1), end=date(2026, 5, 31), context=ctx))
    assert bars and all(isinstance(b, MarketBar) for b in bars)
    assert all(date(2026, 5, 1) <= b.date <= date(2026, 5, 31) for b in bars)


def test_csv_snapshot_returns_latest_eligible_bar():
    ctx = _ctx(datetime(2026, 5, 31, tzinfo=UTC))
    snap = asyncio.run(CsvMarketAdapter().fetch_snapshot(asset=Asset.BTC, context=ctx))
    assert isinstance(snap, MarketBar) and snap.date <= date(2026, 5, 31)


def test_binance_adapter_conforms_and_returns_bars():
    as_of = datetime(2026, 6, 3, tzinfo=UTC)
    def _kline(d, c):
        om = int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)
        return [om, "1", "2", "0", str(c), "10", om + 86_400_000 - 1, "0", 0, "0", "0", "0"]
    payload = [_kline(date(2026, 6, 1), 100), _kline(date(2026, 6, 2), 105)]
    adapter = BinanceMarketAdapter(client=_mock_client(lambda r: httpx.Response(200, json=payload)))
    bars = asyncio.run(adapter.fetch_daily_bars(
        asset=Asset.BTC, start=date(2026, 6, 1), end=date(2026, 6, 3), context=_ctx(as_of)))
    assert [b.date for b in bars] == [date(2026, 6, 1), date(2026, 6, 2)]


def test_rss_research_adapter_returns_raw_records():
    as_of = datetime(2026, 6, 3, tzinfo=UTC)
    feed = ('<?xml version="1.0"?><rss version="2.0"><channel>'
            '<item><title>Bitcoin rallies on ETF inflows</title>'
            '<link>https://example.com/a</link>'
            '<pubDate>Mon, 02 Jun 2026 12:00:00 +0000</pubDate></item>'
            '</channel></rss>')
    adapter = RssResearchAdapter(
        feed_url="https://example.com/rss", source_name="CoinDesk", publisher_domain="coindesk.com",
        client=_mock_client(lambda r: httpx.Response(200, text=feed)))
    records = asyncio.run(adapter.fetch(operation="news.rss", context=_ctx(as_of)))
    assert records and all(isinstance(r, RawSourceRecord) for r in records)
    r = records[0]
    assert r.source_type == SourceType.news
    assert r.asset == Asset.BTC
    assert r.title and "Bitcoin" in r.title
    assert r.record_id  # non-empty stable id
    assert r.metadata["operation"] == "news.rss"
