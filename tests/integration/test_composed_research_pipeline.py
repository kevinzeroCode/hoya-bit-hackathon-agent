"""The composition root wires a real research branch (S6 exit criteria).

Covers what only the composed pipeline can show: the designated baseline research
source produces schema-valid Evidence, an optional source failing does not fail
the run, a repost does not become a second independent group, a missing source is
a disclosed gap rather than an invented fact, and the fixed skip order now has the
source lists it needs to fire in a real run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from hoya_agent.application import (
    BASELINE_RESEARCH_OPERATIONS,
    COUNTER_SIGNAL_OPERATIONS,
    OPTIONAL_CONTEXT_OPERATIONS,
    NewsFeed,
    build_research_pipeline,
    build_research_tool_registry,
)
from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    Reliability,
    ResearchPlan,
    RunContext,
    RunMode,
    SourceType,
)
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline, PipelineOutcome
from hoya_agent.reasoning.arbiter_output import ArbiterOutput
from hoya_agent.reasoning.planner import default_plan_payload
from hoya_agent.reasoning.research_extractor import ExtractedFact, ResearchExtraction

pytestmark = pytest.mark.integration

NOW = datetime(2026, 6, 3, tzinfo=UTC)
CSV_AS_OF = date(2026, 5, 31)

FEEDS = (
    NewsFeed(
        feed_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
        source_name="CoinDesk",
        publisher_domain="coindesk.com",
    ),
)

_FEED_XML = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    "<item><title>Bitcoin spot ETFs post weekly outflows</title>"
    "<link>https://www.coindesk.com/markets/2026/06/02/story</link>"
    "<pubDate>Tue, 02 Jun 2026 12:00:00 +0000</pubDate></item>"
    "</channel></rss>"
)


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


def _context(assets=(Asset.BTC,), deadline_seconds: int = 900) -> RunContext:
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=list(assets),
        requested_at=NOW,
        analysis_as_of=NOW,
        deadline_seconds=deadline_seconds,
        run_mode=RunMode.rehearsal,
        run_id="run_20260603_000000_cr01",
    )
    return build_run_context(request, Clock())


def _routing_client(*, fear_greed: httpx.Response | Exception | None = None) -> httpx.AsyncClient:
    """One client for every research host, routed by URL like the live client is."""

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if "alternative.me" in host:
            if isinstance(fear_greed, Exception):
                raise fear_greed
            return fear_greed or httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "timestamp": "1780272000",
                            "value": "42",
                            "value_classification": "Fear",
                        }
                    ]
                },
            )
        if "coindesk.com" in host:
            return httpx.Response(200, text=_FEED_XML)
        # Official project feeds and CryptoPanic are not configured in this run.
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _registry(client: httpx.AsyncClient, feeds=FEEDS):
    """Registry with the retry backoff collapsed: tests never spend real seconds."""
    return build_research_tool_registry(
        news_feeds=feeds, client=client, retry_backoff_seconds=0.0
    )


async def _extraction() -> ResearchExtraction:
    return ResearchExtraction(
        drafts=[
            ExtractedFact(
                record_id=record_id,
                normalized_fact=fact,
                event_type="etf_flow",
                asset=Asset.BTC,
            )
            for record_id, fact in await _expected_records()
        ]
    )


async def _expected_records() -> list[tuple[str, str]]:
    # The record id is derived deterministically from source url + headline, so the
    # extraction fixture can cite it exactly the way a model must.
    from hoya_agent.adapters.port_adapters import _to_raw_record
    from hoya_agent.adapters.rss import fetch_rss_news

    result = await fetch_rss_news(
        "BTC",
        analysis_as_of=NOW,
        client=_routing_client(),
        feed_url=FEEDS[0].feed_url,
        source_name=FEEDS[0].source_name,
        publisher_domain=FEEDS[0].publisher_domain,
    )
    record = _to_raw_record(result.drafts[0], operation="fetch_rss_news")
    return [
        (record.record_id, "現貨 ETF 於該週出現淨流出。"),
        (record.record_id, "同期資金流向轉為負值。"),
    ]


class ScriptedLLM:
    """Dispatches by operation: a valid plan for the Planner, facts for extraction.

    A single queue would be wrong here — the Planner and the extraction call are two
    different schemas, and feeding the plan call an extraction object is how the
    frozen Planner ends up on its deterministic fallback.
    """

    def __init__(self, *, extraction: ResearchExtraction, operations: tuple[str, ...]) -> None:
        self._extraction = extraction
        self._operations = operations
        self.calls: list[str] = []

    async def converse_structured(self, *, operation: str, **kwargs: object):
        self.calls.append(operation)
        if operation == "planner":
            return ResearchPlan.model_validate(
                default_plan_payload(
                    assets=["BTC"],
                    allowed_operations=self._operations,
                    lookback_days=14,
                    reason="test plan",
                )
            )
        if operation == "research_extraction":
            return self._extraction
        if operation == "arbiter":
            # The composition root wires the Arbiter with `ArbiterOutput`, so the
            # double has to answer in that schema too.
            return ArbiterOutput.model_validate(
                {
                    "direct_answer": "以現有證據描述近期市場狀況。",
                    "market_context": {"summary": "BTC 市場狀況。", "time_range": None},
                    "claims": [
                        {
                            "claim_id": "cl_001",
                            "claim_type": "fact",
                            "assets": ["BTC"],
                            "text": "BTC 的 14 日報酬為 -4.88%。",
                            "based_on_claim_ids": [],
                            "confidence": "medium",
                        }
                    ],
                    "claim_evidence_links": [
                        {
                            "claim_id": "cl_001",
                            "evidence_id": "ev_001",
                            "stance": "supports",
                            "reason": "deterministic 市場計算。",
                        }
                    ],
                    "confidence": "medium",
                    "confidence_rationale": "單一獨立市場來源支持。",
                }
            )
        raise AssertionError(f"unexpected LLM operation: {operation}")


async def _run(
    *,
    with_llm: bool = True,
    fear_greed: httpx.Response | Exception | None = None,
    deadline_seconds: int = 900,
    assets=(Asset.BTC,),
) -> PipelineOutcome:
    client = _routing_client(fear_greed=fear_greed)
    registry = _registry(client)
    llm = (
        ScriptedLLM(extraction=await _extraction(), operations=tuple(registry.operations()))
        if with_llm
        else None
    )
    pipeline = build_research_pipeline(
        clock=Clock(),
        llm=llm,
        tool_registry=registry,
        market_pipeline=OrganizerCsvPipeline(analysis_date=CSV_AS_OF),
    )
    return await pipeline.execute(
        _context(assets=assets, deadline_seconds=deadline_seconds), lambda event: None
    )


async def test_baseline_research_source_produces_schema_valid_evidence() -> None:
    outcome = await _run()

    news = [item for item in outcome.ledger.items if item.source_type is SourceType.news]
    assert news, "the designated baseline research source must reach the ledger"
    for item in news:
        assert item.source_name == "CoinDesk"
        assert item.independence_group == "coindesk.com"
        assert item.reliability is Reliability.low  # feed item, original page not fetched
        assert item.content_hash and item.query_or_parameters and item.content_reference


async def test_market_and_research_evidence_share_one_ledger() -> None:
    outcome = await _run()

    source_types = {item.source_type for item in outcome.ledger.items}
    assert SourceType.market in source_types
    assert SourceType.news in source_types


async def test_optional_source_failure_does_not_fail_the_run() -> None:
    outcome = await _run(
        fear_greed=httpx.ReadTimeout("fear & greed timed out"),
    )

    assert outcome.ledger.items, "baseline evidence must survive an optional-source failure"
    assert any(item.source_type is SourceType.news for item in outcome.ledger.items)
    assert any("fetch_fear_greed" in note for note in outcome.degradation_notes)


async def test_reposted_headline_is_not_counted_as_a_second_group() -> None:
    """Two outlets carrying byte-identical wording collapse to one Evidence item."""
    duplicate_feeds = (
        FEEDS[0],
        NewsFeed(
            feed_url="https://decrypt.co/feed",
            source_name="Decrypt",
            publisher_domain="decrypt.co",
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "alternative.me" in request.url.host:
            return httpx.Response(404)
        if "coindesk.com" in request.url.host or "decrypt.co" in request.url.host:
            return httpx.Response(200, text=_FEED_XML)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    registry = _registry(client, duplicate_feeds)
    from hoya_agent.adapters.port_adapters import _to_raw_record
    from hoya_agent.adapters.rss import fetch_rss_news

    feed_result = await fetch_rss_news(
        "BTC",
        analysis_as_of=NOW,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        feed_url=duplicate_feeds[0].feed_url,
        source_name=duplicate_feeds[0].source_name,
        publisher_domain=duplicate_feeds[0].publisher_domain,
    )
    record_id = _to_raw_record(feed_result.drafts[0], operation="fetch_rss_news").record_id
    extraction = ResearchExtraction(
        drafts=[
            ExtractedFact(
                record_id=record_id,
                normalized_fact="現貨 ETF 於該週出現淨流出。",
                event_type="etf_flow",
                asset=Asset.BTC,
            )
        ]
    )

    pipeline = build_research_pipeline(
        clock=Clock(),
        llm=ScriptedLLM(extraction=extraction, operations=tuple(registry.operations())),
        tool_registry=registry,
        market_pipeline=OrganizerCsvPipeline(analysis_date=CSV_AS_OF),
    )
    outcome = await pipeline.execute(_context(), lambda event: None)

    facts = [item.normalized_fact for item in outcome.ledger.items]
    assert facts.count("現貨 ETF 於該週出現淨流出。") == 1


async def test_missing_source_is_a_disclosed_gap_not_an_invented_fact() -> None:
    """CryptoPanic without a token must degrade visibly, never fabricate."""
    outcome = await _run()

    assert any("fetch_cryptopanic_news" in note for note in outcome.degradation_notes)
    assert all("CryptoPanic" != item.source_name for item in outcome.ledger.items)


async def test_skip_order_source_lists_are_declared_by_the_composition_root() -> None:
    registry = _registry(_routing_client())
    pipeline = build_research_pipeline(
        clock=Clock(), tool_registry=registry, market_pipeline=OrganizerCsvPipeline()
    )

    assert pipeline._optional_operations == frozenset(OPTIONAL_CONTEXT_OPERATIONS)
    assert pipeline._counter_signal_operations == frozenset(COUNTER_SIGNAL_OPERATIONS)
    # Baseline research must never be classified as optional work.
    for operation in BASELINE_RESEARCH_OPERATIONS:
        assert operation not in pipeline._optional_operations
        assert operation not in pipeline._counter_signal_operations
    assert set(registry.operations()) >= set(BASELINE_RESEARCH_OPERATIONS)


async def test_a_transient_baseline_failure_recovers_within_the_run() -> None:
    """One flaky first attempt must not cost the judged run its baseline evidence."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "coindesk.com" in request.url.host:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ReadTimeout("transient")
            return httpx.Response(200, text=_FEED_XML)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    registry = _registry(client)
    pipeline = build_research_pipeline(
        clock=Clock(),
        llm=ScriptedLLM(
            extraction=await _extraction(), operations=tuple(registry.operations())
        ),
        tool_registry=registry,
        market_pipeline=OrganizerCsvPipeline(analysis_date=CSV_AS_OF),
    )
    outcome = await pipeline.execute(_context(), lambda event: None)

    assert attempts["count"] == 2, "exactly one retry"
    assert any(item.source_type is SourceType.news for item in outcome.ledger.items)
    assert any("重試" in note for note in outcome.degradation_notes), (
        "a recovered source must still be disclosed as flaky"
    )


async def test_a_non_allowlisted_research_host_is_rejected_before_any_call() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        build_research_tool_registry(
            news_feeds=(
                NewsFeed(
                    feed_url="https://evil.example.com/feed",
                    source_name="Evil",
                    publisher_domain="evil.example.com",
                ),
            )
        )


async def test_research_runs_without_an_llm_and_discloses_the_substitution() -> None:
    """No model configured: fetches still run, extraction is honestly absent."""
    outcome = await _run(with_llm=False)

    assert outcome.ledger.items, "market evidence must still ship"
    assert any("決定論預設計畫" in note for note in outcome.degradation_notes)
