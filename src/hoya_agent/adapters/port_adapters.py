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
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

import httpx

from hoya_agent.adapters._errors import (
    CATEGORY_HTTP_ERROR,
    CATEGORY_MALFORMED,
    CATEGORY_REJECTED,
    CATEGORY_TIMEOUT,
    category_of,
)
from hoya_agent.adapters.alternative_me import API_URL as FEAR_GREED_URL
from hoya_agent.adapters.alternative_me import fetch_fear_greed
from hoya_agent.adapters.binance import fetch_binance_daily
from hoya_agent.adapters.cryptopanic import CRYPTOPANIC_URL, fetch_cryptopanic_news
from hoya_agent.adapters.official import fetch_official_announcements
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


def _new_client() -> httpx.AsyncClient:
    """One shared client per run is the contract.

    `build_research_tool_registry` creates a single `AsyncClient` and hands it to
    every adapter. A wrapper building its own is the fallback for direct use in
    tests and scripts, not the composed path.
    """
    return httpx.AsyncClient(headers=_UA, follow_redirects=True, timeout=30.0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceUnavailable(RuntimeError):
    """A research source failed in a way worth disclosing as a source gap.

    Raised only by the registry handlers, whose caller (the frozen Research Agent)
    already converts an operation failure into a degradation note. An *empty*
    result is not an error and never raises.
    """

    def __init__(self, operation: str, status: SourceStatus, detail: str | None) -> None:
        super().__init__(f"{operation} unavailable: {status.value}{f' ({detail})' if detail else ''}")
        self.operation = operation
        self.status = status
        self.detail = detail


def _resolve_cutoff(context: RunContext | None, params: dict[str, object]) -> datetime:
    """The frozen cutoff, from a RunContext or from explicit parameters.

    Never recomputed from the wall clock: a source that widened its own cutoff
    could admit evidence published after `analysis_as_of`.
    """
    if context is not None:
        return context.analysis_as_of
    as_of = params.get("analysis_as_of")
    if not isinstance(as_of, datetime):
        raise ValueError("analysis_as_of is required when no RunContext is supplied")
    return as_of


def _resolve_target(
    context: RunContext | None, params: dict[str, object]
) -> tuple[list[Asset], datetime]:
    """Assets and frozen cutoff, from a RunContext or from explicit parameters.

    The static tool registry invokes operations with plain parameters rather than a
    RunContext, so both call shapes have to work.
    """
    as_of = _resolve_cutoff(context, params)
    if context is not None:
        return list(context.request.assets), as_of

    raw_assets = params.get("assets") or ()
    assets = [asset if isinstance(asset, Asset) else Asset(str(asset)) for asset in raw_assets]  # type: ignore[union-attr]
    if not assets:
        raise ValueError("at least one asset is required")
    return assets, as_of


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

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
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
        bars, degradation = await fetch_binance_daily(
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


def _to_raw_record(
    draft, *, operation: str, original_page_fetched: bool = False
) -> RawSourceRecord:
    digest = hashlib.sha1(
        f"{draft.source_url or ''}|{draft.normalized_fact}".encode()
    ).hexdigest()[:16]
    # `content` is what the bounded extraction call reads, so it carries the
    # source's own quotation when the adapter captured one. Grounding later checks
    # extracted numbers against exactly this text.
    reference = getattr(draft, "content_reference", "") or ""
    body = reference if reference.strip() else draft.normalized_fact
    return RawSourceRecord(
        record_id=f"{draft.source_name}-{digest}",
        source_name=draft.source_name,
        source_type=SourceType(draft.source_type),
        source_url=draft.source_url,
        asset=Asset(draft.asset) if draft.asset else None,
        published_at=draft.published_at,
        fetched_at=draft.fetched_at,
        title=draft.normalized_fact,
        content=body,
        query_or_parameters=draft.query_or_parameters,
        metadata={
            "operation": operation,
            "source_reference": reference,
            # Provenance the deterministic completion step needs; reliability and
            # independence group are decided by the processor, never by the model.
            "original_publisher": getattr(draft, "original_publisher", None)
            or getattr(draft, "provider_id", None)
            or "",
            "original_page_fetched": original_page_fetched,
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
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._feed_url = feed_url
        self._source_name = source_name
        self._publisher_domain = publisher_domain
        self._client = client

    async def fetch(
        self, *, operation: str, context: RunContext | None = None, **params: object
    ) -> SourceResult[list[RawSourceRecord]]:
        client = self._client or _new_client()
        lookback = int(params.get("lookback_days", 14) or 14)  # type: ignore[arg-type]
        assets, analysis_as_of = _resolve_target(context, params)
        records: list[RawSourceRecord] = []
        degradation_notes: list[str] = []
        t0 = time.monotonic()

        for asset in assets:
            result = await fetch_rss_news(
                asset.value,
                analysis_as_of=analysis_as_of,
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
            status=_status_for(records, degradation_notes),
            data=records,
            fetched_at=_utcnow(),
            query_or_parameters=(
                f"feed_url={self._feed_url}&lookback_days={lookback}"
            ),
            latency_ms=latency,
            error_category=error_category,
        )


def _status_for(records: list[RawSourceRecord], notes: list[str]) -> SourceStatus:
    """Records win; otherwise the adapter's normalized category decides.

    A source that returned nothing and reported no failure is `empty`, which is a
    disclosed gap rather than an error — the two must not be conflated because
    only one of them is worth retrying.
    """
    if records:
        return SourceStatus.ok
    category = category_of(notes)
    if category is None:
        return SourceStatus.empty
    return _CATEGORY_STATUS.get(category, SourceStatus.http_error)


_CATEGORY_STATUS = {
    CATEGORY_TIMEOUT: SourceStatus.timeout,
    CATEGORY_HTTP_ERROR: SourceStatus.http_error,
    CATEGORY_MALFORMED: SourceStatus.malformed,
    CATEGORY_REJECTED: SourceStatus.rejected,
}

#: Only transient outcomes justify a second attempt. `malformed` will be malformed
#: again, `rejected` means a missing credential, and `empty` is a real answer.
RETRYABLE_STATUSES = frozenset({SourceStatus.timeout, SourceStatus.http_error})

#: Upper bound for the single backoff. Jittered below this, never above it, so the
#: retry cannot eat a meaningful slice of the acquisition window.
DEFAULT_RETRY_BACKOFF_SECONDS = 1.5


async def fetch_with_single_retry(
    adapter: Any,
    *,
    operation: str,
    params: Mapping[str, Any],
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    random_source: Callable[[], float] = random.random,
) -> tuple[SourceResult[list[RawSourceRecord]], list[str]]:
    """Fetch once, and retry exactly once for a transient failure.

    Bounded by construction: one extra attempt, one jittered backoff below
    `backoff_seconds`, and no clock of its own — the acquisition window in
    `_fork_join` already owns the deadline and cancels straight through this.
    `CancelledError` is therefore re-raised untouched; retrying into a cancelled
    window would be exactly the behaviour the deadline exists to prevent.

    Returns `(result, notes)`; the notes disclose that a retry happened, so a
    flaky source is visible in the report rather than looking clean.
    """
    notes: list[str] = []

    async def attempt() -> SourceResult[list[RawSourceRecord]]:
        return await adapter.fetch(operation=operation, **params)

    try:
        result = await attempt()
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalized into a typed retry decision
        first_failure: str | None = f"{type(exc).__name__}"
        result = None  # type: ignore[assignment]
    else:
        first_failure = None
        if result.status not in RETRYABLE_STATUSES:
            return result, notes

    detail = first_failure or result.status.value
    await sleeper(backoff_seconds * (0.5 + 0.5 * random_source()))
    notes.append(
        f"來源 {operation} 首次取得失敗（{detail}），已在取證窗口內重試一次。"
    )

    try:
        retried = await attempt()
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - the gap is disclosed, never raised on
        if result is not None:
            return result, notes
        return (
            SourceResult[list[RawSourceRecord]](
                source_name=operation,
                status=SourceStatus.http_error,
                data=[],
                fetched_at=_utcnow(),
                error_category=f"{detail}; retry {type(exc).__name__}",
            ),
            notes,
        )
    return retried, notes


class CryptoPanicResearchAdapter:
    """ResearchSourceAdapter over the CryptoPanic aggregator feed.

    Aggregator records stay `low` reliability because the original article page is
    not fetched, and `original_publisher` is carried in metadata so the
    independence group belongs to that publisher rather than to CryptoPanic.
    The API token is never written into `query_or_parameters`.
    """

    def __init__(self, *, api_token: str | None, client: httpx.AsyncClient | None = None) -> None:
        self._api_token = api_token
        self._client = client

    async def fetch(
        self, *, operation: str, context: RunContext | None = None, **params: object
    ) -> SourceResult[list[RawSourceRecord]]:
        client = self._client or _new_client()
        lookback = int(params.get("lookback_days") or 14)  # type: ignore[arg-type]
        assets, analysis_as_of = _resolve_target(context, params)
        t0 = time.monotonic()
        result = await fetch_cryptopanic_news(
            assets=[asset.value for asset in assets],
            analysis_as_of=analysis_as_of,
            client=client,
            api_token=self._api_token,
            lookback_days=lookback,
        )
        notes = list(result.degradation)
        records = [
            _to_raw_record(draft, operation=operation, original_page_fetched=False)
            for draft in result.drafts
        ]
        return SourceResult[list[RawSourceRecord]](
            source_name="CryptoPanic",
            source_url=CRYPTOPANIC_URL,
            status=_status_for(records, notes),
            data=records,
            fetched_at=_utcnow(),
            # Token deliberately absent: `run_config.json` records only whether a
            # credential was configured, never its value.
            query_or_parameters=(
                f"currencies={','.join(a.value for a in assets)}"
                f"&lookback_days={lookback}&auth_token=<redacted>"
            ),
            latency_ms=(time.monotonic() - t0) * 1000,
            error_category=notes[0] if notes else None,
        )


class FearGreedResearchAdapter:
    """ResearchSourceAdapter over Alternative.me Fear & Greed.

    Whole-market context: the record carries `asset=None`, so it never counts
    toward a single asset's evidence quota and cannot alone support a per-coin
    conclusion.
    """

    def __init__(self, *, client: httpx.AsyncClient | None = None, limit: int = 7) -> None:
        self._client = client
        self._limit = limit

    async def fetch(
        self, *, operation: str, context: RunContext | None = None, **params: object
    ) -> SourceResult[list[RawSourceRecord]]:
        client = self._client or _new_client()
        analysis_as_of = _resolve_cutoff(context, params)
        t0 = time.monotonic()
        result = await fetch_fear_greed(
            analysis_as_of=analysis_as_of,
            client=client,
            limit=self._limit,
        )
        notes = list(result.degradation)
        records = [
            _to_raw_record(draft, operation=operation, original_page_fetched=False)
            for draft in result.drafts
        ]
        return SourceResult[list[RawSourceRecord]](
            source_name="Alternative.me Fear & Greed",
            source_url=FEAR_GREED_URL,
            status=_status_for(records, notes),
            data=records,
            fetched_at=_utcnow(),
            query_or_parameters=f"limit={self._limit}",
            latency_ms=(time.monotonic() - t0) * 1000,
            error_category=notes[0] if notes else None,
        )


class OfficialAnnouncementsResearchAdapter:
    """ResearchSourceAdapter over configured official project feeds.

    Best-effort by policy: an asset with no configured feed is a disclosed gap and
    never blocks the run. Records are first-hand, so the static policy grades them
    `high` — which is exactly why the feed list is configuration and not something
    a model may extend.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        feed_overrides: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._client = client
        self._feed_overrides = feed_overrides

    async def fetch(
        self, *, operation: str, context: RunContext | None = None, **params: object
    ) -> SourceResult[list[RawSourceRecord]]:
        client = self._client or _new_client()
        lookback = int(params.get("lookback_days") or 14)  # type: ignore[arg-type]
        assets, analysis_as_of = _resolve_target(context, params)
        t0 = time.monotonic()
        result = await fetch_official_announcements(
            assets=[asset.value for asset in assets],
            analysis_as_of=analysis_as_of,
            client=client,
            lookback_days=lookback,
            feed_overrides=self._feed_overrides,
        )
        notes = list(result.degradation)
        records = [
            _to_raw_record(draft, operation=operation, original_page_fetched=True)
            for draft in result.drafts
        ]
        return SourceResult[list[RawSourceRecord]](
            source_name="official-project-feeds",
            source_url=None,
            status=_status_for(records, notes),
            data=records,
            fetched_at=_utcnow(),
            query_or_parameters=f"assets={','.join(a.value for a in assets)}"
            f"&lookback_days={lookback}",
            latency_ms=(time.monotonic() - t0) * 1000,
            error_category=notes[0] if notes else None,
        )
