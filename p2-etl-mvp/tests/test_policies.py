"""Tests for deterministic evidence policies: reliability, independence, caps.

All rules are static (no LLM). See CLAUDE.md and evidence-contracts.md sections 4,
5, and 10.
"""

from __future__ import annotations

import pytest
from evidence.policies import (
    ORGANIZER_GROUP,
    ConfidenceSignals,
    SourceClass,
    independence_group,
    max_confidence,
    news_reliability,
    registered_domain,
    reliability_for,
)

# --- static reliability table ---------------------------------------------


@pytest.mark.parametrize(
    "source_class, expected",
    [
        (SourceClass.ORGANIZER_CSV, "high"),
        (SourceClass.EXCHANGE_MARKET_API, "high"),
        (SourceClass.DETERMINISTIC_CALC, "high"),
        (SourceClass.OFFICIAL_ANNOUNCEMENT, "high"),
        (SourceClass.MARKET_AGGREGATOR, "medium"),
        (SourceClass.ORIGINAL_NEWS_PAGE, "medium"),
        (SourceClass.NEWS_AGGREGATOR, "low"),
        (SourceClass.FEAR_GREED, "low"),
        (SourceClass.SOCIAL, "low"),
        (SourceClass.SECONDARY_COMMENTARY, "low"),
    ],
)
def test_reliability_table(source_class, expected):
    assert reliability_for(source_class) == expected


def test_news_reliability_depends_on_original_fetch():
    # Aggregator/feed item stays low unless the original page is actually fetched.
    assert news_reliability(original_page_fetched=True) == "medium"
    assert news_reliability(original_page_fetched=False) == "low"


# --- independence group ----------------------------------------------------


def test_registered_domain_strips_subdomain_and_www():
    assert registered_domain("https://api.binance.com/api/v3/klines") == "binance.com"
    assert registered_domain("https://www.coindesk.com/markets/x") == "coindesk.com"
    assert registered_domain("alternative.me") == "alternative.me"


def test_independence_group_prefers_original_publisher():
    assert (
        independence_group(
            original_publisher="coindesk.com",
            source_url="https://cryptopanic.com/news/1",
        )
        == "coindesk.com"
    )


def test_independence_group_falls_back_to_url():
    assert independence_group(source_url="https://cryptopanic.com/news/1") == "cryptopanic.com"


def test_independence_group_uses_provider_id_when_no_url():
    assert independence_group(provider_id=ORGANIZER_GROUP) == ORGANIZER_GROUP


def test_repost_shares_original_publisher_group():
    # A repost that names its original publisher groups with that publisher.
    assert (
        independence_group(
            original_publisher="theblock.co",
            source_url="https://some-aggregator.com/x",
        )
        == "theblock.co"
    )


def test_independence_group_requires_an_identifier():
    with pytest.raises(ValueError):
        independence_group()


# --- confidence caps -------------------------------------------------------


def test_insufficient_data_caps_low():
    s = ConfidenceSignals(supporting_groups=3, max_supporting_reliability="high", insufficient_data=True)
    assert max_confidence(s) == "low"


def test_material_conflict_caps_low():
    s = ConfidenceSignals(supporting_groups=2, max_supporting_reliability="high", has_material_conflict=True)
    assert max_confidence(s) == "low"


def test_only_low_evidence_caps_low():
    assert max_confidence(ConfidenceSignals(supporting_groups=3, max_supporting_reliability="low")) == "low"


def test_only_stale_cache_caps_low():
    s = ConfidenceSignals(supporting_groups=2, max_supporting_reliability="high", only_stale_cache=True)
    assert max_confidence(s) == "low"


def test_single_independence_group_caps_medium():
    assert max_confidence(ConfidenceSignals(supporting_groups=1, max_supporting_reliability="high")) == "medium"


def test_two_groups_allows_high():
    assert max_confidence(ConfidenceSignals(supporting_groups=2, max_supporting_reliability="medium")) == "high"
