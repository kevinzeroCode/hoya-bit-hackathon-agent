"""Port-conforming adapters — wrap P2's sync fetchers to satisfy the async ports.

`ports.py` defines async boundaries the orchestrator (S4) calls:
  - MarketDataAdapter.fetch_daily_bars / fetch_snapshot  → SourceResult[list[MarketBar]]
  - ResearchSourceAdapter.fetch                          → SourceResult[list[RawSourceRecord]]

Every adapter method returns a `SourceResult` envelope (design.md §8.7) carrying
provider identity, status, data, timing metadata, safe query parameters, and a
normalized error category.  Degradation is surfaced — never silently discarded.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import date, datetime, timezone

import httpx

from hoya_agent.adapters.binance import fetch_binance_daily
from hoya_agent.adapters.organizer_csv import default_data_dir, load_organizer_csv
from hoya_agent.adapters.rss import fetch_rss_news
from hoya_agent.data.types import MarketBar
from hoya_agent.models import (
    Asset,
    RawSourceRecord,
    RunContext,
    SourceResult,
    SourceStatus,
    SourceType,
)

_UA = {"User-Agent": "Mozilla/5.0 (research; hoya-market-agent/0.1)"}


def _new_client() -> httpx.Client:
    return httpx.Client(headers=_UA, follow_redirects=True, timeout=30.0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── MarketDataAdapter implementations ───────────────────────────────────────


class CsvMarketAdapter:
    """MarketDataAdapter over the organizer Daily OHLCV CSV (deterministic, offline)."""

    async def fetch_daily_bars(
        self,
        *,
        asset: Asset,
        start: date,
        end: date,
        context: RunContext,
    ) -> SourceResult[list[MarketBar]]:
        t0 = time.monotonic()
        path = default_data_dir() / f"{asset.value}_daily_ohlcv.csv"
        bars = await asyncio.to_thread(load_organizer_csv, path)
        selected = [b for b in bars if start <= b.date <= end]
        latency = (time.monotonic() - t0) * 1000
        return SourceResult[list[MarketBar]](
            source_name="public_market_data",
            status=SourceStatus.ok if selected else SourceStatus.empty,
            data=selected,
            fetched_at=_utcnow(),
            query_or_parameters=f"asset={asset.value}&start={start}&end={end}",
            latency_ms=latency,
        )

    async def fetch_snapshot(
        self, *, asset: Asset, context: RunContext
    ) -> SourceResult[MarketBar | None]:
        t0 = time.monotonic()
        path = default_data_dir() / f"{asset.value}_daily_ohlcv.csv"
        bars = await asyncio.to_thread(load_organizer_csv, path)
        eligible = [b for b in bars if b.date <= context.analysis_as_of.date()]
        result = eligible[-1] if eligible else None
        latency = (time.monotonic() - t0) * 1000
        return SourceResult[MarketBar | None](
            source_name="public_market_data",
            status=SourceStatus.ok if result else SourceStatus.empty,
            data=result,
            fetched_at=_utcnow(),
            query_or_parameters=f"asset={asset.value}&as_of={context.analysis_as_of.date()}",
            latency_ms=latency,
        )


class BinanceMarketAdapter:
    """MarketDataAdapter over Binance public klines (live baseline)."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    async def fetch_daily_bars(
        self,
        *,
        asset: Asset,
        start: date,
        end: date,
        context: RunContext,
    ) -> SourceResult[list[MarketBar]]:
        client = self._client or _new_client()
        t0 = time.monotonic()
        bars, degradation = await asyncio.to_thread(
            fetch_binance_daily,
            asset.value,
            analysis_as_of=context.analysis_as_of,
            client=client,
        )
        selected = [b for b in bars if start <= b.date <= end]
        latency = (time.monotonic() - t0) * 1000

        if degradation:
            status = SourceStatus.empty if not selected else SourceStatus.ok
            error_category = degradation[0]
        else:
            status = SourceStatus.ok if selected else SourceStatus.empty
            error_category = None

        return SourceResult[list[MarketBar]](
            source_name="binance-klines",
            source_url="https://api.binance.com/api/v3/klines",
            status=status,
            data=selected,
            fetched_at=_utcnow(),
            query_or_parameters=f"symbol={asset.value}USDT&interval=1d",
            latency_ms=latency,
            error_category=error_category,
        )

    async def fetch_snapshot(
        self, *, asset: Asset, context: RunContext
    ) -> SourceResult[MarketBar | None]:
        """24hr ticker is not part of MVP scope — returns unavailable."""
        return SourceResult[MarketBar | None](
            source_name="binance-klines",
            status=SourceStatus.empty,
            data=None,
            fetched_at=_utcnow(),
            query_or_parameters=f"asset={asset.value}&type=snapshot",
            content_reference="24hr ticker not part of MVP",
        )


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
        content=draft.normalized_fact,
        query_or_parameters=draft.query_or_parameters,
        metadata={
            "operation": operation,
            "source_reference": draft.content_reference,
            # These values are assigned deterministically by the source adapter,
            # never by the extraction model.  Preserve them across the raw-record
            # boundary so orchestration can admit a schema-valid extracted fact.
            "reliability": draft.reliability,
            "independence_group": draft.independence_group,
        },
    )


class RssResearchAdapter:
    """ResearchSourceAdapter over a first-party outlet RSS feed → RawSourceRecord[]."""

    def __init__(
        self,
        *,
        feed_url: str,
        source_name: str,
        publisher_domain: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._feed_url = feed_url
        self._source_name = source_name
        self._publisher_domain = publisher_domain
        self._client = client

    async def fetch(
        self, *, operation: str, context: RunContext, **params: object
    ) -> SourceResult[list[RawSourceRecord]]:
        client = self._client or _new_client()
        lookback = int(params.get("lookback_days", 14))  # type: ignore[arg-type]
        records: list[RawSourceRecord] = []
        degradation_notes: list[str] = []
        t0 = time.monotonic()

        for asset in context.request.assets:
            result = await asyncio.to_thread(
                fetch_rss_news,
                asset.value,
                analysis_as_of=context.analysis_as_of,
                client=client,
                feed_url=self._feed_url,
                source_name=self._source_name,
                publisher_domain=self._publisher_domain,
                lookback_days=lookback,
            )
            records.extend(
                _to_raw_record(d, operation=operation) for d in result.drafts
            )
            degradation_notes.extend(result.degradation)

        latency = (time.monotonic() - t0) * 1000
        error_category = degradation_notes[0] if degradation_notes else None

        return SourceResult[list[RawSourceRecord]](
            source_name=self._source_name,
            source_url=self._feed_url,
            status=SourceStatus.ok if records else SourceStatus.empty,
            data=records,
            fetched_at=_utcnow(),
            query_or_parameters=(
                f"feed_url={self._feed_url}&lookback_days={lookback}"
            ),
            latency_ms=latency,
            error_category=error_category,
        )

