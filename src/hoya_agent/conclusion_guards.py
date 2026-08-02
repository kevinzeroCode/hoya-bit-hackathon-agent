"""Enforce the conclusion-layer contract from outside the frozen reasoning package.

The frozen schemas accept ``claims: []`` as valid, so a prose-only generation
sails past ``structural_violations()`` (every loop no-ops on an empty list) and
renders an empty §7 結論 while the report still advertises confidence=medium and
資料是否不足=否 — the exact state AC 6.4 / AC 9.6 forbid. Rehearsals measured one
conclusion-bearing run in seven (docs/rehearsals/run-log.md).

Two layers close the gap without touching ``reasoning/``:

- ``StrictArbiterGeneration`` / ``StrictArbiterOutput`` are injected as the
  Arbiter's ``result_schema``. An empty or conclusion-free claims list becomes a
  ``ValidationError``, which the Bedrock client feeds back to the model through
  its single repair turn; if the repair also fails, the frozen Arbiter falls
  back to its honest fact-layer result (``insufficient_data=true``).
- ``ensure_honest_insufficiency`` is the pipeline-side last line of defense: a
  claims-empty ``AnalysisResult`` may never ship as a confident report.

The validator exempts ``insufficient_data=true`` because the frozen fallback
legitimately emits ``claims: []`` when no high-reliability facts survive. For
the same reason the constraint must not be a ``Field(min_length=1)``: it would
reject the fallback payload and cannot express the conditional anyway.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import model_validator

from hoya_agent.models import AnalysisResult, Reliability
from hoya_agent.reasoning.arbiter_output import ArbiterOutput
from hoya_agent.reasoning.schemas import ArbiterGeneration

# Written for the Bedrock repair turn: state the failure, the two admissible
# fixes, and repeat the no-new-evidence rule so it cannot conflict with the
# repair boilerplate's 「不要新增證據」.
_EMPTY_CLAIMS_ERROR = (
    "claims 為空但 insufficient_data=false。請依據已提供的 evidence 重新輸出結構化"
    " claims：至少 2 個 fact、1 個 inference、1 個 claim_type=\"conclusion\"，並為每個"
    " inference/conclusion 附上 stance=\"supports\" 的 claim_evidence_links，只引用既有"
    " ev_ 證據、不要新增證據。若現有證據確實不足以形成結論，請改設"
    " insufficient_data=true 並於 degradation_notes 說明原因。"
)
_NO_CONCLUSION_ERROR = (
    "claims 缺少 conclusion 層：insufficient_data=false 時必須至少有一個"
    " claim_type=\"conclusion\" 的 claim。請新增 conclusion，其 based_on_claim_ids 指向"
    " 既有 fact/inference，並附上 stance=\"supports\" 的 claim_evidence_links 指向既有"
    " ev_ 證據、不要新增證據。若無法從現有證據得出結論，請改設 insufficient_data=true。"
)

#: Disclosed on any result the honesty guard had to correct.
HONESTY_NOTE = "Arbiter 完成但未產出任何 claim，依 AC 6.4 改列為資料不足並將信心下修為 low。"


def _require_conclusion_layer(insufficient_data: bool, claims: Sequence[Any]) -> None:
    """Raise unless the claims carry a conclusion or the result admits it can't."""
    if insufficient_data:
        return
    if not claims:
        raise ValueError(_EMPTY_CLAIMS_ERROR)
    if not any(str(getattr(claim, "claim_type", "")) == "conclusion" for claim in claims):
        raise ValueError(_NO_CONCLUSION_ERROR)


class StrictArbiterGeneration(ArbiterGeneration):
    """`ArbiterGeneration` that refuses a confident result with no conclusion."""

    @model_validator(mode="after")
    def _conclusion_layer_present(self) -> "StrictArbiterGeneration":
        _require_conclusion_layer(self.insufficient_data, self.claims)
        return self


class StrictArbiterOutput(ArbiterOutput):
    """`ArbiterOutput` that refuses a confident result with no conclusion."""

    @model_validator(mode="after")
    def _conclusion_layer_present(self) -> "StrictArbiterOutput":
        _require_conclusion_layer(self.insufficient_data, self.claims)
        return self


def ensure_honest_insufficiency(result: AnalysisResult) -> AnalysisResult:
    """Never let a claims-empty result pose as a confident one (AC 6.4 / 9.6).

    ``model_copy`` skips validators, so the ``insufficient_data ⇒ confidence=low``
    invariant must be re-established by hand here.
    """
    if result.claims or result.insufficient_data:
        return result
    return result.model_copy(
        update={
            "insufficient_data": True,
            "confidence": Reliability.low,
            "degradation_notes": [*result.degradation_notes, HONESTY_NOTE],
        }
    )
