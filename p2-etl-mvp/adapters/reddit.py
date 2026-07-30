"""Reddit r/CryptoCurrency adapter — community/social source.

Public JSON, no API key. Coin-agnostic: reads a general crypto subreddit and
keeps only posts that mention the requested asset. Each post is low-reliability
social/community data (a discussion title, not a verified fact); the title is
stored verbatim as untrusted quoted data. Optional / non-blocking.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from adapters._assets import mentions
from data.market_worker import WorkerResult
from evidence.policies import SourceClass, independence_group, reliability_for
from evidence.types import EvidenceDraft

UTC = timezone.utc
_UA = {"User-Agent": "hoya-market-agent/0.1"}


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
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": limit},
            headers=_UA,
            timeout=timeout,
        )
        resp.raise_for_status()
        children = resp.json()["data"]["children"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return WorkerResult("failed", [], ["Reddit fetch failed (optional source)"])

    drafts: list[EvidenceDraft] = []
    for child in children:
        try:
            post = child["data"]
            title = str(post["title"]).strip()
            created = datetime.fromtimestamp(int(post["created_utc"]), tz=UTC)
        except (KeyError, ValueError, TypeError):
            continue
        if not title or not mentions(asset, title) or created > analysis_as_of:
            continue
        url = "https://www.reddit.com" + str(post.get("permalink", ""))
        drafts.append(
            EvidenceDraft(
                asset=asset,
                source_type="social",
                source_name=f"Reddit r/{subreddit}",
                source_url=url,
                published_at=created,
                fetched_at=fetched_at,
                query_or_parameters=f"reddit r/{subreddit}/hot?limit={limit}",
                content_reference=f"Reddit 社群討論標題（{created.date()}）",
                normalized_fact=title,  # community discussion, untrusted quoted data
                reliability=reliability_for(SourceClass.SOCIAL),
                independence_group=independence_group(source_url=url),
            )
        )

    if not drafts:
        return WorkerResult("failed", [], ["no relevant Reddit posts in window"])
    return WorkerResult("completed", drafts, [])
