from hoya_agent.composition import _repair_arbiter_generation
from hoya_agent.reasoning.schemas import ArbiterGeneration


def test_repair_adds_matching_numeric_evidence_link_and_conclusion_support() -> None:
    generation = ArbiterGeneration.model_validate(
        {
            "direct_answer": "BTC 近期下跌。",
            "claims": [
                {
                    "claim_id": "cl_001",
                    "claim_type": "fact",
                    "assets": ["BTC"],
                    "text": "BTC 近 14 日報酬為 -3.10%",
                    "confidence": "medium",
                },
                {
                    "claim_id": "cl_002",
                    "claim_type": "conclusion",
                    "assets": ["BTC"],
                    "text": "下行風險仍需觀察。",
                    "based_on_claim_ids": ["cl_001"],
                    "confidence": "low",
                },
            ],
            "claim_evidence_links": [
                {
                    "claim_id": "cl_001",
                    "evidence_id": "ev_002",
                    "stance": "neutral",
                    "reason": "model link",
                }
            ],
            "confidence": "low",
            "confidence_rationale": "test",
        }
    )
    repaired = _repair_arbiter_generation(
        generation,
        [
            {
                "evidence_id": "ev_001",
                "asset": "BTC",
                "normalized_fact": "BTC 近 14 日報酬為 -3.10%",
                "content_reference": "BTC return -3.10% over 14 days",
            },
            {
                "evidence_id": "ev_002",
                "asset": "BTC",
                "normalized_fact": "市場資料",
                "content_reference": "market data",
            },
        ],
    )
    links = repaired.claim_evidence_links
    assert any(
        link.claim_id == "cl_001" and link.evidence_id == "ev_001" and link.stance == "supports"
        for link in links
    )
    assert any(
        link.claim_id == "cl_002" and link.evidence_id == "ev_001" and link.stance == "supports"
        for link in links
    )
