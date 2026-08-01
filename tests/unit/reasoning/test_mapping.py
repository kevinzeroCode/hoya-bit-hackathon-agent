"""Arbiter generation → AnalysisResult mapping (fail-safe)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from hoya_agent.models import AnalysisResult
from hoya_agent.reasoning.mapping import to_analysis_result
from hoya_agent.reasoning.schemas import (
    ArbiterGeneration,
    GenClaim,
    GenLink,
)

UTC = timezone.utc


def _request():
    return SimpleNamespace(
        run_id="run_20260801_120000_test",
        question="BTC 過去兩週表現如何?",
        assets=["BTC"],
        analysis_as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )


def test_valid_generation_maps_to_analysis_result_with_a_claim():
    gen = ArbiterGeneration(
        direct_answer="BTC 近兩週小幅震盪。",
        claims=[
            GenClaim(claim_id="cl_001", claim_type="fact", assets=["BTC"], text="近 14 日報酬約 -1.6%。"),
        ],
        claim_evidence_links=[
            GenLink(claim_id="cl_001", evidence_id="ev_001", stance="supports", reason="市場數據"),
        ],
        confidence="medium",
        confidence_rationale="單一獨立來源,信心中等。",
    )
    result = to_analysis_result(gen, request=_request(), ledger=None)
    assert isinstance(result, AnalysisResult)
    assert result.run_id == "run_20260801_120000_test"
    assert len(result.claims) == 1
    assert result.claims[0].claim_id == "cl_001"
    assert result.insufficient_data is False


def test_insufficient_generation_maps_cleanly():
    gen = ArbiterGeneration(
        direct_answer="目前無法可靠判定。",
        confidence="low",
        confidence_rationale="資料不足。",
        insufficient_data=True,
    )
    result = to_analysis_result(gen, request=_request(), ledger=None)
    assert isinstance(result, AnalysisResult)
    assert result.insufficient_data is True
    assert result.claims == []


def test_malformed_generation_degrades_to_none():
    gen = ArbiterGeneration(
        direct_answer="x",
        claims=[GenClaim(claim_id="cl_001", claim_type="not_a_real_type", assets=["BTC"])],
        confidence="medium",
    )
    assert to_analysis_result(gen, request=_request(), ledger=None) is None


def test_bad_asset_degrades_to_none():
    gen = ArbiterGeneration(direct_answer="x", confidence="medium")
    bad_request = SimpleNamespace(
        run_id="run_20260801_120000_test",
        question="q",
        assets=["NOTACOIN"],
        analysis_as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert to_analysis_result(gen, request=bad_request, ledger=None) is None
