"""Alternative.me Fear & Greed adapter.

Whole-market sentiment (NOT a coin-specific signal). Produces one low-reliability
EvidenceDraft with asset=None; the report must not let it alone support a
single-coin conclusion. No API key. Coin-agnostic (one index for the whole market).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from hoya_agent.adapters._errors import category_note, classify_error
from hoya_agent.data.market_worker import WorkerResult
from hoya_agent.evidence.drafts import pending
from hoya_agent.evidence.policies import SourceClass

API_URL = "https://api.alternative.me/fng/"
UTC = timezone.utc


async def fetch_fear_greed(
    *, analysis_as_of: datetime, client: httpx.AsyncClient, limit: int = 7, timeout: float = 45.0
) -> WorkerResult:
    fetched_at = datetime.now(UTC)
    try:
        resp = await client.get(API_URL, params={"limit": limit}, timeout=timeout)
        resp.raise_for_status()
        rows = resp.json()["data"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return WorkerResult(
            "failed",
            [],
            [
                category_note(
                    "Fear & Greed fetch failed (optional source)", classify_error(exc)
                )
            ],
        )

    # Most recent reading at or before the frozen cutoff.
    best: tuple[datetime, str, str] | None = None
    for row in rows:
        try:
            published = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
            value = str(row["value"])
            classification = str(row["value_classification"])
        except (KeyError, ValueError, TypeError):
            continue
        if published > analysis_as_of:
            continue
        if best is None or published > best[0]:
            best = (published, value, classification)

    if best is None:
        return WorkerResult("failed", [], ["no Fear & Greed reading at or before analysis_as_of"])

    published, value, classification = best
    draft = pending(
        source_class=SourceClass.FEAR_GREED,
        provider_id="alternative.me",
        asset=None,  # whole-market context, not coin-specific
        source_type="social",
        source_name="Alternative.me Fear & Greed",
        source_url=API_URL,
        published_at=published,
        fetched_at=fetched_at,
        query_or_parameters=f"alternative.me /fng/?limit={limit}",
        content_reference=f"Fear & Greed Index = {value} ({classification}) on {published.date()} UTC",
        normalized_fact=f"全市場恐懼與貪婪指數為 {value}（{classification}），"
        f"截至 {published.date()} UTC；此為全市場情緒，非單一幣種指標。",
    )
    return WorkerResult("completed", [draft], [])
