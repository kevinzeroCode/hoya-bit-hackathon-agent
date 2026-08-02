"""Binance public REST adapter — designated baseline live market source.

Fetches daily UTC klines and returns MarketBars (same shape as the organizer CSV,
so the Market Worker can compute indicators from either). Coin-agnostic via a
fixed {ASSET}USDT allowlist. No API key. Only completed daily candles at or
before analysis_as_of are returned; failures degrade to an empty result rather
than raising, so an optional/baseline source failure never crashes the run.

Keep Binance and the organizer CSV as DISTINCT sources (different independence
groups); never claim the CSV came from Binance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from hoya_agent.data.types import MarketBar

KLINES_URL = "https://api.binance.com/api/v3/klines"
UTC = timezone.utc

_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
}

MAX_KLINE_PAGE = 1000

SOURCE_NAME = "Binance Spot"
INDEPENDENCE_GROUP = "binance.com"


async def fetch_binance_daily(
    asset: str,
    *,
    analysis_as_of: datetime,
    client: httpx.AsyncClient,
    limit: int = 500,
    timeout: float = 45.0,
) -> tuple[list[MarketBar], list[str]]:
    """Return (bars, degradation_notes). Bars are sorted, completed, <= analysis_as_of."""
    if asset not in _SYMBOLS:
        raise ValueError(f"unsupported asset: {asset}")
    symbol = _SYMBOLS[asset]

    try:
        resp = await client.get(
            KLINES_URL,
            params={"symbol": symbol, "interval": "1d", "limit": limit},
            timeout=timeout,
        )
        resp.raise_for_status()
        rows = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return [], [f"Binance fetch failed for {symbol}: {type(exc).__name__}"]

    bars: list[MarketBar] = []
    degradation: list[str] = []
    for row in rows:
        try:
            open_ms, close_ms = int(row[0]), int(row[6])
            o, h, low, c, v = (float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
        except (IndexError, ValueError, TypeError):
            degradation.append("skipped malformed kline")
            continue
        # Only keep candles that fully closed at or before the cutoff.
        if datetime.fromtimestamp(close_ms / 1000, tz=UTC) > analysis_as_of:
            continue
        day = datetime.fromtimestamp(open_ms / 1000, tz=UTC).date()
        bars.append(MarketBar(date=day, open=o, high=h, low=low, close=c, volume=v))

    bars.sort(key=lambda b: b.date)
    return bars, degradation


async def fetch_binance_daily_history(
    asset: str,
    *,
    analysis_as_of: datetime,
    client: httpx.AsyncClient,
    days: int = 365 * 5 + 2,
    timeout: float = 45.0,
) -> tuple[list[MarketBar], list[str]]:
    """Fetch up to ``days`` completed daily candles using Binance pagination.

    This is intended for the one-time local cache prefetch, not every run.
    """
    if asset not in _SYMBOLS:
        raise ValueError(f"unsupported asset: {asset}")
    if days <= 0:
        raise ValueError("days must be positive")

    symbol = _SYMBOLS[asset]
    end_ms = int(analysis_as_of.timestamp() * 1000)
    start_ms = int((analysis_as_of - timedelta(days=days)).timestamp() * 1000)
    bars: list[MarketBar] = []
    degradation: list[str] = []
    seen_open_ms: set[int] = set()

    while start_ms < end_ms:
        try:
            response = await client.get(
                KLINES_URL,
                params={
                    "symbol": symbol,
                    "interval": "1d",
                    "limit": MAX_KLINE_PAGE,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            degradation.append(f"Binance history fetch failed for {symbol}: {type(exc).__name__}")
            break
        if not isinstance(rows, list) or not rows:
            break

        last_open_ms = start_ms
        for row in rows:
            try:
                open_ms, close_ms = int(row[0]), int(row[6])
                o, h, low, c, v = (
                    float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])
                )
            except (IndexError, ValueError, TypeError):
                degradation.append("skipped malformed historical kline")
                continue
            last_open_ms = max(last_open_ms, open_ms)
            if open_ms in seen_open_ms or datetime.fromtimestamp(close_ms / 1000, tz=UTC) > analysis_as_of:
                continue
            seen_open_ms.add(open_ms)
            bars.append(
                MarketBar(
                    date=datetime.fromtimestamp(open_ms / 1000, tz=UTC).date(),
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=v,
                )
            )
        if len(rows) < MAX_KLINE_PAGE or last_open_ms <= start_ms:
            break
        start_ms = last_open_ms + 86_400_000

    bars.sort(key=lambda b: b.date)
    return bars, degradation
