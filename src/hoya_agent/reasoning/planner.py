"""Planner: turn the question into a bounded, allowlisted collection plan.

The Planner is deliberately weak. It chooses *which allowlisted operations to
run*, and nothing else: it forms no market view, and it cannot name a provider,
host, or URL that configuration did not already approve. Any plan that strays
outside the registry is discarded in favour of the deterministic default, so a
prompt injection in the question cannot widen the tool surface.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from hoya_agent.adapters.bedrock import LLMError
from hoya_agent.reasoning.prompt_library import load_prompt

DEFAULT_LOOKBACK_DAYS = 14
MIN_PLANNED_STEPS = 1
MAX_PLANNED_STEPS = 8


class PlanRejected(Exception):
    """The generated plan violated the tool allowlist or the frozen request."""


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def plan_violations(
    plan: Any, allowed_operations: Sequence[str], requested_assets: Sequence[str]
) -> list[str]:
    """Every reason the generated plan must not be executed."""
    violations: list[str] = []
    allowed = set(allowed_operations)

    steps = list(_attr(plan, "planned_steps") or ())
    if not steps:
        violations.append("plan contains no steps")
    if len(steps) > MAX_PLANNED_STEPS:
        violations.append(f"plan has {len(steps)} steps, more than {MAX_PLANNED_STEPS}")

    for step in steps:
        operation = str(_attr(step, "tool_operation", ""))
        if operation not in allowed:
            # The single most important check in this module.
            violations.append(f"step names non-allowlisted operation {operation!r}")

    planned_assets = [str(asset) for asset in (_attr(plan, "assets") or ())]
    if planned_assets != [str(asset) for asset in requested_assets]:
        violations.append(
            f"plan changed the requested assets to {planned_assets!r}"
        )

    lookback = _attr(plan, "lookback_days")
    if lookback is not None and (not isinstance(lookback, int) or lookback <= 0):
        violations.append(f"lookback_days must be a positive integer, got {lookback!r}")

    return violations


def default_plan_payload(
    *,
    assets: Sequence[str],
    allowed_operations: Sequence[str],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    reason: str = "",
) -> dict[str, Any]:
    """Deterministic plan used whenever the Planner cannot be trusted."""
    steps = [
        {
            "step_id": f"s{index}",
            "tool_operation": operation,
            "rationale": "決定論預設計畫：依允許清單順序蒐集可得證據。",
        }
        for index, operation in enumerate(allowed_operations[:MAX_PLANNED_STEPS], start=1)
    ]
    notes = ["使用決定論預設計畫。"]
    if reason:
        notes.append(reason)
    return {
        "plan_version": "deterministic-default-v1",
        "assets": [str(asset) for asset in assets],
        "question_summary": "（未使用 Planner 產出的摘要）",
        "lookback_days": lookback_days,
        "required_evidence_types": [],
        "planned_steps": steps,
        "asset_question_mismatch_warning": None,
        "notes": notes,
    }


@dataclass
class PlannerSettings:
    max_tokens: int = 2000
    default_lookback_days: int = DEFAULT_LOOKBACK_DAYS


@dataclass
class Planner:
    llm: Any
    plan_schema: type[BaseModel]
    tool_registry: Any
    settings: PlannerSettings = field(default_factory=PlannerSettings)

    @property
    def prompt_version(self) -> str:
        return load_prompt("planner").version_label

    def allowed_operations(self) -> tuple[str, ...]:
        return tuple(self.tool_registry.operations())

    async def run(
        self, *, request: Any, deadline: float
    ) -> tuple[BaseModel, list[str]]:
        """Return ``(plan, notes)``; falls back deterministically on any doubt."""
        assets = [str(asset) for asset in (_attr(request, "assets") or ())]
        operations = self.allowed_operations()
        notes: list[str] = []

        try:
            generated = await self.llm.converse_structured(
                operation="planner",
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": self._user_text(request, assets, operations)}],
                    }
                ],
                schema=self.plan_schema,
                max_tokens=self.settings.max_tokens,
                deadline=deadline,
                system_prompt=load_prompt("planner").body,
            )
        except LLMError as exc:
            notes.append(f"Planner 生成失敗（{type(exc).__name__}），改用決定論預設計畫")
            return self._default(assets, operations, str(exc)), notes

        violations = plan_violations(generated, operations, assets)
        if violations:
            notes.append("Planner 計畫違反工具允許清單或凍結請求：" + "；".join(violations[:3]))
            return self._default(assets, operations, violations[0]), notes

        warning = _attr(generated, "asset_question_mismatch_warning")
        if warning:
            notes.append(f"題目與指定幣種不一致：{warning}")
        return generated, notes

    def _user_text(
        self, request: Any, assets: Sequence[str], operations: Sequence[str]
    ) -> str:
        return json.dumps(
            {
                "question": _attr(request, "question"),
                "assets": list(assets),
                "analysis_as_of": str(_attr(request, "analysis_as_of")),
                "available_operations": list(operations),
                "default_lookback_days": self.settings.default_lookback_days,
            },
            ensure_ascii=False,
        )

    def _default(
        self, assets: Sequence[str], operations: Sequence[str], reason: str
    ) -> BaseModel:
        return self.plan_schema.model_validate(
            default_plan_payload(
                assets=assets,
                allowed_operations=operations,
                lookback_days=self.settings.default_lookback_days,
                reason=reason,
            )
        )
