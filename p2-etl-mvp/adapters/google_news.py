"""Google News RSS *search* adapter — query-by-coin news that guarantees coverage.

General outlet feeds are BTC/ETH-heavy, so minor coins (SOL/BNB/XRP) get almost no
hits. Google News search is queried BY the coin, returning many items for every
asset — this closes the coin-agnostic coverage gap so any drawn coin has news.

It is an AGGREGATOR (it reposts other outlets), so reliability is `low` and the
independence group maps to each item's ORIGINAL publisher domain (from the
<source url> element), never news.google.com. Titles are stored as untrusted
quoted data. No API key.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from adapters._assets import mentions
from data.market_worker import WorkerResult
from evidence.policies import SourceClass, independence_group, reliability_for
from evidence.types import EvidenceDraft

UTC = timezone.utc
SEARCH_URL = "https://news.google.com/rss/search"
_QUERY = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binance coin OR BNB", "XRP": "xrp ripple",
}


def fetch_google_news(
    asset: str, *, analysis_as_of: datetime, client: httpx.Client,
    lookback_days: int = 14, limit: int = 15, timeout: float = 45.0,
) -> WorkerResult:
    if asset not in _QUERY:
        raise ValueError(f"unsupported asset: {asset}")
    query = _QUERY[asset]
    earliest = analysis_as_of - timedelta(days=lookback_days)
    fetched_at = datetime.now(UTC)
    params = {"q": f"{query} when:{lookback_days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
    try:
        resp = client.get(SEARCH_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except (httpx.HTTPError, ET.ParseError):
        return WorkerResult("failed", [], [f"Google News fetch failed for {asset} (optional source)"])

    drafts: list[EvidenceDraft] = []
    for item in root.iter("item"):
        title_el, date_el = item.find("title"), item.find("pubDate")
        link_el, src_el = item.find("link"), item.find("source")
        if title_el is None or date_el is None or not (title_el.text or "").strip():
            continue
        title = title_el.text.strip()
        try:
            published = parsedate_to_datetime(date_el.text)
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if published > analysis_as_of or published < earliest:
            continue
        if not mentions(asset, title):  # query is targeted, but keep only on-topic titles
            continue
        src_name = (src_el.text if src_el is not None else None) or "Google News"
        src_url = src_el.get("url") if src_el is not None else None
        link = (link_el.text if link_el is not None else SEARCH_URL) or SEARCH_URL
        drafts.append(
            EvidenceDraft(
                asset=asset, source_type="news", source_name=src_name, source_url=link,
                published_at=published, fetched_at=fetched_at,
                query_or_parameters=f"google news search q={query!r}; lookback={lookback_days}d",
                content_reference=f"{src_name} via Google News（{published.date()}）",
                normalized_fact=title,  # aggregator headline, untrusted quoted data
                reliability=reliability_for(SourceClass.NEWS_AGGREGATOR),
                independence_group=independence_group(source_url=src_url or link),
            )
        )
        if len(drafts) >= limit:
            break

    if not drafts:
        return WorkerResult("failed", [], [f"no Google News items for {asset} in window"])
    return WorkerResult("completed", drafts, [])
