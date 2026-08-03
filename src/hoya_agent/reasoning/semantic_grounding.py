"""Semantic grounding recheck for purely-qualitative facts (Task 16 / G1).

`evidence/grounding.py`'s deterministic pass returns `unverified` for a fact
with no checkable hard atom (no percent/money/date/number) — not because it
looks fabricated, but because there is nothing numeric to mechanically check.
That verdict currently costs the fact its confidence support under
`evidence.ledger.confidence_signals_for_claim(require_grounding=True)`, the
same penalty a demonstrably-fabricated numeric fact gets. This module gives
purely-qualitative facts a fair, bounded LLM plausibility check instead of a
permanent penalty.

Deliberately outside `evidence/`: that package must stay LLM-free per its own
docstring. This is additive reasoning-layer code — it does not modify the
frozen `reasoning/arbiter.py`, `research_agent.py` or `evidence/grounding.py`.

Red lines (same as the deterministic half):
- Never mutates the static `reliability` table.
- Adds no field to `EvidenceItem`/`EvidenceDraft`.
- Never blocks or fails a run: any LLM error, timeout or malformed output
  degrades to `SemanticGroundingStatus.unverified` — the same safe default
  the deterministic pass already produces for a purely-qualitative fact, so
  a failure here never claims more than the deterministic pass already did.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from hoya_agent.adapters.bedrock import LLMError
from hoya_agent.reasoning.prompt_library import load_prompt

DEFAULT_MAX_TOKENS = 300
_VALID_VERDICTS = frozenset({"verified", "contradicted", "uncertain"})


class SemanticGroundingStatus(str, Enum):
    verified = "verified"          # source plausibly supports the fact
    contradicted = "contradicted"  # source appears to contradict the fact
    unverified = "unverified"      # LLM unavailable, failed or uncertain — safe default


@dataclass(frozen=True)
class SemanticVerdict:
    status: SemanticGroundingStatus
    note: str = ""


class SemanticGroundingGeneration(BaseModel):
    """The model's raw structured output for one fact-vs-source check."""

    model_config = ConfigDict(extra="forbid")

    verdict: str
    reason: str = ""


async def semantic_ground(
    normalized_fact: str,
    content_reference: str,
    *,
    llm: Any,
    deadline: float,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SemanticVerdict:
    """One bounded LLM call: does `content_reference` plausibly support `normalized_fact`?

    Never raises. Any LLM error, timeout, or an out-of-enum `verdict` degrades
    to `SemanticGroundingStatus.unverified` rather than propagating — this call
    must never be able to block or fail a run.
    """
    try:
        generated = await llm.converse_structured(
            operation="semantic_grounding",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                f"原文摘錄：{content_reference}\n\n"
                                f"待查事實：{normalized_fact}"
                            )
                        }
                    ],
                }
            ],
            schema=SemanticGroundingGeneration,
            max_tokens=max_tokens,
            deadline=deadline,
            system_prompt=load_prompt("semantic_grounding").body,
        )
    except LLMError:
        return SemanticVerdict(
            SemanticGroundingStatus.unverified, note="語意複核呼叫失敗，維持確定性判定"
        )

    verdict = str(getattr(generated, "verdict", "") or "").strip().lower()
    reason = str(getattr(generated, "reason", "") or "")
    if verdict not in _VALID_VERDICTS or verdict == "uncertain":
        return SemanticVerdict(
            SemanticGroundingStatus.unverified, note=reason or "模型回覆不確定或格式不符"
        )
    return SemanticVerdict(SemanticGroundingStatus(verdict), note=reason)
