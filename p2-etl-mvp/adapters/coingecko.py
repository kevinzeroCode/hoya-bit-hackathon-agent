"""CoinGecko aggregated-price adapter — an optional second market source.

CoinGecko is an aggregated snapshot, not a first-hand exchange, so it is `medium`
reliability (vs Binance `high`). It is a distinct independence group (coingecko.com),
which strengthens upstream-source independence. Coin-agnostic via a fixed id map;
no API key for the basic simple/price endpoint. Optional / non-blocking.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from data.market_worker import WorkerResult
from evidence.policies import SourceClass, independence_group, reliability_for
from evidence.types import EvidenceDraft

API_URL = "https://api.coingecko.com/api/v3/simple/price"
UTC = timezone.utc

_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
}


def fetch_coingecko_snapshot(
    asset: str, *, analysis_as_of: datetime, client: httpx.Client, timeout: float = 45.0
) -> WorkerResult:
    if asset not in _IDS:
        raise ValueError(f"unsupported asset: {asset}")
    coin_id = _IDS[asset]
    fetched_at = datetime.now(UTC)

    try:
        resp = client.get(
            API_URL,
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()[coin_id]
        price = float(data["usd"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return WorkerResult("failed", [], [f"CoinGecko fetch failed for {asset} (optional source)"])

    change = data.get("usd_24h_change")
    change_txt = f"，24h 變化 {change:+.2f}%" if isinstance(change, (int, float)) else ""
    draft = EvidenceDraft(
        asset=asset,
        source_type="market",
        source_name="CoinGecko",
        source_url=API_URL,
        published_at=fetched_at,  # live snapshot; no separate source timestamp
        fetched_at=fetched_at,
        query_or_parameters=f"coingecko simple/price ids={coin_id}&vs=usd",
        content_reference=f"CoinGecko aggregated USD snapshot for {asset} at {fetched_at.isoformat()}",
        normalized_fact=f"{asset} 現價約 ${price:,.2f}{change_txt}（CoinGecko 聚合報價快照）",
        reliability=reliability_for(SourceClass.MARKET_AGGREGATOR),
        independence_group=independence_group(source_url=API_URL),
    )
    return WorkerResult("completed", [draft], [])
