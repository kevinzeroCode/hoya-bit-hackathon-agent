"""Research Agent: run the approved plan, then extract facts once.

The agent is an executor, not an explorer. It walks the plan's steps, invokes
only operations the static registry already allows, and makes exactly one
bounded extraction call over whatever it collected. There is no free loop, no
follow-up fetch decided by the model, and no path by which retrieved content can
add an operation to the registry.

Retrieved text is treated as data throughout. A record that tells the model to
ignore its instructions is extracted like any other record and flagged.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from hoya_agent.adapters.bedrock import LLMError
from hoya_agent.reasoning.prompt_library import load_prompt

#: Substrings that mark a record as carrying instruction-like text. Presence
#: never changes behaviour; it only adds a disclosure note.
INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard the above",
    "you are now",
    "system prompt",
    "忽略先前",
    "忽略以上",
    "你現在是",
)

STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def looks_like_injection(text: Any) -> bool:
    """True when a record contains instruction-like text worth disclosing."""
    if not text:
        return False
    lowered = str(text).lower()
    return any(marker in lowered for marker in INJECTION_MARKERS)


@dataclass
class ResearchOutcome:
    """What the Research Agent hands back to the pipeline."""

    status: str
    drafts: list[Any] = field(default_factory=list)
    records: list[Any] = field(default_factory=list)
    degradation_events: list[str] = field(default_factory=list)
    executed_operations: list[str] = field(default_factory=list)


@dataclass
class ResearchSettings:
    max_tokens: int = 6000
    max_records: int = 40


@dataclass
class ResearchAgent:
    llm: Any
    draft_schema: type[BaseModel]
    tool_registry: Any
    settings: ResearchSettings = field(default_factory=ResearchSettings)

    @property
    def prompt_version(self) -> str:
        return load_prompt("research_extraction").version_label

    async def run(
        self, *, plan: Any, request: Any, deadline: float
    ) -> ResearchOutcome:
        """Execute the plan's allowlisted steps, then extract once."""
        outcome = ResearchOutcome(status=STATUS_COMPLETED)
        allowed = set(self.tool_registry.operations())

        for step in _attr(plan, "planned_steps") or ():
            operation = str(_attr(step, "tool_operation", ""))
            # Re-checked here even though the Planner already validated: the
            # registry is the authority, and this is the last gate before I/O.
            if operation not in allowed or not self.tool_registry.is_allowed(operation):
                outcome.degradation_events.append(
                    f"略過非允許清單操作 {operation!r}"
                )
                outcome.status = STATUS_PARTIAL
                continue
            try:
                records = await self.tool_registry.invoke(
                    operation,
                    assets=[str(a) for a in (_attr(request, "assets") or ())],
                    lookback_days=_attr(plan, "lookback_days"),
                    analysis_as_of=_attr(request, "analysis_as_of"),
                )
            except Exception as exc:  # noqa: BLE001 - adapter failures are data
                outcome.degradation_events.append(
                    f"操作 {operation} 失敗（{type(exc).__name__}），該來源缺漏"
                )
                outcome.status = STATUS_PARTIAL
                continue
            outcome.executed_operations.append(operation)
            outcome.records.extend(records or ())

        # Registry immutability is a contract, not an aspiration.
        if set(self.tool_registry.operations()) != allowed:
            raise RuntimeError("tool registry mutated during research execution")

        if not outcome.records:
            outcome.degradation_events.append("研究分支未取得任何來源紀錄")
            outcome.status = (
                STATUS_FAILED if not outcome.executed_operations else STATUS_PARTIAL
            )
            return outcome

        flagged = [
            str(_attr(record, "record_id"))
            for record in outcome.records
            if looks_like_injection(_attr(record, "content"))
            or looks_like_injection(_attr(record, "title"))
        ]
        if flagged:
            outcome.degradation_events.append(
                "下列來源含疑似指令式文字，已作為引用資料處理："
                + ", ".join(sorted(flagged))
            )

        records = outcome.records[: self.settings.max_records]
        if len(records) < len(outcome.records):
            outcome.degradation_events.append(
                f"來源紀錄自 {len(outcome.records)} 筆截斷為 {len(records)} 筆"
            )

        try:
            extracted = await self.llm.converse_structured(
                operation="research_extraction",
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": self._user_text(records, request)}],
                    }
                ],
                schema=self.draft_schema,
                max_tokens=self.settings.max_tokens,
                deadline=deadline,
                system_prompt=load_prompt("research_extraction").body,
            )
        except LLMError as exc:
            outcome.degradation_events.append(
                f"研究抽取失敗（{type(exc).__name__}），保留原始紀錄但無 Evidence draft"
            )
            outcome.status = STATUS_PARTIAL
            return outcome

        known_ids = {str(_attr(record, "record_id")) for record in records}
        drafts = []
        for draft in _attr(extracted, "drafts") or ():
            record_id = str(_attr(draft, "record_id"))
            if record_id not in known_ids:
                # A draft citing a record we never fetched is a fabricated fact.
                outcome.degradation_events.append(
                    f"捨棄引用不存在紀錄 {record_id!r} 的抽取結果"
                )
                outcome.status = STATUS_PARTIAL
                continue
            drafts.append(draft)
        outcome.drafts = drafts
        if not drafts:
            outcome.status = STATUS_PARTIAL
        return outcome

    def _user_text(self, records: Sequence[Any], request: Any) -> str:
        return json.dumps(
            {
                "assets": [str(a) for a in (_attr(request, "assets") or ())],
                "analysis_as_of": str(_attr(request, "analysis_as_of")),
                "records": [
                    {
                        "record_id": _attr(record, "record_id"),
                        "source_name": _attr(record, "source_name"),
                        "source_url": _attr(record, "source_url"),
                        "source_type": _attr(record, "source_type"),
                        "published_at": str(_attr(record, "published_at") or ""),
                        "title": _attr(record, "title"),
                        "content": _attr(record, "content"),
                    }
                    for record in records
                ],
            },
            ensure_ascii=False,
        )
