"""The conclusion layer may be absent only when the result admits it (AC 6.4/9.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from tests.fakes import FakeLLM

from hoya_agent.conclusion_guards import (
    HONESTY_NOTE,
    StrictArbiterGeneration,
    StrictArbiterOutput,
    ensure_honest_insufficiency,
)
from hoya_agent.models import (
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    Reliability,
    Stance,
    TimeRange,
)
from hoya_agent.reasoning.arbiter import Arbiter

AS_OF = datetime(2026, 8, 1, tzinfo=UTC)


def _gen_claim(claim_id: str, claim_type: str, based_on: list[str] | None = None) -> dict:
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "assets": ["BTC"],
        "text": f"{claim_type} 主張。",
        "based_on_claim_ids": based_on or [],
        "confidence": "medium",
    }


def _generation_payload(**overrides: object) -> dict:
    payload: dict = {"direct_answer": "只有散文的回答。", "confidence": "medium"}
    payload.update(overrides)
    return payload


def _output_payload(**overrides: object) -> dict:
    payload: dict = {
        "direct_answer": "只有散文的回答。",
        "confidence": "medium",
        "confidence_rationale": "模型自報。",
    }
    payload.update(overrides)
    return payload


FACT_AND_CONCLUSION = [
    _gen_claim("cl_001", "fact"),
    _gen_claim("cl_002", "conclusion", based_on=["cl_001"]),
]


class TestStrictSchemas:
    @pytest.mark.parametrize(
        ("schema", "payload"),
        [
            (StrictArbiterGeneration, _generation_payload),
            (StrictArbiterOutput, _output_payload),
        ],
    )
    def test_empty_claims_without_insufficient_data_is_rejected(self, schema, payload):
        with pytest.raises(ValidationError) as excinfo:
            schema.model_validate(payload(claims=[]))
        # The message drives the Bedrock repair turn: it must name both fixes.
        message = str(excinfo.value)
        assert "insufficient_data=true" in message
        assert "conclusion" in message

    @pytest.mark.parametrize(
        ("schema", "payload"),
        [
            (StrictArbiterGeneration, _generation_payload),
            (StrictArbiterOutput, _output_payload),
        ],
    )
    def test_fact_only_claims_are_rejected(self, schema, payload):
        with pytest.raises(ValidationError) as excinfo:
            schema.model_validate(payload(claims=[_gen_claim("cl_001", "fact")]))
        message = str(excinfo.value)
        assert "conclusion" in message
        assert "insufficient_data=true" in message

    @pytest.mark.parametrize(
        ("schema", "payload"),
        [
            (StrictArbiterGeneration, _generation_payload),
            (StrictArbiterOutput, _output_payload),
        ],
    )
    def test_fact_plus_conclusion_is_accepted(self, schema, payload):
        result = schema.model_validate(payload(claims=FACT_AND_CONCLUSION))
        assert [str(claim.claim_type) for claim in result.claims] == ["fact", "conclusion"]

    @pytest.mark.parametrize(
        ("schema", "payload"),
        [
            (StrictArbiterGeneration, _generation_payload),
            (StrictArbiterOutput, _output_payload),
        ],
    )
    def test_empty_claims_with_insufficient_data_is_accepted(self, schema, payload):
        result = schema.model_validate(payload(claims=[], insufficient_data=True))
        assert result.insufficient_data is True


async def test_strict_schema_never_breaks_the_frozen_fallback() -> None:
    """A provider failure must still yield the honest fact-layer fallback."""
    from hoya_agent.adapters.bedrock import LLMUnavailableError

    ledger = SimpleNamespace(
        items=[
            SimpleNamespace(
                evidence_id="ev_001",
                asset="BTC",
                source_type="market_data",
                source_name="binance_spot",
                reliability="high",
                independence_group="binance",
                published_at=AS_OF,
                fetched_at=AS_OF,
                is_stale=False,
                normalized_fact="BTC 近 14 日收盤報酬為 -4.88%。",
                content_reference="deterministic 市場計算。",
            )
        ]
    )
    request = SimpleNamespace(question="BTC 近況?", assets=["BTC"], analysis_as_of=AS_OF)
    arbiter = Arbiter(
        llm=FakeLLM([LLMUnavailableError("boom")]),
        result_schema=StrictArbiterGeneration,
    )

    result, _notes = await arbiter.run(request=request, ledger=ledger, deadline=0.0)

    assert result.insufficient_data is True
    assert all(str(claim.claim_type) == "fact" for claim in result.claims)


def _analysis_result(**overrides: object) -> AnalysisResult:
    payload: dict = {
        "run_id": "run_20260801_120000_test",
        "question": "BTC 近況?",
        "assets": [Asset.BTC],
        "analysis_as_of": AS_OF,
        "direct_answer": "只有散文的回答。",
        "confidence": Reliability.medium,
        "confidence_rationale": "模型自報。",
    }
    payload.update(overrides)
    return AnalysisResult.model_validate(payload)


class TestEnsureHonestInsufficiency:
    def test_degenerate_result_is_marked_insufficient_and_low(self):
        degenerate = _analysis_result(claims=[], insufficient_data=False)

        honest = ensure_honest_insufficiency(degenerate)

        assert honest.insufficient_data is True
        assert honest.confidence is Reliability.low
        assert HONESTY_NOTE in honest.degradation_notes
        # The input is frozen and must stay untouched.
        assert degenerate.insufficient_data is False
        assert degenerate.confidence is Reliability.medium

    def test_result_with_claims_is_returned_unchanged(self):
        with_claims = _analysis_result(
            claims=[
                Claim(
                    claim_id="cl_001",
                    claim_type=ClaimType.fact,
                    assets=[Asset.BTC],
                    time_range=TimeRange(start="2026-07-18", end="2026-08-01"),
                    text="BTC 近 14 日收盤報酬為 -4.88%。",
                    confidence=Reliability.medium,
                )
            ],
            claim_evidence_links=[
                ClaimEvidenceLink(
                    claim_id="cl_001",
                    evidence_id="ev_001",
                    stance=Stance.supports,
                    reason="deterministic 市場計算。",
                )
            ],
        )

        assert ensure_honest_insufficiency(with_claims) is with_claims

    def test_already_insufficient_result_is_returned_unchanged(self):
        honest_empty = _analysis_result(
            claims=[], insufficient_data=True, confidence=Reliability.low
        )

        assert ensure_honest_insufficiency(honest_empty) is honest_empty
