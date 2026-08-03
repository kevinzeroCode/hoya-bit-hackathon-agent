"""H3 conditional debate — opt-in, off by default (Task 17).

`DisabledConflictExtension` (`conflict_extension.py`) stays the only extension
wired anywhere by default; this module is a second, additive implementation of
the same `evaluate()` shape, selectable only when a caller explicitly opts in
and explicitly wires it. Nothing here changes `DisabledConflictExtension`,
`reasoning/arbiter.py`, or any other frozen file.

Design, and why it looks the way it does:

- **`evaluate()` never calls the LLM.** It only decides whether a debate is
  warranted (an `enable_conditional_debate` context flag plus a real material
  conflict from `evidence/ledger.py::build_conflict_indicators` — the existing
  deterministic rule; this module invents no second conflict detector). This
  mirrors `DisabledConflictExtension.evaluate()` exactly, so the "no material
  conflict -> route straight to Arbiter, unchanged" behavior is identical
  whether or not the flag is set.
- **The actual debate is a separate method, `run_debate()`**, because
  `ConflictExtensionResult` (the shared return shape) carries no room for a
  revised claim, and inventing a second return type would break interface
  parity with `DisabledConflictExtension`. A caller that gets `route="debate"`
  from `evaluate()` calls `run_debate()` next; this module does not call
  itself, so there is no risk of `evaluate()` silently starting an LLM call.
- **The Judge's output schema is narrower than `ArbiterClaim`**, not a reuse
  of it: `claim_id`, `claim_type`, `assets`, `time_range` and
  `based_on_claim_ids` come from the *original* claim, unchanged, and are
  never in the model's own output. Only `text`, `confidence`, `limitations`
  and `confidence_rationale` are revisable — the narrowest surface that lets
  the Judge do its one job (weigh both sides) without being able to touch
  claim identity, dependencies or scope. This still follows
  `arbiter_output.py`'s pattern (LLM fills a narrow schema; deterministic code
  projects the frozen/unchanged parts back on), just not by importing
  `ArbiterClaim` itself, which exposes fields (assets, time_range,
  based_on_claim_ids) H3 must never let the model rewrite.
- **Any failure at any of the three steps (timeout, LLM error, schema
  failure) aborts the whole debate** and the caller keeps the Arbiter's
  original claim unchanged. H3 must never be able to make an otherwise-
  successful run fail or degrade.

**Not wired into `orchestration/pipeline.py` in this change.** See
`docs/Implementation-Plan.md` §9 Task 17 for why, and exactly where a future
change would need to insert the `evaluate()` / `run_debate()` calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from hoya_agent.adapters.bedrock import LLMError
from hoya_agent.models import Claim, Reliability
from hoya_agent.reasoning.conflict_extension import (
    ARBITER_ROUTE,
    DISABLED_STATUS,
    ConflictExtensionResult,
)
from hoya_agent.reasoning.prompt_library import load_prompt

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime dependency
    from hoya_agent.models import ConflictIndicator, EvidenceLedger, RunContext

#: Route value the pipeline would need to recognize to call `run_debate()`.
#: Not read anywhere today — recorded here so a future wiring has one place
#: to point at rather than inventing its own string.
DEBATE_ROUTE = "debate"
ACTIVE_STATUS = "active"

#: Shown wherever the product states H3's status once this lands and passes
#: its own rehearsal. Not swapped in for `conflict_extension.UNIMPLEMENTED_LABEL`
#: anywhere by this change — that label still describes the wired default.
OPT_IN_LABEL = "H3 conditional debate: opt-in, off by default"

DEFAULT_MAX_TOKENS = 400


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class DebateArgument(BaseModel):
    """Bull's or Bear's single-sided output — see `prompts/bull-v1.md` / `bear-v1.md`."""

    model_config = ConfigDict(extra="forbid")

    argument: str
    cited_evidence_ids: list[str] = []

    @field_validator("argument")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("argument must not be blank")
        return text


class DebateVerdict(BaseModel):
    """The Judge's output — deliberately narrower than `ArbiterClaim`; see the
    module docstring for why `claim_id`/`claim_type`/`assets`/`time_range`/
    `based_on_claim_ids` are not fields here."""

    model_config = ConfigDict(extra="forbid")

    text: str
    confidence: Literal["medium", "low"]
    limitations: list[str] = []
    confidence_rationale: str

    @field_validator("text", "confidence_rationale")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("text fields must not be blank")
        return text


@dataclass(frozen=True)
class DebateOutcome:
    """`revised_claim` is `None` on any failure — the caller must then keep
    the original claim unchanged, never fall back to a half-updated one."""

    revised_claim: Claim | None
    notes: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.revised_claim is not None


def _evidence_payload(ledger: "EvidenceLedger | Any", evidence_ids: list[str]) -> list[dict[str, Any]]:
    items: dict[str, Any] = {
        str(_attr(item, "evidence_id")): item for item in (_attr(ledger, "items") or ())
    }
    payload = []
    for eid in evidence_ids:
        item = items.get(eid)
        if item is None:
            continue
        payload.append(
            {
                "evidence_id": eid,
                "normalized_fact": str(_attr(item, "normalized_fact", "")),
                "reliability": str(_attr(_attr(item, "reliability"), "value", _attr(item, "reliability"))),
                "independence_group": str(_attr(item, "independence_group", "")),
            }
        )
    return payload


@dataclass(frozen=True)
class ConditionalDebateExtension:
    """H3: at most one Bull round, one Bear round, one Judge call, only for a
    conclusion claim carrying a real material conflict. See the module
    docstring for the full design and its boundaries.
    """

    llm: Any
    max_tokens: int = DEFAULT_MAX_TOKENS
    label: str = OPT_IN_LABEL

    async def evaluate(
        self,
        ledger: "EvidenceLedger | None" = None,
        indicators: "list[ConflictIndicator] | tuple[Any, ...] | None" = None,
        context: "RunContext | None" = None,
    ) -> ConflictExtensionResult:
        """Decide only. No LLM call — mirrors `DisabledConflictExtension.evaluate()`
        exactly, so a caller that never invokes `run_debate()` sees identical
        behavior whether this class or the disabled one is wired.
        """
        indicators = tuple(indicators or ())
        enabled = bool(getattr(context, "enable_conditional_debate", False))
        if enabled and indicators:
            return ConflictExtensionResult(
                status=ACTIVE_STATUS,
                route=DEBATE_ROUTE,
                indicators=indicators,
                notes=(
                    f"material conflict found on {len(indicators)} claim(s); "
                    "conditional debate is eligible to run",
                ),
            )
        notes: list[str] = [self.label]
        if enabled:
            notes.append(
                "enable_conditional_debate=true but no material conflict was found; "
                "execution routed directly to the Arbiter result"
            )
        return ConflictExtensionResult(
            status=DISABLED_STATUS, route=ARBITER_ROUTE, indicators=indicators, notes=tuple(notes)
        )

    async def run_debate(
        self,
        *,
        claim: Claim,
        indicator: "ConflictIndicator",
        ledger: "EvidenceLedger",
        deadline: float,
    ) -> DebateOutcome:
        """Bull -> Bear -> Judge for one conclusion claim.

        Only ever called after `evaluate()` returned `route=DEBATE_ROUTE` for
        this same claim/indicator pair. Any exception at any step degrades to
        `DebateOutcome(None, notes)`; nothing here re-raises into the caller.
        """
        if claim.claim_type.value != "conclusion":
            return DebateOutcome(
                None, (f"H3 skipped: {claim.claim_id} is not a conclusion claim",)
            )

        supporting = _evidence_payload(ledger, list(indicator.supporting_evidence_ids))
        opposing = _evidence_payload(ledger, list(indicator.opposing_evidence_ids))
        if not supporting or not opposing:
            return DebateOutcome(
                None,
                (
                    f"H3 skipped for {claim.claim_id}: indicator names evidence not "
                    "present in the ledger, so a faithful debate is not possible",
                ),
            )

        try:
            bull = await self.llm.converse_structured(
                operation="debate_bull",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": self._json(
                                    {"claim_text": claim.text, "supporting_evidence": supporting}
                                )
                            }
                        ],
                    }
                ],
                schema=DebateArgument,
                max_tokens=self.max_tokens,
                deadline=deadline,
                system_prompt=load_prompt("debate_bull").body,
            )
            bear = await self.llm.converse_structured(
                operation="debate_bear",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": self._json(
                                    {"claim_text": claim.text, "opposing_evidence": opposing}
                                )
                            }
                        ],
                    }
                ],
                schema=DebateArgument,
                max_tokens=self.max_tokens,
                deadline=deadline,
                system_prompt=load_prompt("debate_bear").body,
            )
            verdict = await self.llm.converse_structured(
                operation="debate_judge",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": self._json(
                                    {
                                        "original_text": claim.text,
                                        "bull_argument": bull.argument,
                                        "bear_argument": bear.argument,
                                    }
                                )
                            }
                        ],
                    }
                ],
                schema=DebateVerdict,
                max_tokens=self.max_tokens,
                deadline=deadline,
                system_prompt=load_prompt("debate_judge").body,
            )
        except LLMError as exc:
            return DebateOutcome(
                None, (f"H3 debate failed for {claim.claim_id} ({type(exc).__name__}); kept the original claim",)
            )

        revised = claim.model_copy(
            update={
                "text": verdict.text,
                "confidence": Reliability(verdict.confidence),
                "limitations": [*claim.limitations, *verdict.limitations],
            }
        )
        notes = (
            f"H3 conditional debate revised {claim.claim_id}: {verdict.confidence_rationale}",
        )
        return DebateOutcome(revised, notes)

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False)
