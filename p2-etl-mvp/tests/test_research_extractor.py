"""Tests for the provider-agnostic news fact extractor.

The extractor depends only on the LLMClient interface, so a fake LLM drives the
tests with no network. Swapping the fake for a GPT mock (now) or a Bedrock
client (production) is a one-line change at the call site.
"""

from __future__ import annotations

from datetime import datetime, timezone

from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft
from reasoning.llm_client import FakeLLMClient
from reasoning.research_extractor import NewsRecord, extract_news_facts

AS_OF = datetime(2026, 5, 31, tzinfo=timezone.utc)


def _record(title: str = "Bitcoin ETF sees record inflows") -> NewsRecord:
    return NewsRecord(
        asset="BTC",
        title=title,
        body="A long article body about BTC ETF flows...",
        source_name="CoinDesk",
        publisher_domain="coindesk.com",
        source_url="https://cryptopanic.com/news/1",
        published_at=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
    )


def test_extracts_fact_into_low_reliability_news_draft():
    llm = FakeLLMClient('{"fact": "BTC spot ETFs recorded their largest single-day inflow."}')
    result = extract_news_facts([_record()], llm=llm)
    assert isinstance(result, WorkerResult)
    assert result.status == "completed"
    assert len(result.drafts) == 1
    d = result.drafts[0]
    assert isinstance(d, EvidenceDraft)
    assert d.source_type == "news"
    assert d.reliability == "low"  # aggregator feed, static policy — not from the LLM
    assert d.asset == "BTC"
    assert d.independence_group == "coindesk.com"
    assert d.normalized_fact == "BTC spot ETFs recorded their largest single-day inflow."
    assert d.published_at is not None
    assert d.fetched_at.tzinfo is not None
    assert "research-extraction-v1" in d.query_or_parameters  # prompt version, not full text


def test_malformed_llm_output_is_degradation_not_crash():
    llm = FakeLLMClient("this is not json")
    result = extract_news_facts([_record()], llm=llm)
    assert result.drafts == []
    assert result.degradation


def test_empty_fact_is_skipped():
    llm = FakeLLMClient('{"fact": "   "}')
    result = extract_news_facts([_record()], llm=llm)
    assert result.drafts == []
    assert result.degradation


def test_multiple_records_each_produce_a_draft():
    llm = FakeLLMClient('{"fact": "Some factual statement about BTC."}')
    result = extract_news_facts([_record("A"), _record("B")], llm=llm)
    assert len(result.drafts) == 2
    assert all(d.reliability == "low" and d.source_type == "news" for d in result.drafts)


def test_no_records_returns_failed_without_calling_conclusions():
    llm = FakeLLMClient('{"fact": "unused"}')
    result = extract_news_facts([], llm=llm)
    assert result.status == "failed"
    assert result.drafts == []
