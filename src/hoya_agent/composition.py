"""Composition root: wire concrete providers into a runnable analysis service.

This is the ONE module allowed to import concrete adapters (Bedrock, live
sources) and hand them to the orchestration layer — orchestration/, evidence/
and ui/ stay provider-free by construction. Everything is injected, so tests
pass a fake LLM and never touch the network.

Two run shapes:
- `build_live_pipeline(...)` with a real BedrockLLMClient → live Binance + Fear &
  Greed evidence, then the Arbiter reasons over it into an AnalysisResult.
- No credentials → the caller uses the deterministic live-data pipeline instead;
  and even here, any Arbiter/mapping failure degrades to the insufficient-data
  report (never a crash), because the mapper returns None on any invalid output.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings
from hoya_agent.adapters.live_sources import binance_bar_loader, fear_greed_drafts
from hoya_agent.adapters.port_adapters import RssResearchAdapter
from hoya_agent.models import Asset, ResearchPlan, ResearchStep, SourceStatus, SourceType
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, OrganizerCsvPipeline
from hoya_agent.ports import Clock, StaticToolRegistry
from hoya_agent.reasoning.arbiter import Arbiter, ArbiterSettings
from hoya_agent.reasoning.mapping import build_analysis_result
from hoya_agent.reasoning.research_agent import ResearchAgent
from hoya_agent.reasoning.schemas import ArbiterGeneration, DraftBatch

_BINANCE_URL = "https://api.binance.com/api/v3/klines"
_COINDESK_RSS = "https://www.coindesk.com/arc/outboundfeeds/rss/"


def build_bedrock_llm(
    *,
    region: str,
    primary_model_id: str,
    fallback_model_id: str | None = None,
    call_timeout_seconds: float = 45.0,
    client: Any = None,
) -> BedrockLLMClient:
    """Construct the Bedrock Converse client. `client=None` uses the standard AWS
    credential chain (EC2 IAM instance role, or local env) — no key in code."""
    settings = BedrockSettings(
        region=region,
        primary_model_id=primary_model_id,
        fallback_model_id=fallback_model_id,
        call_timeout_seconds=call_timeout_seconds,
    )
    return BedrockLLMClient(settings=settings, client=client)


@dataclass
class MappingArbiter:
    """Adapts the real Arbiter (lax generation output) to the pipeline's contract.

    Runs the frozen S7 Arbiter, then maps its `ArbiterGeneration` onto a strict
    `AnalysisResult`. Returns `None` on any mapping/validation failure so the
    pipeline (and app) degrade to the deterministic insufficient-data report.
    """

    inner: Arbiter

    @property
    def settings(self) -> Any:
        return self.inner.settings

    async def run(
        self,
        *,
        request: Any,
        ledger: Any,
        indicators: Any = (),
        deadline: float,
        degradation_notes: Any = (),
    ) -> tuple[Any, list[str]]:
        generation, notes = await self.inner.run(
            request=request,
            ledger=ledger,
            indicators=indicators,
            deadline=deadline,
            degradation_notes=degradation_notes,
        )
        notes = list(notes)
        try:
            result = build_analysis_result(generation, request=request, ledger=ledger)
        except Exception as exc:  # noqa: BLE001 - surface why the mapping failed
            result = None
            notes.append(
                f"Arbiter 輸出無法映射為有效 AnalysisResult({type(exc).__name__}):"
                f"{str(exc)[:400]}"
            )
        return result, notes


_NEWS_OPERATIONS = ("baseline_news", "question_news")

# Full names improve Google News recall (feeds say "Bitcoin", not "BTC") and let
# the adapter's relevance filter match.
_ASSET_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BNB",
    "XRP": "XRP Ripple",
}


class _BaselinePlanner:
    """Deterministic planner: plan the fixed baseline feed + a question-driven search.

    No LLM call for planning — cheaper and more robust, and the tool allowlist is
    fixed. `baseline_news` is a first-party outlet (CoinDesk); `question_news`
    searches Google News with the run's question, so news adapts to the question
    without a fragile LLM planner.
    """

    def __init__(self, lookback_days: int = 30) -> None:
        self._lookback = lookback_days

    async def run(self, *, request: Any, deadline: float) -> tuple[ResearchPlan, list[str]]:
        del deadline
        return (
            ResearchPlan(
                assets=[Asset(a) for a in request.assets],
                question_summary=getattr(request, "question", "") or "市場研究",
                lookback_days=self._lookback,
                required_evidence_types=[SourceType.news],
                planned_steps=[
                    ResearchStep(
                        step_id="baseline_01",
                        tool_operation="baseline_news",
                        rationale="first-party outlet (CoinDesk) baseline",
                    ),
                    ResearchStep(
                        step_id="baseline_02",
                        tool_operation="question_news",
                        rationale="question-driven Google News search",
                    ),
                ],
            ),
            [],
        )


def _google_news_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


_UA = "Mozilla/5.0 (compatible; HoyaMarketAgent/1.0)"


async def _fetch_rss(
    *, feed_url: str, source_name: str, publisher_domain: str,
    operation: str, analysis_as_of: datetime, assets: list[str], lookback: int,
) -> Any:
    """Fetch one RSS feed → RawSourceRecord[]; own AsyncClient per call, closed cleanly.

    A browser-like User-Agent is required for Google News, which serves an empty
    response to the default python-httpx agent.
    """
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30.0, headers={"User-Agent": _UA}
    ) as client:
        rss = RssResearchAdapter(
            feed_url=feed_url, source_name=source_name,
            publisher_domain=publisher_domain, client=client,
        )
        result = await rss.fetch(
            operation=operation, lookback_days=lookback,
            analysis_as_of=analysis_as_of, assets=assets,
        )
    if result.status is not SourceStatus.ok or not result.data:
        raise RuntimeError(result.error_category or f"{source_name} returned no records")
    return result.data


def _news_tool_registry(
    analysis_as_of: datetime, assets: Sequence[Asset], question: str
) -> StaticToolRegistry:
    """Two independent news ops: fixed first-party CoinDesk + question-driven Google
    News search. Each op raises on empty so the Research Agent discloses the gap
    rather than silently dropping the source; two sources add resilience."""
    asset_values = [a.value for a in assets]
    # Coin-targeted English query only. Empirically, appending the question (Chinese
    # or extra keywords) collapses Google News recall to ~0 usable items — the
    # rss.py filter requires the coin name in the title, which narrow searches miss.
    # The question drives the Arbiter's answer; the search stays reliable.
    del question
    names = " ".join(_ASSET_NAMES.get(a, a) for a in asset_values)
    query = f"{names} cryptocurrency"

    async def _baseline_news(**params: Any) -> Any:
        return await _fetch_rss(
            feed_url=_COINDESK_RSS, source_name="CoinDesk", publisher_domain="coindesk.com",
            operation="baseline_news", analysis_as_of=analysis_as_of, assets=asset_values,
            lookback=params.get("lookback_days", 30),
        )

    async def _question_news(**params: Any) -> Any:
        return await _fetch_rss(
            feed_url=_google_news_url(query), source_name="Google News",
            publisher_domain="news.google.com", operation="question_news",
            analysis_as_of=analysis_as_of, assets=asset_values,
            lookback=params.get("lookback_days", 30),
        )

    return StaticToolRegistry({"baseline_news": _baseline_news, "question_news": _question_news})


def build_live_pipeline(
    *,
    clock: Clock,
    llm: Any,
    analysis_as_of: datetime,
    assets: Sequence[Asset] = (),
    question: str = "",
    per_stage_timeout_seconds: float = 45.0,
    kline_limit: int = 1000,
    arbiter_max_tokens: int = 3000,
    enable_news: bool = True,
) -> DeadlineAwarePipeline:
    """Live market + sentiment + (optional) first-party news, then Arbiter reasoning.

    With `enable_news` and at least one asset, a deterministic planner + Research
    Agent extract facts from CoinDesk RSS (a third, independent source type). The
    news branch runs in parallel with market and degrades on its own if the feed
    or extraction fails — the market + sentiment + Arbiter path is unaffected.
    """
    market_pipeline = OrganizerCsvPipeline(
        load_bars=binance_bar_loader(analysis_as_of, limit=kline_limit),
        extra_drafts=fear_greed_drafts(analysis_as_of),
        analysis_date=analysis_as_of.date(),
        market_source_name="binance_spot",
        market_independence_group="binance",
        market_source_url=_BINANCE_URL,
        # The Arbiter runs downstream in the DeadlineAwarePipeline, so the market
        # branch must not emit the misleading "no Arbiter" note.
        emit_no_arbiter_note=False,
    )
    # Cap output so a full analysis finishes inside the 45s single-call limit
    # (default 8000 tokens can overrun → DeadlineExceeded → fallback).
    arbiter = MappingArbiter(
        inner=Arbiter(
            llm=llm,
            result_schema=ArbiterGeneration,
            settings=ArbiterSettings(max_tokens=arbiter_max_tokens),
        )
    )

    planner = None
    research_agent = None
    if enable_news and assets:
        planner = _BaselinePlanner()
        research_agent = ResearchAgent(
            llm=llm,
            draft_schema=DraftBatch,
            tool_registry=_news_tool_registry(analysis_as_of, assets, question),
        )

    return DeadlineAwarePipeline(
        clock=clock,
        market_pipeline=market_pipeline,
        planner=planner,
        research_agent=research_agent,
        arbiter=arbiter,
        per_stage_timeout_seconds=per_stage_timeout_seconds,
    )
