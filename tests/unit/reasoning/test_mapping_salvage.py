"""Deterministic claim-graph salvage: one bad claim must not discard the rest.

Regression for the live symptom "沒有推論和結論" — a single conclusion whose only
evidence link was neutral used to fail strict validation and force the fact-only
fallback, dropping every inference and conclusion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from hoya_agent.models import ClaimType
from hoya_agent.reasoning.mapping import build_analysis_result, to_analysis_result
from hoya_agent.reasoning.schemas import ArbiterGeneration, GenClaim, GenLink

UTC = timezone.utc


def _request():
    return SimpleNamespace(
        run_id="run_20260801_120000_test",
        question="BTC 過去兩週表現?",
        assets=["BTC"],
        analysis_as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )


def _claim(cid, ctype, based_on=()):
    return GenClaim(
        claim_id=cid, claim_type=ctype, assets=["BTC"], text=f"{cid} text",
        based_on_claim_ids=list(based_on), confidence="medium",
    )


def _link(cid, eid, stance):
    return GenLink(claim_id=cid, evidence_id=eid, stance=stance, reason="r")


def _types(result):
    return [(c.claim_id, c.claim_type) for c in result.claims]


def test_drops_only_the_unsupported_conclusion_keeps_the_rest():
    gen = ArbiterGeneration(
        direct_answer="分析。",
        claims=[
            _claim("cl_001", "fact"),
            _claim("cl_002", "fact"),
            _claim("cl_003", "inference", based_on=["cl_001"]),
            _claim("cl_004", "conclusion", based_on=["cl_003"]),  # only neutral link -> drop
            _claim("cl_005", "conclusion", based_on=["cl_003"]),
        ],
        claim_evidence_links=[
            _link("cl_001", "ev_001", "supports"),
            _link("cl_002", "ev_002", "supports"),
            _link("cl_003", "ev_001", "supports"),
            _link("cl_004", "ev_002", "neutral"),   # not a real support
            _link("cl_005", "ev_001", "supports"),
        ],
        confidence="medium",
    )
    result = build_analysis_result(gen, request=_request(), ledger=None)
    assert _types(result) == [
        ("cl_001", ClaimType.fact),
        ("cl_002", ClaimType.fact),
        ("cl_003", ClaimType.inference),
        ("cl_005", ClaimType.conclusion),
    ]
    # cl_004 (and its dangling link) are gone; the disclosure is honest.
    assert not any(link.claim_id == "cl_004" for link in result.claim_evidence_links)
    assert any("自我修復" in note and "1" in note for note in result.degradation_notes)


def test_cascades_when_a_dependency_is_removed():
    gen = ArbiterGeneration(
        direct_answer="分析。",
        claims=[
            _claim("cl_001", "fact"),
            _claim("cl_002", "inference", based_on=["cl_099"]),  # missing dep -> drop
            _claim("cl_003", "conclusion", based_on=["cl_002"]),  # orphaned -> drop
        ],
        claim_evidence_links=[
            _link("cl_001", "ev_001", "supports"),
            _link("cl_002", "ev_001", "supports"),
            _link("cl_003", "ev_001", "supports"),
        ],
        confidence="medium",
    )
    result = build_analysis_result(gen, request=_request(), ledger=None)
    assert _types(result) == [("cl_001", ClaimType.fact)]


def test_link_citing_a_claim_id_as_evidence_is_dropped():
    gen = ArbiterGeneration(
        direct_answer="分析。",
        claims=[
            _claim("cl_001", "fact"),
            _claim("cl_002", "fact"),  # only "evidence" is a cl_ id -> unsupported -> drop
        ],
        claim_evidence_links=[
            _link("cl_001", "ev_001", "supports"),
            _link("cl_002", "cl_001", "supports"),  # malformed evidence_id
        ],
        confidence="medium",
    )
    result = build_analysis_result(gen, request=_request(), ledger=None)
    assert _types(result) == [("cl_001", ClaimType.fact)]


def test_evidence_id_absent_from_ledger_is_dropped():
    ledger = SimpleNamespace(items=[SimpleNamespace(evidence_id="ev_001")])
    gen = ArbiterGeneration(
        direct_answer="分析。",
        claims=[_claim("cl_001", "fact"), _claim("cl_002", "fact")],
        claim_evidence_links=[
            _link("cl_001", "ev_001", "supports"),
            _link("cl_002", "ev_777", "supports"),  # not in ledger
        ],
        confidence="medium",
    )
    result = build_analysis_result(gen, request=_request(), ledger=ledger)
    assert _types(result) == [("cl_001", ClaimType.fact)]


def test_unsalvageable_generation_degrades_to_none():
    gen = ArbiterGeneration(
        direct_answer="散文。",
        claims=[_claim("cl_001", "conclusion", based_on=["cl_999"])],  # nothing valid
        claim_evidence_links=[_link("cl_001", "ev_001", "neutral")],
        confidence="medium",
    )
    assert to_analysis_result(gen, request=_request(), ledger=None) is None
