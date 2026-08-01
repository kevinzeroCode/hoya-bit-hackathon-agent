"""Material conflict survives into the artifacts (evidence-contracts §9, §10).

The Arbiter emits claims and stanced links; the deterministic conflict rule then
runs over the ledger, the indicator is persisted in `evidence.json`, the affected
conclusion is capped at `low`, overall confidence cannot stay `high`, and the
renderer shows both sides. H3 never executes for any of this to happen.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    EvidenceItem,
    EvidenceLedger,
    Reliability,
    RunContext,
    RunMode,
    SourceType,
    Stance,
    TerminalState,
    TimeRange,
)
from hoya_agent.orchestration.pipeline import DeadlineAwarePipeline, PipelineOutcome
from hoya_agent.reporting.renderer import render

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, tzinfo=UTC)
RUN_ID = "run_20260531_000000_mc01"


class Clock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


def _item(
    evidence_id: str,
    *,
    reliability: Reliability,
    group: str,
    source_type: SourceType,
    fact: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        asset=Asset.BTC,
        source_type=source_type,
        source_name=f"source-{evidence_id}",
        source_url=f"https://example.test/{evidence_id}",
        published_at=NOW,
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
                source_type=SourceType.market,
                fact="BTC 的 14 日報酬為 -4.88%（截至 2026-05-31 UTC）。",
            ),
            _item(
                "ev_002",
                reliability=Reliability.medium,
                group="coindesk.com",
                source_type=SourceType.news,
                fact="具名媒體報導指出同期現貨買盤增加。",
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


class ConflictingArbiter:
    """Returns a schema-valid result whose conclusion has both stances on it."""

    async def run(self, *, request, ledger, indicators, deadline, degradation_notes):
        del ledger, indicators, deadline, degradation_notes
        period = TimeRange(start="2026-05-17", end="2026-05-31")
        fact = Claim(
            claim_id="cl_001",
            claim_type=ClaimType.fact,
            assets=[Asset.BTC],
            time_range=period,
            text="BTC 的 14 日報酬為 -4.88%。",
            confidence=Reliability.high,
        )
        conclusion = Claim(
            claim_id="cl_002",
            claim_type=ClaimType.conclusion,
            assets=[Asset.BTC],
            time_range=period,
            text="近期回落主要由現貨賣壓解釋。",
            based_on_claim_ids=[fact.claim_id],
            confidence=Reliability.high,
        )
        result = AnalysisResult(
            run_id=request.run_id,
            question=request.question,
            assets=[Asset.BTC],
            analysis_as_of=request.analysis_as_of,
            direct_answer="回落與現貨賣壓一致，但存在反向訊號。",
            claims=[fact, conclusion],
            claim_evidence_links=[
                ClaimEvidenceLink(
                    claim_id="cl_001",
                    evidence_id="ev_001",
                    stance=Stance.supports,
                    reason="deterministic 報酬計算涵蓋該期間",
                ),
                ClaimEvidenceLink(
                    claim_id="cl_002",
                    evidence_id="ev_001",
                    stance=Stance.supports,
                    reason="報酬方向與結論一致",
                ),
                ClaimEvidenceLink(
                    claim_id="cl_002",
                    evidence_id="ev_002",
                    stance=Stance.opposes,
                    reason="具名媒體報導與賣壓解釋方向相反",
                ),
            ],
            confidence=Reliability.high,
            confidence_rationale="兩個獨立來源涵蓋主要觀察。",
        )
        return result, []


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


async def _run() -> PipelineOutcome:
    return await DeadlineAwarePipeline(
        clock=Clock(),
        market_pipeline=Market(),
        arbiter=ConflictingArbiter(),
    ).execute(_context(), lambda event: None)


async def test_material_conflict_is_persisted_in_the_ledger() -> None:
    outcome = await _run()

    assert len(outcome.ledger.conflict_indicators) == 1
    indicator = outcome.ledger.conflict_indicators[0]
    assert indicator.claim_id == "cl_002"
    assert indicator.supporting_evidence_ids == ["ev_001"]
    assert indicator.opposing_evidence_ids == ["ev_002"]
    assert indicator.independence_groups == [
        "coindesk.com",
        "organizer-public-market-data",
    ]


async def test_conflicted_conclusion_is_capped_at_low() -> None:
    outcome = await _run()
    assert outcome.result is not None

    conclusion = next(claim for claim in outcome.result.claims if claim.claim_id == "cl_002")
    assert conclusion.confidence is Reliability.low
    assert outcome.result.confidence is not Reliability.high


async def test_conflict_is_disclosed_and_both_sides_render() -> None:
    outcome = await _run()
    assert outcome.result is not None

    assert any("矛盾" in note for note in outcome.degradation_notes)
    report = render(outcome.result, outcome.ledger)
    assert "ev_001" in report
    assert "ev_002" in report


async def test_trust_scorecard_consistency_reflects_the_conflict() -> None:
    outcome = await _run()
    assert outcome.result is not None

    cards = {card.claim_id: card for card in outcome.result.trust_scorecards}
    assert "cl_002" in cards, "a conclusion must still receive a scorecard"
    consistency = cards["cl_002"].consistency
    assert consistency.has_material_conflict is True
    assert consistency.level.value == "weak"
