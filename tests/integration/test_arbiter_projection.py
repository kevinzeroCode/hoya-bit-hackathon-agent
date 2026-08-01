"""The real Arbiter, wired through the pipeline, yields a canonical AnalysisResult.

This is the offline half of the S8 reasoning path: the frozen `Arbiter` fills
`ArbiterOutput`, deterministic code stamps the frozen request context back on, and
the ledger, confidence caps and Trust Scorecards all behave. Only the live Bedrock
call is missing after this, not the wiring.

Both Silver-relevant paths are covered: a schema-valid model result, and a forced
model failure that must still produce a traceable deterministic report.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.adapters.bedrock import LLMError
from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    AnalysisResult,
    Asset,
    ClaimType,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunContext,
    RunMode,
    SourceType,
    Stance,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, PipelineOutcome
from hoya_agent.reasoning.arbiter import Arbiter
from hoya_agent.reasoning.arbiter_output import ArbiterOutput
from hoya_agent.reporting.renderer import render

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, tzinfo=UTC)
PUBLISHED = datetime(2026, 5, 20, tzinfo=UTC)
RUN_ID = "run_20260531_000000_ap01"


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


def _item(evidence_id: str, *, reliability: Reliability, group: str, fact: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        asset=Asset.BTC,
        source_type=SourceType.market if reliability is Reliability.high else SourceType.news,
        source_name=f"source-{evidence_id}",
        source_url=f"https://example.test/{evidence_id}",
        published_at=PUBLISHED,
        fetched_at=NOW,
        query_or_parameters=f"id={evidence_id}",
        content_reference=f"quote {evidence_id}",
        normalized_fact=fact,
        reliability=reliability,
        independence_group=group,
        content_hash=evidence_id.encode().hex().ljust(64, "0"),
    )


def _ledger(context: RunContext) -> EvidenceLedger:
    return EvidenceLedger(
        run_id=context.run_id,
        analysis_as_of=context.analysis_as_of,
        run_mode=context.run_mode,
        items=[
            _item(
                "ev_001",
                reliability=Reliability.high,
                group="organizer-public-market-data",
                fact="BTC 的 14 日報酬為 -4.88%（截至 2026-05-31 UTC）。",
            ),
            _item(
                "ev_002",
                reliability=Reliability.medium,
                group="coindesk.com",
                fact="具名媒體報導同期現貨買盤增加。",
            ),
        ],
    )


class Market:
    async def execute(self, context: RunContext, emit) -> PipelineOutcome:
        del emit
        return PipelineOutcome(
            ledger=_ledger(context),
            result=None,
            terminal_state=TerminalState.completed,
        )


class OutputLLM:
    """Returns a schema-valid ArbiterOutput, as a live model is expected to."""

    async def converse_structured(self, **kwargs):
        del kwargs
        return ArbiterOutput.model_validate(
            {
                "direct_answer": "近期回落與現貨賣壓一致，但存在反向訊號。",
                "market_context": {"summary": "BTC 市場狀況。", "time_range": None},
                "claims": [
                    {
                        "claim_id": "cl_001",
                        "claim_type": "fact",
                        "assets": ["BTC"],
                        "text": "BTC 的 14 日報酬為 -4.88%。",
                        "based_on_claim_ids": [],
                        "confidence": "high",
                    },
                    {
                        "claim_id": "cl_002",
                        "claim_type": "conclusion",
                        "assets": ["BTC"],
                        "text": "近期回落主要由現貨賣壓解釋。",
                        "based_on_claim_ids": ["cl_001"],
                        "confidence": "high",
                    },
                ],
                "claim_evidence_links": [
                    {
                        "claim_id": "cl_001",
                        "evidence_id": "ev_001",
                        "stance": "supports",
                        "reason": "deterministic 報酬計算涵蓋該期間。",
                    },
                    {
                        "claim_id": "cl_002",
                        "evidence_id": "ev_001",
                        "stance": "supports",
                        "reason": "報酬方向與結論一致。",
                    },
                    {
                        "claim_id": "cl_002",
                        "evidence_id": "ev_002",
                        "stance": "opposes",
                        "reason": "具名媒體報導方向相反。",
                    },
                ],
                "confidence": "high",
                "confidence_rationale": "兩個獨立來源涵蓋主要觀察。",
                "watch_items": ["後續現貨買盤是否延續"],
            }
        )


class FailingLLM:
    async def converse_structured(self, **kwargs):
        del kwargs
        raise LLMError("injected model failure")


def _context() -> RunContext:
    request = AnalysisRequest(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        requested_at=NOW,
        analysis_as_of=NOW,
        run_mode=RunMode.rehearsal,
        run_id=RUN_ID,
    )
    return build_run_context(request, Clock())


async def _run(llm) -> PipelineOutcome:
    return await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=Market(),
        arbiter=Arbiter(llm=llm, result_schema=ArbiterOutput),
    ).execute(_context(), lambda event: None)


async def test_model_result_projects_onto_a_canonical_analysis_result() -> None:
    outcome = await _run(OutputLLM())

    assert isinstance(outcome.result, AnalysisResult)
    assert outcome.result.run_id == RUN_ID
    assert outcome.result.assets == [Asset.BTC]
    assert outcome.result.analysis_as_of == NOW
    assert [claim.claim_type for claim in outcome.result.claims] == [
        ClaimType.fact,
        ClaimType.conclusion,
    ]
    assert outcome.result.claim_evidence_links[2].stance is Stance.opposes


async def test_time_ranges_come_from_the_evidence_window() -> None:
    outcome = await _run(OutputLLM())
    assert outcome.result is not None

    assert outcome.result.market_context is not None
    assert outcome.result.market_context.time_range.start == "2026-05-20"
    assert outcome.result.market_context.time_range.end == "2026-05-31"
    for claim in outcome.result.claims:
        assert claim.time_range.end <= "2026-05-31"


async def test_material_conflict_and_caps_still_apply_after_projection() -> None:
    outcome = await _run(OutputLLM())
    assert outcome.result is not None

    assert [i.claim_id for i in outcome.ledger.conflict_indicators] == ["cl_002"]
    conclusion = next(c for c in outcome.result.claims if c.claim_id == "cl_002")
    assert conclusion.confidence is Reliability.low
    assert outcome.result.confidence is not Reliability.high
    assert outcome.result.trust_scorecards, "the conclusion must receive a scorecard"


async def test_the_report_renders_from_the_projected_result() -> None:
    outcome = await _run(OutputLLM())
    assert outcome.result is not None

    report = render(outcome.result, outcome.ledger)
    assert "ev_001" in report
    assert "ev_002" in report


async def test_model_failure_still_yields_a_traceable_deterministic_report() -> None:
    """Silver's second half: the fallback must keep its evidence links."""
    outcome = await _run(FailingLLM())

    assert isinstance(outcome.result, AnalysisResult)
    assert outcome.result.insufficient_data is True
    assert outcome.result.confidence is Reliability.low
    assert outcome.result.claims, "the fallback must retain validated facts"
    assert outcome.result.claim_evidence_links[0].evidence_id == "ev_001"
    assert outcome.terminal_state is TerminalState.degraded
    report = render(outcome.result, outcome.ledger)
    assert "ev_001" in report
