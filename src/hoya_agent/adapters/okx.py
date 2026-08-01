"""OKX public REST adapter — a SECOND independent exchange market source.

Same shape as binance.py (returns MarketBars, so the Market Worker computes
indicators from either), but a DISTINCT independence group (okx.com). Having two
first-hand exchanges lets the pipeline cross-verify high-reliability market facts
instead of trusting a single venue.

Uses the UTC-aligned daily bar (`1Dutc`) to match the organizer CSV and Binance.
Coin-agnostic via a fixed {ASSET}-USDT allowlist. No API key. Only fully-closed
candles (OKX `confirm == "1"`) at or before analysis_as_of are returned; failures
degrade to an empty result rather than raising.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from hoya_agent.data.types import MarketBar

CANDLES_URL = "https://www.okx.com/api/v5/market/history-candles"
UTC = timezone.utc
_DAY_MS = 86_400_000

_SYMBOLS = {
    "BTC": "BTC-USDT",
    "ETH": "ETH-USDT",
    "SOL": "SOL-USDT",
    "BNB": "BNB-USDT",
    "XRP": "XRP-USDT",
}

SOURCE_NAME = "OKX Spot"
INDEPENDENCE_GROUP = "okx.com"


def fetch_okx_daily(
    asset: str,
    *,
    analysis_as_of: datetime,
    client: httpx.Client,
    limit: int = 300,
    timeout: float = 45.0,
) -> tuple[list[MarketBar], list[str]]:
    """Return (bars, degradation_notes). Bars are sorted, closed, <= analysis_as_of."""
    if asset not in _SYMBOLS:
        raise ValueError(f"unsupported asset: {asset}")
    symbol = _SYMBOLS[asset]

    try:
        resp = client.get(
            CANDLES_URL,
            params={"instId": symbol, "bar": "1Dutc", "limit": limit},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return [], [f"OKX fetch failed for {symbol}: {type(exc).__name__}"]

    if not isinstance(payload, dict) or payload.get("code") != "0":
        return [], [f"OKX returned error code for {symbol}: {payload.get('code') if isinstance(payload, dict) else 'malformed'}"]

    bars: list[MarketBar] = []
    degradation: list[str] = []
    for row in payload.get("data", []):
        try:
            open_ms = int(row[0])
            o, h, low, c, v = (float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
            confirm = str(row[8])
        except (IndexError, ValueError, TypeError):
            degradation.append("skipped malformed candle")
            continue
        # Only fully-closed candles, and only those closed at/before the cutoff.
        if confirm != "1":
            continue
        if datetime.fromtimestamp((open_ms + _DAY_MS) / 1000, tz=UTC) > analysis_as_of:
            continue
        day = datetime.fromtimestamp(open_ms / 1000, tz=UTC).date()
        bars.append(MarketBar(date=day, open=o, high=h, low=low, close=c, volume=v))

    bars.sort(key=lambda b: b.date)
    return bars, degradation
