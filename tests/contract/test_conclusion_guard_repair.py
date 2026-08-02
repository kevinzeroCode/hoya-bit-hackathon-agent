"""The dominant live failure — a claims-empty generation — must trigger the repair turn.

docs/rehearsals/run-log.md: over seven identical live runs, six produced
`claims: []` straight from the model (not lost in mapping). With the strict
schema injected, that payload fails validation inside the Bedrock client, which
sends its single repair turn quoting the violation; the second payload must
carry a conclusion. This is the whole point of `StrictArbiterGeneration`.
"""

from __future__ import annotations

import asyncio
import time
import unittest

from hoya_agent.adapters.bedrock import (
    STRUCTURED_TOOL_NAME,
    BedrockLLMClient,
    BedrockSettings,
)
from hoya_agent.conclusion_guards import StrictArbiterGeneration


def tool_response(payload: dict, tool_name: str = STRUCTURED_TOOL_NAME) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"name": tool_name, "input": payload}}],
            }
        }
    }


class FakeConverse:
    """Replays a queued script of responses, recording requests."""

    def __init__(self, script) -> None:
        self.script = list(script)
        self.requests: list[dict] = []

    def converse(self, **request):
        self.requests.append(request)
        if not self.script:
            raise AssertionError("FakeConverse ran out of scripted responses")
        return self.script.pop(0)


PROSE_ONLY = {
    "direct_answer": "BTC 近兩週走弱，量能放大。",
    "confidence": "medium",
    "claims": [],
}

REPAIRED = {
    "direct_answer": "BTC 近兩週走弱，量能放大。",
    "confidence": "medium",
    "claims": [
        {
            "claim_id": "cl_001",
            "claim_type": "fact",
            "assets": ["BTC"],
            "text": "BTC 近 14 日收盤報酬為 -4.88%。",
        },
        {
            "claim_id": "cl_002",
            "claim_type": "conclusion",
            "assets": ["BTC"],
            "text": "就指定期間而言，BTC 呈現帶量回落的整理格局。",
            "based_on_claim_ids": ["cl_001"],
        },
    ],
    "claim_evidence_links": [
        {"claim_id": "cl_001", "evidence_id": "ev_001", "stance": "supports", "reason": "市場計算。"},
        {"claim_id": "cl_002", "evidence_id": "ev_001", "stance": "supports", "reason": "同一市場計算支持結論。"},
    ],
}


class ConclusionGuardRepairTests(unittest.TestCase):
    def test_empty_claims_payload_is_repaired_in_band(self):
        fake = FakeConverse([tool_response(PROSE_ONLY), tool_response(REPAIRED)])
        client = BedrockLLMClient(
            settings=BedrockSettings(region="us-east-1", primary_model_id="anthropic.primary"),
            client=fake,
        )

        result = asyncio.run(
            client.converse_structured(
                operation="arbiter",
                messages=[{"role": "user", "content": [{"text": "分析 BTC"}]}],
                schema=StrictArbiterGeneration,
                max_tokens=3000,
                deadline=time.monotonic() + 30.0,
                system_prompt="SYSTEM PROMPT BODY",
            )
        )

        self.assertEqual(len(fake.requests), 2, "exactly one repair turn")
        self.assertTrue(
            any(str(claim.claim_type) == "conclusion" for claim in result.claims)
        )
        # The repair turn must tell the model both admissible fixes.
        repair_text = fake.requests[1]["messages"][-1]["content"][0]["text"]
        self.assertIn("conclusion", repair_text)
        self.assertIn("insufficient_data=true", repair_text)


if __name__ == "__main__":
    unittest.main()
