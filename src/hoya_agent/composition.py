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

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings
from hoya_agent.adapters.live_sources import binance_bar_loader, fear_greed_drafts
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, OrganizerCsvPipeline
from hoya_agent.ports import Clock
from hoya_agent.reasoning.arbiter import Arbiter, ArbiterSettings
from hoya_agent.reasoning.mapping import build_analysis_result
from hoya_agent.reasoning.schemas import ArbiterGeneration

_BINANCE_URL = "https://api.binance.com/api/v3/klines"


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


def build_live_pipeline(
    *,
    clock: Clock,
    llm: Any,
    analysis_as_of: datetime,
    per_stage_timeout_seconds: float = 45.0,
    kline_limit: int = 1000,
    arbiter_max_tokens: int = 3000,
) -> DeadlineAwarePipeline:
    """Live market + sentiment evidence, then Arbiter (Bedrock) reasoning.

    Planner / Research (news extraction) are left off for the first live cut —
    they are the fragile multi-stage layer and are added once the Arbiter path is
    proven. The market branch alone still yields real-time, multi-source evidence.
    """
    market_pipeline = OrganizerCsvPipeline(
        load_bars=binance_bar_loader(analysis_as_of, limit=kline_limit),
        extra_drafts=fear_greed_drafts(analysis_as_of),
        analysis_date=analysis_as_of.date(),
        market_source_name="binance_spot",
        market_independence_group="binance",
        market_source_url=_BINANCE_URL,
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
    return DeadlineAwarePipeline(
        clock=clock,
        market_pipeline=market_pipeline,
        planner=None,
        research_agent=None,
        arbiter=arbiter,
        per_stage_timeout_seconds=per_stage_timeout_seconds,
    )
