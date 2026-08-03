"""Unit tests for the G1 semantic grounding recheck (Task 16)."""

from __future__ import annotations

import time
import unittest

from _stubs import BoomError, FakeLLM

from hoya_agent.reasoning.semantic_grounding import (
    SemanticGroundingGeneration,
    SemanticGroundingStatus,
    semantic_ground,
)


def _run(llm, fact="市場情緒轉為樂觀", source="分析師表示市場情緒已明顯轉向樂觀"):
    import asyncio

    return asyncio.run(
        semantic_ground(fact, source, llm=llm, deadline=time.monotonic() + 30)
    )


class SemanticGroundTests(unittest.TestCase):
    def test_a_supporting_source_is_verified(self):
        llm = FakeLLM([SemanticGroundingGeneration(verdict="verified", reason="原文明確提到樂觀")])
        verdict = _run(llm)
        self.assertEqual(verdict.status, SemanticGroundingStatus.verified)
        self.assertIn("樂觀", verdict.note)

    def test_a_contradicting_source_is_contradicted(self):
        llm = FakeLLM([SemanticGroundingGeneration(verdict="contradicted", reason="原文說市場轉為悲觀")])
        verdict = _run(llm, fact="市場情緒轉為樂觀", source="分析師表示市場情緒已明顯轉向悲觀")
        self.assertEqual(verdict.status, SemanticGroundingStatus.contradicted)

    def test_llm_failure_degrades_to_unverified_never_raises(self):
        llm = FakeLLM([BoomError("provider unavailable")])
        verdict = _run(llm)
        self.assertEqual(verdict.status, SemanticGroundingStatus.unverified)

    def test_llm_timeout_degrades_to_unverified_never_raises(self):
        llm = FakeLLM([BoomError("deadline exceeded")])
        verdict = _run(llm)
        self.assertEqual(verdict.status, SemanticGroundingStatus.unverified)

    def test_model_uncertain_verdict_degrades_to_unverified(self):
        llm = FakeLLM([SemanticGroundingGeneration(verdict="uncertain", reason="原文未提及")])
        verdict = _run(llm)
        self.assertEqual(verdict.status, SemanticGroundingStatus.unverified)

    def test_an_out_of_enum_verdict_degrades_to_unverified_not_raises(self):
        """The model must never be trusted to only ever emit the three allowed
        values; a stray fourth value must degrade safely, not propagate."""
        llm = FakeLLM([SemanticGroundingGeneration(verdict="probably", reason="")])
        verdict = _run(llm)
        self.assertEqual(verdict.status, SemanticGroundingStatus.unverified)

    def test_sends_only_the_fact_and_source_never_an_unbounded_payload(self):
        llm = FakeLLM([SemanticGroundingGeneration(verdict="verified", reason="ok")])
        _run(llm, fact="X 事件發生", source="原文提到 X 事件")
        call = llm.calls[0]
        self.assertEqual(call["operation"], "semantic_grounding")
        text = call["messages"][0]["content"][0]["text"]
        self.assertIn("X 事件發生", text)
        self.assertIn("原文提到 X 事件", text)
        self.assertLessEqual(call["max_tokens"], 300)


if __name__ == "__main__":
    unittest.main()
