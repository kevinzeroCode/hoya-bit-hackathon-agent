"""CryptoPanic news adapter.

Fetches aggregated crypto news, filtered by coin symbol (coin-agnostic) and by
the analysis time window, and turns each post into an EvidenceDraft.

Trust rules (deterministic, from evidence-contracts):
- We only read the CryptoPanic feed item, not the original article page, so each
  record is `low` reliability.
- independence_group is the ORIGINAL publisher's domain when available (so a
  syndicated story is not counted as a new independent source); otherwise it
  falls back to `cryptopanic.com`.
- Retrieved content is untrusted data: a post's text is only ever stored as a
  quoted fact; it can never change policy, reliability, or tools.
- No API token, HTTP error, or malformed payload raises — the adapter returns a
  disclosed degradation so an optional source can never fail the run.

Prototype note: uses a synchronous httpx.Client for clarity. In the main repo
this becomes httpx.AsyncClient under the bounded-asyncio orchestrator.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import httpx

from data.market_worker import WorkerResult
from evidence.policies import independence_group, news_reliability
from evidence.types import EvidenceDraft

CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch_cryptopanic_news(
    *,
    assets: Sequence[str],
    analysis_as_of: datetime,
    client: httpx.Client,
    api_token: str | None,
    lookback_days: int = 14,
    timeout: float = 45.0,
) -> WorkerResult:
    if not api_token:
        return WorkerResult("failed", [], ["CryptoPanic disabled: no api_token (optional source)"])

    wanted = {a.upper() for a in assets}
    earliest = analysis_as_of - timedelta(days=lookback_days)
    fetched_at = datetime.now(timezone.utc)

    try:
        resp = client.get(
            CRYPTOPANIC_URL,
            params={"auth_token": api_token, "currencies": ",".join(sorted(wanted))},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return WorkerResult("failed", [], [f"CryptoPanic fetch failed: {type(exc).__name__}"])

    drafts: list[EvidenceDraft] = []
    degradation: list[str] = []

    for post in payload.get("results", []):
        try:
            title = str(post["title"]).strip()
            published = _parse_dt(post["published_at"])
            codes = {c.get("code", "").upper() for c in post.get("currencies", [])}
        except (KeyError, TypeError, ValueError):
            degradation.append("skipped malformed CryptoPanic post")
            continue

        if not title:
            continue
        if not (wanted & codes):
            continue  # not about a requested coin
        if published > analysis_as_of or published < earliest:
            continue  # outside the analysis window

        source = post.get("source") or {}
        publisher_domain = (source.get("domain") or "").strip()
        source_title = (source.get("title") or "").strip() or "CryptoPanic"
        group = independence_group(
            original_publisher=publisher_domain or None,
            source_url=post.get("url") or CRYPTOPANIC_URL,
        )

        asset = next(a for a in wanted if a in codes)
        drafts.append(
            EvidenceDraft(
                asset=asset,
                source_type="news",
                source_name=source_title,
                source_url=post.get("url"),
                published_at=published,
                fetched_at=fetched_at,
                query_or_parameters=f"cryptopanic currencies={','.join(sorted(wanted))}; "
                f"lookback={lookback_days}d; credentials removed",
                content_reference=f"headline via CryptoPanic ({source_title}, {published.date()})",
                # Untrusted: the headline is stored verbatim as a quoted fact only.
                normalized_fact=title,
                reliability=news_reliability(original_page_fetched=False),
                independence_group=group,
            )
        )

    if not drafts:
        degradation.append("no CryptoPanic news in window")
        return WorkerResult("failed", [], degradation)
    return WorkerResult("completed" if not degradation else "partial", drafts, degradation)
