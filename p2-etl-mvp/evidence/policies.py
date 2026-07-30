"""Deterministic evidence policies: reliability, independence group, confidence caps.

All static and rule-based — no LLM ever assigns or upgrades any of these.
Mirrors evidence-contracts.md sections 4 (reliability), 5 (independence), and
10 (confidence caps).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal
from urllib.parse import urlparse

Reliability = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]

ORGANIZER_GROUP = "organizer-public-market-data"


class SourceClass(str, Enum):
    """Static source classes that map to a fixed reliability."""

    ORGANIZER_CSV = "organizer_csv"
    EXCHANGE_MARKET_API = "exchange_market_api"
    DETERMINISTIC_CALC = "deterministic_calc"
    OFFICIAL_ANNOUNCEMENT = "official_announcement"
    MARKET_AGGREGATOR = "market_aggregator"  # CoinGecko / CryptoCompare snapshots
    ORIGINAL_NEWS_PAGE = "original_news_page"
    NEWS_AGGREGATOR = "news_aggregator"
    FEAR_GREED = "fear_greed"
    SOCIAL = "social"
    SECONDARY_COMMENTARY = "secondary_commentary"


_RELIABILITY: dict[SourceClass, Reliability] = {
    SourceClass.ORGANIZER_CSV: "high",
    SourceClass.EXCHANGE_MARKET_API: "high",
    SourceClass.DETERMINISTIC_CALC: "high",
    SourceClass.OFFICIAL_ANNOUNCEMENT: "high",
    SourceClass.MARKET_AGGREGATOR: "medium",  # aggregated snapshot, not first-hand exchange
    SourceClass.ORIGINAL_NEWS_PAGE: "medium",
    SourceClass.NEWS_AGGREGATOR: "low",
    SourceClass.FEAR_GREED: "low",
    SourceClass.SOCIAL: "low",
    SourceClass.SECONDARY_COMMENTARY: "low",
}


def reliability_for(source_class: SourceClass) -> Reliability:
    return _RELIABILITY[source_class]


def news_reliability(*, original_page_fetched: bool) -> Reliability:
    """A news item is `medium` only when its original page was actually fetched;
    an aggregator/feed record on its own stays `low`."""
    return "medium" if original_page_fetched else "low"


def registered_domain(url: str) -> str:
    """Registered domain (eTLD+1 heuristic), lowercased, without `www`.

    MVP heuristic: strip creds/port, drop a leading `www.`, keep the last two
    dotted labels. Good enough for .com/.me/.io crypto sources; multi-part TLDs
    like co.uk are out of MVP scope.
    """
    u = url.strip().lower()
    if "://" not in u:
        u = "//" + u
    host = urlparse(u).netloc
    if not host:
        raise ValueError(f"no host in url: {url!r}")
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    labels = [x for x in host.split(".") if x]
    if not labels:
        raise ValueError(f"no host in url: {url!r}")
    return ".".join(labels[-2:]) if len(labels) >= 2 else labels[0]


def independence_group(
    *,
    original_publisher: str | None = None,
    source_url: str | None = None,
    provider_id: str | None = None,
) -> str:
    """First applicable: original publisher, else original URL's registered domain,
    else configured provider id. A repost shares its original publisher's group."""
    if original_publisher:
        p = original_publisher.strip()
        return registered_domain(p) if "." in p else p.lower()
    if source_url:
        return registered_domain(source_url)
    if provider_id:
        return provider_id.strip().lower()
    raise ValueError("independence_group needs at least one identifier")


@dataclass(frozen=True)
class ConfidenceSignals:
    supporting_groups: int  # distinct independence groups supporting the claim
    max_supporting_reliability: Reliability  # highest reliability among supporters
    has_material_conflict: bool = False
    only_stale_cache: bool = False
    insufficient_data: bool = False


def max_confidence(signals: ConfidenceSignals) -> Confidence:
    """The highest confidence a claim may be assigned given deterministic caps.

    This is a ceiling, not the final confidence — the Arbiter may go lower.
    """
    if (
        signals.insufficient_data
        or signals.has_material_conflict
        or signals.max_supporting_reliability == "low"
        or signals.only_stale_cache
    ):
        return "low"
    if signals.supporting_groups < 2:
        return "medium"
    return "high"
