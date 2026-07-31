"""Reddit r/CryptoCurrency adapter — community/social source (Atom feed).

Reddit's public JSON endpoints now 403 unauthenticated / datacenter traffic, but
its Atom RSS feed (`…/.rss`) is still served, so we read that. Coin-agnostic:
reads a general crypto subreddit and keeps only posts mentioning the requested
asset. Each post is low-reliability social data (a discussion title, not a
verified fact); the title is stored verbatim as untrusted quoted data.
Optional / non-blocking (Reddit rate-limits: one feed per run).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from adapters._assets import mentions
from data.market_worker import WorkerResult
from evidence.policies import SourceClass, independence_group, reliability_for
from evidence.types import EvidenceDraft

UTC = timezone.utc
_ATOM = "{http://www.w3.org/2005/Atom}"
_UA = {"User-Agent": "Mozilla/5.0 (research; hoya-market-agent/0.1)"}


def _parse_dt(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def fetch_reddit_posts(
    asset: str,
    *,
    analysis_as_of: datetime,
    client: httpx.Client,
    subreddit: str = "CryptoCurrency",
    limit: int = 25,
    timeout: float = 45.0,
) -> WorkerResult:
    mentions(asset, "")  # validates the asset (raises on unsupported)
    fetched_at = datetime.now(UTC)
    try:
        resp = client.get(
            f"https://www.reddit.com/r/{subreddit}/hot/.rss",
            params={"limit": limit},
            headers=_UA,
            timeout=timeout,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except (httpx.HTTPError, ET.ParseError):
        return WorkerResult("failed", [], ["Reddit fetch failed (optional source)"])

    drafts: list[EvidenceDraft] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = (entry.findtext(f"{_ATOM}title") or "").strip()
        created = _parse_dt(
            entry.findtext(f"{_ATOM}updated") or entry.findtext(f"{_ATOM}published")
        )
        if not title or created is None:
            continue
        if not mentions(asset, title) or created > analysis_as_of:
            continue
        link_el = entry.find(f"{_ATOM}link")
        url = (link_el.get("href") if link_el is not None else "") or f"https://www.reddit.com/r/{subreddit}"
        author = (entry.findtext(f"{_ATOM}author/{_ATOM}name") or "unknown").strip()
        drafts.append(
            EvidenceDraft(
                asset=asset,
                source_type="social",
                source_name=f"Reddit r/{subreddit}",
                source_url=url,
                published_at=created,
                fetched_at=fetched_at,
                query_or_parameters=f"reddit r/{subreddit}/hot .rss?limit={limit}",
                content_reference=f"Reddit 社群討論標題（{author}，{created.date()}）",
                normalized_fact=title,  # community discussion, untrusted quoted data
                reliability=reliability_for(SourceClass.SOCIAL),
                independence_group=independence_group(source_url=url),
            )
        )

    if not drafts:
        return WorkerResult("failed", [], ["no relevant Reddit posts in window"])
    return WorkerResult("completed", drafts, [])
