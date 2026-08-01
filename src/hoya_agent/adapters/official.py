"""Official project announcement adapter — coin-agnostic RSS/Atom feeds.

Fetches official project blogs/announcements using RSS/Atom feeds. Each
project's feed URL is queried with the same code path regardless of asset.
Coin-agnostic: the asset symbol is a parameter; a single adapter implementation
serves all five supported coins.

Trust rules (deterministic, from evidence-contracts):
- Official project announcements are the original publisher → `high` reliability.
- independence_group is the project's registered domain.
- This is a best-effort source — failure never blocks the run.
- We only include items at or before analysis_as_of.
- Content is untrusted data: stored as quoted fact only.

Competition constraint: "每個幣需各自實作一套的來源一律 best-effort" — this adapter
uses a lookup table of known official feeds. If a coin has no configured feed,
the adapter returns a disclosed gap rather than failing the run.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from hoya_agent.adapters._assets import mentions
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.policies import SourceClass, independence_group, reliability_for
from hoya_agent.evidence.types import EvidenceDraft

try:
    import xml.etree.ElementTree as ET
except ImportError:  # pragma: no cover
    ET = None  # type: ignore[assignment,misc]

UTC = timezone.utc

# Known official project feeds — best-effort, not all coins have one.
# These are the actual official blog/announcement feeds for each project.
OFFICIAL_FEEDS: dict[str, dict[str, str]] = {
    "BTC": {
        "feed_url": "https://blog.bitcoin.org/feed.xml",
        "source_name": "Bitcoin.org Blog",
        "publisher_domain": "bitcoin.org",
    },
    "ETH": {
        "feed_url": "https://blog.ethereum.org/feed.xml",
        "source_name": "Ethereum Foundation Blog",
        "publisher_domain": "ethereum.org",
    },
    "SOL": {
        "feed_url": "https://solana.com/news/feed.xml",
        "source_name": "Solana News",
        "publisher_domain": "solana.com",
    },
    "BNB": {
        "feed_url": "https://www.bnbchain.org/en/blog/rss.xml",
        "source_name": "BNB Chain Blog",
        "publisher_domain": "bnbchain.org",
    },
    "XRP": {
        "feed_url": "https://ripple.com/insights/feed/",
        "source_name": "Ripple Insights",
        "publisher_domain": "ripple.com",
    },
}


def _parse_rfc822_or_iso(text: str) -> datetime | None:
    """Parse RFC 822 (RSS pubDate) or ISO 8601 (Atom) timestamps."""
    from email.utils import parsedate_to_datetime

    text = text.strip()
    if not text:
        return None
    # Try RFC 822 first (RSS pubDate format)
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (TypeError, ValueError):
        pass
    # Try ISO 8601 (Atom updated/published)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (TypeError, ValueError):
        pass
    return None


def _extract_entries(root: Any) -> list[dict[str, str | None]]:
    """Extract title, link, date from RSS <item> or Atom <entry> elements."""
    entries: list[dict[str, str | None]] = []

    # RSS format: <channel><item>
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        date_el = item.find("pubDate")
        entries.append({
            "title": title_el.text if title_el is not None else None,
            "link": link_el.text if link_el is not None else None,
            "date": date_el.text if date_el is not None else None,
        })

    # Atom format: <feed><entry>
    # Atom uses namespaces; try with and without
    atom_ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{atom_ns}entry"):
        title_el = entry.find(f"{atom_ns}title")
        link_el = entry.find(f"{atom_ns}link")
        updated_el = entry.find(f"{atom_ns}updated")
        published_el = entry.find(f"{atom_ns}published")
        link_href = link_el.get("href") if link_el is not None else None
        link_text = link_el.text if link_el is not None and link_el.text else link_href
        date_text = (
            (published_el.text if published_el is not None else None)
            or (updated_el.text if updated_el is not None else None)
        )
        entries.append({
            "title": title_el.text if title_el is not None else None,
            "link": link_text,
            "date": date_text,
        })

    # Also try Atom entries without namespace (some feeds omit it)
    if not entries:
        for entry in root.iter("entry"):
            title_el = entry.find("title")
            link_el = entry.find("link")
            updated_el = entry.find("updated")
            published_el = entry.find("published")
            link_href = link_el.get("href") if link_el is not None else None
            link_text = link_el.text if link_el is not None and link_el.text else link_href
            date_text = (
                (published_el.text if published_el is not None else None)
                or (updated_el.text if updated_el is not None else None)
            )
            entries.append({
                "title": title_el.text if title_el is not None else None,
                "link": link_text,
                "date": date_text,
            })

    return entries


def fetch_official_announcements(
    *,
    assets: Sequence[str],
    analysis_as_of: datetime,
    client: httpx.Client,
    lookback_days: int = 14,
    timeout: float = 45.0,
    feed_overrides: dict[str, dict[str, str]] | None = None,
) -> WorkerResult:
    """Fetch official project announcements for the given assets.

    Returns WorkerResult following the standard adapter pattern.
    Missing feeds for an asset produce a disclosed gap, not an error.
    """
    feeds = feed_overrides if feed_overrides is not None else OFFICIAL_FEEDS
    earliest = analysis_as_of - timedelta(days=lookback_days)
    fetched_at = datetime.now(UTC)
    drafts: list[EvidenceDraft] = []
    degradation: list[str] = []

    for asset in assets:
        asset_upper = asset.upper()
        feed_config = feeds.get(asset_upper)
        if not feed_config:
            degradation.append(
                f"無 {asset_upper} 官方公告 feed 設定（best-effort 來源，非阻塞）"
            )
            continue

        feed_url = feed_config["feed_url"]
        source_name = feed_config["source_name"]
        publisher_domain = feed_config["publisher_domain"]

        try:
            resp = client.get(feed_url, timeout=timeout)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)  # type: ignore[union-attr]
        except (httpx.HTTPError, ET.ParseError, Exception):  # noqa: BLE001
            degradation.append(
                f"{source_name} 取得失敗（best-effort 來源，非阻塞）"
            )
            continue

        entries = _extract_entries(root)
        asset_drafts = 0
        for entry in entries:
            title = (entry.get("title") or "").strip()
            if not title:
                continue

            date_str = entry.get("date")
            published: datetime | None = None
            if date_str:
                published = _parse_rfc822_or_iso(date_str)

            # Filter by time window if we have a publication date
            if published is not None:
                if published > analysis_as_of or published < earliest:
                    continue

            # Filter by asset relevance (title must mention the asset)
            if not mentions(asset_upper, title):
                continue

            link = entry.get("link") or feed_url
            group = independence_group(
                original_publisher=publisher_domain,
                source_url=link,
            )

            drafts.append(
                EvidenceDraft(
                    asset=asset_upper,
                    source_type="official",
                    source_name=source_name,
                    source_url=link,
                    published_at=published,
                    fetched_at=fetched_at,
                    query_or_parameters=f"official feed={feed_url}; credentials removed",
                    content_reference=f"{source_name} 官方公告"
                    f"（{published.date() if published else '日期未知'}）",
                    normalized_fact=title,
                    reliability=reliability_for(SourceClass.OFFICIAL_ANNOUNCEMENT),
                    independence_group=group,
                )
            )
            asset_drafts += 1

        if asset_drafts == 0:
            degradation.append(
                f"無 {asset_upper} 相關官方公告（在分析窗口 {lookback_days} 天內）"
            )

    if not drafts:
        status = "failed" if not degradation else "failed"
        return WorkerResult(status, [], degradation)

    return WorkerResult(
        "completed" if not degradation else "partial",
        drafts,
        degradation,
    )
