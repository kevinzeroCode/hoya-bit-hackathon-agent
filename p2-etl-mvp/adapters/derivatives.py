"""Binance USDT-perp derivatives adapter — a NEW market dimension (leverage/funding).

Funding rate is a live sentiment signal distinct from spot price: a positive rate
means perpetual longs pay shorts (crowded long leverage), negative the reverse.
Coin-agnostic via a fixed {ASSET}USDT-perp allowlist. No API key. High reliability
(exchange-published, deterministic value). Stanceless: we state the number and its
mechanical meaning, never a bullish/bearish conclusion (that is P3's job).

This is a current snapshot (funding settles every 8h), not a completed daily bar,
so it is recorded with its own funding timestamp and only kept if that time is at
or before the live cutoff.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from data.market_worker import WorkerResult
from evidence.policies import SourceClass, independence_group, reliability_for
from evidence.types import EvidenceDraft

UTC = timezone.utc
PREMIUM_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"

_SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "BNB": "BNBUSDT", "XRP": "XRPUSDT"}
SOURCE_NAME = "Binance Futures"
INDEPENDENCE_GROUP = "binance.com"


def fetch_funding_rate(
    asset: str, *, analysis_as_of: datetime, client: httpx.Client, timeout: float = 45.0
) -> WorkerResult:
    if asset not in _SYMBOLS:
        raise ValueError(f"unsupported asset: {asset}")
    symbol = _SYMBOLS[asset]
    fetched_at = datetime.now(UTC)
    try:
        resp = client.get(PREMIUM_URL, params={"symbol": symbol}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        rate = float(data["lastFundingRate"])
        ts = datetime.fromtimestamp(int(data["time"]) / 1000, tz=UTC)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return WorkerResult("failed", [], [f"funding rate fetch failed for {symbol}: {type(exc).__name__}"])

    # Live snapshot: reject only if dated after the cutoff day (avoids off-by-seconds
    # exclusion when the server message time is moments after the captured cutoff).
    if ts.date() > analysis_as_of.date():
        return WorkerResult("failed", [], [f"funding snapshot after cutoff for {symbol}"])

    side = "多頭付費給空頭" if rate > 0 else ("空頭付費給多頭" if rate < 0 else "中性")
    draft = EvidenceDraft(
        asset=asset, source_type="market", source_name=SOURCE_NAME,
        source_url=PREMIUM_URL, published_at=ts, fetched_at=fetched_at,
        query_or_parameters=f"binance fapi premiumIndex symbol={symbol}; live snapshot",
        content_reference=f"perpetual funding rate = {rate:.6f} at {ts.isoformat()}",
        normalized_fact=f"{asset} 永續合約資金費率為 {rate * 100:+.4f}%（{side}，截至 {ts.date()} UTC 快照）",
        reliability=reliability_for(SourceClass.EXCHANGE_MARKET_API),
        independence_group=independence_group(original_publisher=INDEPENDENCE_GROUP, source_url=PREMIUM_URL),
        metric_name="funding_rate", metric_value=rate,
    )
    return WorkerResult("completed", [draft], [])
