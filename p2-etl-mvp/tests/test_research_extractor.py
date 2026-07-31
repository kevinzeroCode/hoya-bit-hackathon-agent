"""Tests for structured LLM news extraction (clean -> semantic understanding).

The LLM output is structured (relevance + event type + multiple stanceless facts).
A fake LLM drives the tests with no network; swap for GPT mock / Bedrock at the
call site (LLMClient interface).
"""

from __future__ import annotations

from datetime import datetime, timezone

from data.market_worker import WorkerResult
from evidence.types import EvidenceDraft
from reasoning.llm_client import FakeLLMClient
from reasoning.research_extractor import NewsRecord, extract_news_facts

UTC = timezone.utc

_GOOD = (
    '{"relevant": true, "event_type": "etf_flow", '
    '"facts": ["現貨 BTC ETF 出現最大單日淨流入", "發行商申報文件為數據來源"]}'
)


def _record(title: str = "Bitcoin ETF sees record inflows", body: str = "<p>Spot BTC ETFs...</p>") -> NewsRecord:
    return NewsRecord(
        asset="BTC",
        title=title,
        body=body,
        source_name="CoinDesk",
        publisher_domain="coindesk.com",
        source_url="https://cryptopanic.com/news/1",
        published_at=datetime(2026, 5, 30, 12, 0, tzinfo=UTC),
    )


def test_extracts_multiple_facts_into_news_drafts():
    result = extract_news_facts([_record()], llm=FakeLLMClient(_GOOD))
    assert isinstance(result, WorkerResult)
    assert result.status == "completed"
    assert len(result.drafts) == 2  # one draft per extracted fact
    for d in result.drafts:
        assert isinstance(d, EvidenceDraft)
        assert d.source_type == "news"
        assert d.reliability == "low"          # aggregator feed, static policy
        assert d.independence_group == "coindesk.com"
        assert "etf_flow" in d.content_reference  # event type recorded
    facts = {d.normalized_fact for d in result.drafts}
    assert "現貨 BTC ETF 出現最大單日淨流入" in facts


def test_irrelevant_article_is_filtered_out():
    llm = FakeLLMClient('{"relevant": false, "event_type": "other", "facts": []}')
    result = extract_news_facts([_record()], llm=llm)
    assert result.drafts == []
    assert result.degradation  # disclosed why it was dropped


def test_body_is_cleaned_before_the_llm_sees_it():
    captured: dict[str, str] = {}

    def fake(system: str, user: str) -> str:
        captured["user"] = user
        return _GOOD

    extract_news_facts(
        [_record(body="<p>Spot <b>BTC</b> ETFs&nbsp;recorded inflows.</p>")],
        llm=FakeLLMClient(fake),
    )
    assert "<p>" not in captured["user"] and "<b>" not in captured["user"]  # HTML stripped
    assert "&nbsp;" not in captured["user"]  # entities unescaped/normalized


def test_malformed_output_is_degradation():
    result = extract_news_facts([_record()], llm=FakeLLMClient("not json"))
    assert result.drafts == []
    assert result.degradation


def test_relevant_but_no_facts_is_degradation():
    llm = FakeLLMClient('{"relevant": true, "event_type": "macro", "facts": []}')
    result = extract_news_facts([_record()], llm=llm)
    assert result.drafts == []
    assert result.degradation


def test_no_records_returns_failed():
    result = extract_news_facts([], llm=FakeLLMClient(_GOOD))
    assert result.status == "failed"
