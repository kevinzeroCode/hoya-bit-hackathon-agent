"""RSS news adapter — first-party crypto outlet feeds (e.g. CoinDesk, Decrypt).

A first-party outlet feed is the original publisher, with the article URL and a
timestamp, so it is `medium` reliability (vs a third-party aggregator like
CryptoPanic, which stays `low`). Coin-agnostic: reads a general feed and keeps
only items mentioning the requested asset. Optional / non-blocking.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
from data.market_worker import WorkerResult
from evidence.policies import SourceClass, independence_group, reliability_for
from evidence.types import EvidenceDraft

from adapters._assets import mentions

UTC = timezone.utc


def fetch_rss_news(
    asset: str,
    *,
    analysis_as_of: datetime,
    client: httpx.Client,
    feed_url: str,
    source_name: str,
    publisher_domain: str,
    lookback_days: int = 14,
    timeout: float = 45.0,
) -> WorkerResult:
    mentions(asset, "")  # validate asset
    earliest = analysis_as_of - timedelta(days=lookback_days)
    fetched_at = datetime.now(UTC)
    try:
        resp = client.get(feed_url, timeout=timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except (httpx.HTTPError, ET.ParseError):
        return WorkerResult("failed", [], [f"RSS fetch failed for {source_name} (optional source)"])

    drafts: list[EvidenceDraft] = []
    for item in root.iter("item"):
        title_el, date_el, link_el = item.find("title"), item.find("pubDate"), item.find("link")
        if title_el is None or date_el is None or not (title_el.text or "").strip():
            continue
        title = title_el.text.strip()
        try:
            published = parsedate_to_datetime(date_el.text)
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if not mentions(asset, title) or published > analysis_as_of or published < earliest:
            continue
        link = (link_el.text if link_el is not None else feed_url) or feed_url
        drafts.append(
            EvidenceDraft(
                asset=asset,
                source_type="news",
                source_name=source_name,
                source_url=link,
                published_at=published,
                fetched_at=fetched_at,
                query_or_parameters=f"rss feed={feed_url}",
                content_reference=f"{source_name} RSS 標題（{published.date()}）",
                normalized_fact=title,
                reliability=reliability_for(SourceClass.ORIGINAL_NEWS_PAGE),
                independence_group=independence_group(
                    original_publisher=publisher_domain, source_url=link
                ),
            )
        )

    if not drafts:
        return WorkerResult("failed", [], [f"no relevant {source_name} items in window"])
    return WorkerResult("completed", drafts, [])
