"""H3 conditional-debate seam. The MVP implementation never debates.

Requirement 14 keeps H3 as an interface only. ``DisabledConflictExtension`` is
the sole implementation for Bronze, Silver, and Gold: it performs no network or
LLM call, hands the deterministic conflict indicators back untouched, and always
routes to the Arbiter. A request asking for the debate is recorded as ignored
rather than honoured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime dependency
    from hoya_agent.models import ConflictIndicator, EvidenceLedger, RunContext

#: Route value understood by the pipeline. There is no other route in MVP.
ARBITER_ROUTE = "arbiter"

#: Status surfaced to the UI and the execution log.
DISABLED_STATUS = "disabled"

#: Shown wherever the product claims a capability, so H3 is never oversold.
UNIMPLEMENTED_LABEL = "H3 conditional debate: unimplemented in this release"


@dataclass(frozen=True)
class ConflictExtensionResult:
    status: str
    route: str
    indicators: tuple[Any, ...]
    notes: tuple[str, ...] = field(default=())

    @property
    def is_disabled(self) -> bool:
        return self.status == DISABLED_STATUS


@dataclass(frozen=True)
class DisabledConflictExtension:
    """Deterministic pass-through. No Bull, no Bear, no Judge, no calls."""

    label: str = UNIMPLEMENTED_LABEL

    async def evaluate(
        self,
        ledger: EvidenceLedger | None = None,
        indicators: "list[ConflictIndicator] | tuple[Any, ...] | None" = None,
        context: RunContext | None = None,
    ) -> ConflictExtensionResult:
        notes = [self.label]
        if getattr(context, "enable_conditional_debate", False):
            # Honouring the flag would be a capability claim we cannot back.
            notes.append(
                "enable_conditional_debate=true was ignored; "
                "execution routed directly to the Arbiter"
            )
        return ConflictExtensionResult(
            status=DISABLED_STATUS,
            route=ARBITER_ROUTE,
            indicators=tuple(indicators or ()),
            notes=tuple(notes),
        )
