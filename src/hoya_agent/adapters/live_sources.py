"""Live source composition — real-time market + sentiment, no LLM, no key.

These factories build the plain sync callables the deterministic pipeline injects
(`load_bars` and `extra_drafts`). All HTTP lives here in the adapter layer;
`orchestration/` receives only callables, so its no-`httpx` boundary holds.

The underlying fetchers are async (`httpx.AsyncClient`), but the pipeline calls
`load_bars`/`extra_drafts` synchronously from inside its own event loop, so we
bridge with a one-shot worker thread running its own loop (`asyncio.run` cannot
nest in a running loop).

Neither source needs credentials: Binance spot klines and the Alternative.me
Fear & Greed index are public. Bedrock (reasoning) is a separate, credentialed
layer added on top.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

import httpx

from hoya_agent.adapters.alternative_me import fetch_fear_greed
from hoya_agent.adapters.binance import fetch_binance_daily
from hoya_agent.adapters.coingecko import fetch_coingecko_price
from hoya_agent.adapters.organizer_csv import load_organizer_csv
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.drafts import PendingEvidence

# Binance caps klines at 1000/request; 1000 daily bars ≈ 2.7 years, enough for a
# stable anomaly sigma (needs ≥365) without pagination. Deeper history (the ~5y
# the exchange can serve) is a startTime-paginated follow-up.
_DEFAULT_KLINE_LIMIT = 1000

_T = TypeVar("_T")


def _run_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run a coroutine to completion from a synchronous caller.

    The pipeline invokes these callables synchronously from within an already
    running event loop, so a fresh loop in a worker thread is used instead of
    `asyncio.run` (which refuses to nest).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def binance_bar_loader(
    analysis_as_of: datetime,
    *,
    limit: int = _DEFAULT_KLINE_LIMIT,
    timeout: float = 45.0,
    cache_dir: str | os.PathLike[str] | None = None,
) -> Callable[[str], Sequence[MarketBar]]:
    """A sync `BarLoader(asset) -> bars` backed by live Binance daily klines.

    Raises ValueError when Binance yields nothing so the pipeline degrades that
    asset (its documented `load_bars` failure contract) rather than emitting an
    empty, misleading series.
    """

    def _load(asset: str) -> Sequence[MarketBar]:
        selected_cache = cache_dir or os.getenv("HOYA_MARKET_CACHE_DIR")
        if selected_cache:
            try:
                cached = load_organizer_csv(Path(selected_cache) / f"{asset}_daily_ohlcv.csv")
            except (FileNotFoundError, OSError, ValueError):
                cached = []
            if cached and cached[-1].date <= analysis_as_of.date():
                return cached

        async def _fetch() -> tuple[list[MarketBar], list[str]]:
            async with httpx.AsyncClient() as client:
                return await fetch_binance_daily(
                    asset, analysis_as_of=analysis_as_of, client=client, limit=limit, timeout=timeout
                )

        bars, degradation = _run_sync(_fetch())
        if not bars:
            raise ValueError("; ".join(degradation) or f"Binance returned no bars for {asset}")
        return bars

    return _load


def fear_greed_drafts(
    analysis_as_of: datetime, *, timeout: float = 45.0
) -> Callable[[], tuple[list[PendingEvidence], list[str]]]:
    """A sync `() -> (drafts, degradation)` for the live Fear & Greed index.

    Whole-market sentiment: one low-reliability `social` draft on its own
    independence group, so it adds a genuinely different source *type* to the
    ledger (the funnel stops being single-source) without any LLM call.
    """

    def _fetch() -> tuple[list[PendingEvidence], list[str]]:
        async def _do() -> Any:
            async with httpx.AsyncClient() as client:
                return await fetch_fear_greed(
                    analysis_as_of=analysis_as_of, client=client, timeout=timeout
                )

        result = _run_sync(_do())
        return list(result.drafts), list(result.degradation)

    return _fetch


def coingecko_drafts(
    assets: Sequence[str], *, timeout: float = 45.0
) -> Callable[[], tuple[list[PendingEvidence], list[str]]]:
    """A sync `() -> (drafts, degradation)` for CoinGecko's optional secondary
    market snapshot — Task 18. Never the baseline; per-asset failures degrade
    independently, so one unsupported/unavailable asset never drops the rest.
    """

    def _fetch() -> tuple[list[PendingEvidence], list[str]]:
        async def _do() -> list:
            async with httpx.AsyncClient() as client:
                results = []
                for asset in assets:
                    results.append(
                        await fetch_coingecko_price(asset, client=client, timeout=timeout)
                    )
                return results

        drafts: list[PendingEvidence] = []
        degradation: list[str] = []
        for result in _run_sync(_do()):
            drafts.extend(result.drafts)
            degradation.extend(result.degradation)
        return drafts, degradation

    return _fetch


def combine_extra_drafts(
    *factories: Callable[[], tuple[list[PendingEvidence], list[str]]],
) -> Callable[[], tuple[list[PendingEvidence], list[str]]]:
    """Chain several `extra_drafts` factories behind the one slot
    `OrganizerCsvPipeline` accepts. Each factory's own failure handling is
    unchanged — this only concatenates results, it does not add degradation of
    its own, and one factory raising is not caught here (each factory already
    degrades internally rather than raising, per its own contract)."""

    def _fetch() -> tuple[list[PendingEvidence], list[str]]:
        drafts: list[PendingEvidence] = []
        degradation: list[str] = []
        for factory in factories:
            f_drafts, f_degradation = factory()
            drafts.extend(f_drafts)
            degradation.extend(f_degradation)
        return drafts, degradation

    return _fetch
