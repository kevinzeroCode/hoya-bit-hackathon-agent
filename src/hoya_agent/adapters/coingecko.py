"""CoinGecko public REST adapter — OPTIONAL secondary market source (Task 18).

Binance remains the sole baseline live market source (Task 4,
`.kiro/steering/competition-rules.md` §Approved Data Policy); this adapter never
replaces it and its failure is always non-blocking. CoinGecko's `/simple/price`
gives one live USD snapshot per asset — an aggregated, not first-hand, reading —
so it maps to `SourceClass.MARKET_AGGREGATOR` (`medium` reliability, the same
class the static reliability table already reserves for it). No API key.

The snapshot's `metric_value` is exposed so a later stage can cross-check it
against the run's Binance close without re-parsing `normalized_fact` text; this
adapter itself does not perform that comparison — see `docs/Gold-Plan.md` and
`tasks.md` Task 18 for the disclosure this enables.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from hoya_agent.adapters._errors import category_note, classify_error
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.drafts import pending
from hoya_agent.evidence.policies import SourceClass

API_URL = "https://api.coingecko.com/api/v3/simple/price"
UTC = timezone.utc

# CoinGecko coin ids for the five-asset request allowlist (Features.md §5.2).
COIN_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
}


async def fetch_coingecko_price(
    asset: str,
    *,
    client: httpx.AsyncClient,
    timeout: float = 45.0,
) -> WorkerResult:
    """One live USD price snapshot for `asset` as a `medium`-reliability draft.

    Never raises: any failure (unsupported asset, timeout, HTTP error, malformed
    body, missing field) returns `WorkerResult("failed", [], [note])`.
    """
    coin_id = COIN_IDS.get(asset)
    if coin_id is None:
        return WorkerResult("failed", [], [f"CoinGecko has no configured id for {asset}"])

    fetched_at = datetime.now(UTC)
    try:
        resp = await client.get(
            API_URL, params={"ids": coin_id, "vs_currencies": "usd"}, timeout=timeout
        )
        resp.raise_for_status()
        price = float(resp.json()[coin_id]["usd"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return WorkerResult(
            "failed",
            [],
            [category_note(f"CoinGecko fetch failed for {asset} (optional source)", classify_error(exc))],
        )

    draft = pending(
        source_class=SourceClass.MARKET_AGGREGATOR,
        provider_id="coingecko",
        asset=asset,
        source_type="market",
        source_name="CoinGecko",
        source_url="https://www.coingecko.com/en/coins/" + coin_id,
        # A /simple/price read has no distinct publish time of its own — it IS
        # the price at the moment fetched, so publish and fetch time coincide
        # rather than one standing in dishonestly for the other.
        published_at=fetched_at,
        fetched_at=fetched_at,
        query_or_parameters=f"coingecko /simple/price?ids={coin_id}&vs_currencies=usd",
        content_reference=f"CoinGecko simple price snapshot for {asset} ({coin_id})",
        normalized_fact=(
            f"{asset} 在 CoinGecko 的即時快照價格為 {price} USD"
            f"（截至 {fetched_at.isoformat()}；聚合快照，非交易所第一手數據）。"
        ),
        metric_name="coingecko_price_usd",
        metric_value=price,
    )
    return WorkerResult("completed", [draft], [])
