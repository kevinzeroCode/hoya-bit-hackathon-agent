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

from datetime import datetime, timezone

import httpx

from data.types import MarketBar

KLINES_URL = "https://api.binance.com/api/v3/klines"
UTC = timezone.utc

_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
}

SOURCE_NAME = "Binance Spot"
INDEPENDENCE_GROUP = "binance.com"


def fetch_binance_daily(
    asset: str,
    *,
    analysis_as_of: datetime,
    client: httpx.Client,
    limit: int = 500,
    timeout: float = 45.0,
) -> tuple[list[MarketBar], list[str]]:
    """Return (bars, degradation_notes). Bars are sorted, completed, <= analysis_as_of."""
    if asset not in _SYMBOLS:
        raise ValueError(f"unsupported asset: {asset}")
    symbol = _SYMBOLS[asset]

    try:
        resp = client.get(
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
