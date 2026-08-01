"""Port-conforming adapters — wrap P2's sync fetchers to satisfy the async ports.

`ports.py` defines async boundaries the orchestrator (S4) calls:
  - MarketDataAdapter.fetch_daily_bars / fetch_snapshot  → returns bars
  - ResearchSourceAdapter.fetch                          → returns list[RawSourceRecord]

P2's underlying fetchers are synchronous and (for research) currently produce
EvidenceDraft. These thin wrappers run them off the event loop (asyncio.to_thread)
and, for research, map to `RawSourceRecord` (evidence admission — reliability,
independence, content_hash — happens downstream in the Evidence Processor, not here).

Only MVP sources are wrapped (organizer CSV, Binance, first-party RSS); the same
pattern extends to the rest.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import date

import httpx

from hoya_agent.adapters.binance import fetch_binance_daily
from hoya_agent.adapters.organizer_csv import default_data_dir, load_organizer_csv
from hoya_agent.adapters.rss import fetch_rss_news
from hoya_agent.models import Asset, RawSourceRecord, RunContext, SourceType

_UA = {"User-Agent": "Mozilla/5.0 (research; hoya-market-agent/0.1)"}


def _new_client() -> httpx.Client:
    return httpx.Client(headers=_UA, follow_redirects=True, timeout=30.0)


# ── MarketDataAdapter implementations ───────────────────────────────────────

class CsvMarketAdapter:
    """MarketDataAdapter over the organizer Daily OHLCV CSV (deterministic, offline)."""

    async def fetch_daily_bars(self, *, asset: Asset, start: date, end: date, context: RunContext):
        path = default_data_dir() / f"{asset.value}_daily_ohlcv.csv"
        bars = await asyncio.to_thread(load_organizer_csv, path)
        return [b for b in bars if start <= b.date <= end]

    async def fetch_snapshot(self, *, asset: Asset, context: RunContext):
        path = default_data_dir() / f"{asset.value}_daily_ohlcv.csv"
        bars = await asyncio.to_thread(load_organizer_csv, path)
        eligible = [b for b in bars if b.date <= context.analysis_as_of.date()]
        return eligible[-1] if eligible else None


class BinanceMarketAdapter:
    """MarketDataAdapter over Binance public klines (live baseline)."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    async def fetch_daily_bars(self, *, asset: Asset, start: date, end: date, context: RunContext):
        client = self._client or _new_client()
        bars, _deg = await asyncio.to_thread(
            fetch_binance_daily, asset.value, analysis_as_of=context.analysis_as_of, client=client
        )
        return [b for b in bars if start <= b.date <= end]

    async def fetch_snapshot(self, *, asset: Asset, context: RunContext):
        return None  # 24hr ticker not part of the MVP


# ── ResearchSourceAdapter implementation ────────────────────────────────────

def _to_raw_record(draft, *, operation: str) -> RawSourceRecord:
    digest = hashlib.sha1(
        f"{draft.source_url or ''}|{draft.normalized_fact}".encode()
    ).hexdigest()[:16]
    return RawSourceRecord(
        record_id=f"{draft.source_name}-{digest}",
        source_name=draft.source_name,
        source_type=SourceType(draft.source_type),
        source_url=draft.source_url,
        asset=Asset(draft.asset) if draft.asset else None,
        published_at=draft.published_at,
        fetched_at=draft.fetched_at,
        title=draft.normalized_fact,
        content=draft.normalized_fact,  # RSS carries the headline; body admission is downstream
        query_or_parameters=draft.query_or_parameters,
        metadata={"operation": operation, "source_reference": draft.content_reference},
    )


class RssResearchAdapter:
    """ResearchSourceAdapter over a first-party outlet RSS feed → RawSourceRecord[]."""

    def __init__(self, *, feed_url: str, source_name: str, publisher_domain: str,
                 client: httpx.Client | None = None) -> None:
        self._feed_url = feed_url
        self._source_name = source_name
        self._publisher_domain = publisher_domain
        self._client = client

    async def fetch(self, *, operation: str, context: RunContext, **params: object) -> list[RawSourceRecord]:
        client = self._client or _new_client()
        lookback = int(params.get("lookback_days", 14))  # type: ignore[arg-type]
        records: list[RawSourceRecord] = []
        for asset in context.request.assets:
            result = await asyncio.to_thread(
                fetch_rss_news, asset.value, analysis_as_of=context.analysis_as_of, client=client,
                feed_url=self._feed_url, source_name=self._source_name,
                publisher_domain=self._publisher_domain, lookback_days=lookback,
            )
            records.extend(_to_raw_record(d, operation=operation) for d in result.drafts)
        return records
