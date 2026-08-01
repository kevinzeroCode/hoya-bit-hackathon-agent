"""Amazon Bedrock Converse boundary for bounded, schema-validated LLM calls.

This module is the only place in the package that talks to Bedrock. It is
generic over the Pydantic result model, so it carries no dependency on the
shared domain contracts and can be exercised in isolation.

Contract highlights enforced here:

- structured output only, obtained through a single forced tool call;
- at most one schema repair attempt, inside the caller's stage deadline;
- per-call timeout clamped to the remaining stage budget, never above the cap;
- model fallback only for retryable availability/throttling failures;
- no prompt text, credential, or model reasoning is ever recorded.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)

#: Name of the synthetic tool used to force structured output.
STRUCTURED_TOOL_NAME = "emit_structured_result"

#: Hard ceiling for a single provider call, per design.md 6.2.
MAX_CALL_TIMEOUT_SECONDS = 45.0

#: Botocore error codes that justify one retry or a fallback model.
RETRYABLE_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "TooManyRequestsException",
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelNotReadyException",
        "ModelTimeoutException",
    }
)


class LLMError(Exception):
    """Base class for every failure that should trigger deterministic fallback."""


class LLMSchemaError(LLMError):
    """Structured output could not be validated, including after one repair."""


class LLMTimeoutError(LLMError):
    """The stage deadline was reached before a usable response arrived."""


class LLMUnavailableError(LLMError):
    """The provider was unreachable, throttled, or returned a server error."""


@dataclass(frozen=True)
class CallEvent:
    """Sanitized record of one provider attempt, for the execution log.

    Deliberately carries no prompt text, no response text, and no credentials.
    """

    operation: str
    model_id: str
    attempt: int
    status: str
    duration_ms: int
    error_category: str | None = None
    is_repair: bool = False
    is_fallback_model: bool = False


@dataclass(frozen=True)
class BedrockSettings:
    region: str
    primary_model_id: str
    fallback_model_id: str | None = None
    call_timeout_seconds: float = MAX_CALL_TIMEOUT_SECONDS

    def resolved_timeout(self) -> float:
        return min(self.call_timeout_seconds, MAX_CALL_TIMEOUT_SECONDS)


def remaining_seconds(deadline: float, now: float | None = None) -> float:
    """Seconds left until ``deadline`` on the ``time.monotonic()`` clock."""
    current = time.monotonic() if now is None else now
    return deadline - current


def effective_timeout(
    deadline: float, cap: float = MAX_CALL_TIMEOUT_SECONDS, now: float | None = None
) -> float:
    """Clamp a single call to both the per-call cap and the remaining budget.

    Raises:
        LLMTimeoutError: if the stage deadline has already passed.
    """
    remaining = remaining_seconds(deadline, now)
    if remaining <= 0:
        raise LLMTimeoutError("stage deadline reached before the call started")
    return min(cap, MAX_CALL_TIMEOUT_SECONDS, remaining)


def error_code_of(exc: BaseException) -> str | None:
    """Best-effort botocore error code extraction without importing botocore."""
    response = getattr(exc, "response", None)
    if isinstance(response, Mapping):
        error = response.get("Error")
        if isinstance(error, Mapping):
            code = error.get("Code")
            if isinstance(code, str):
                return code
    return None


def is_retryable_error(exc: BaseException) -> bool:
    """True when a different attempt could plausibly succeed.

    Schema problems are never retryable here: they are handled by the single
    repair attempt, not by re-sending the same request.
    """
    if isinstance(exc, (LLMSchemaError, asyncio.CancelledError)):
        return False
    code = error_code_of(exc)
    if code is not None:
        return code in RETRYABLE_ERROR_CODES
    return isinstance(exc, (TimeoutError, ConnectionError))


def build_converse_request(
    *,
    model_id: str,
    system_prompt: str,
    messages: Sequence[Mapping[str, Any]],
    json_schema: Mapping[str, Any],
    max_tokens: int,
    tool_name: str = STRUCTURED_TOOL_NAME,
) -> dict[str, Any]:
    """Build a Converse request that forces one structured tool call.

    An empty or whitespace-only ``system_prompt`` is omitted entirely: Bedrock
    requires ``system[0].text`` to be at least one character, so sending a blank
    block fails botocore's client-side validation before the request is sent.
    """
    request: dict[str, Any] = {
        "modelId": model_id,
        "messages": [dict(message) for message in messages],
        "inferenceConfig": {"maxTokens": max_tokens},
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": tool_name,
                        "description": (
                            "Return the analysis payload. This is the only "
                            "permitted way to answer."
                        ),
                        "inputSchema": {"json": dict(json_schema)},
                    }
                }
            ],
            "toolChoice": {"tool": {"name": tool_name}},
        },
    }
    if system_prompt.strip():
        request["system"] = [{"text": system_prompt}]
    return request


def extract_tool_input(
    response: Mapping[str, Any], tool_name: str = STRUCTURED_TOOL_NAME
) -> dict[str, Any]:
    """Pull the forced tool call's input out of a Converse response.

    Raises:
        LLMSchemaError: when the model answered with prose instead of the tool,
            or named a different tool.
    """
    output = response.get("output")
    if not isinstance(output, Mapping):
        raise LLMSchemaError("Converse response carried no output")
    message = output.get("message")
    if not isinstance(message, Mapping):
        raise LLMSchemaError("Converse response carried no message")
    for block in message.get("content") or ():
        if not isinstance(block, Mapping):
            continue
        tool_use = block.get("toolUse")
        if isinstance(tool_use, Mapping) and tool_use.get("name") == tool_name:
            tool_input = tool_use.get("input")
            if isinstance(tool_input, Mapping):
                return dict(tool_input)
            raise LLMSchemaError("tool call input was not a JSON object")
    raise LLMSchemaError(f"no {tool_name} tool call in the response")


def build_repair_messages(
    original: Sequence[Mapping[str, Any]],
    rejected_payload: Mapping[str, Any],
    errors: str,
) -> list[dict[str, Any]]:
    """Append one corrective turn describing why the previous payload failed."""
    repaired = [dict(message) for message in original]
    repaired.append(
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "你上一次的輸出未通過 schema 驗證，因此已被丟棄。\n\n"
                        "被拒絕的內容：\n"
                        f"{json.dumps(dict(rejected_payload), ensure_ascii=False)}\n\n"
                        "驗證錯誤：\n"
                        f"{errors}\n\n"
                        "請只修正這些錯誤後重新輸出完整結果。不要改變事實內容、"
                        "不要新增證據，也不要加入任何說明文字。"
                    )
                }
            ],
        }
    )
    return repaired


@dataclass
class BedrockLLMClient:
    """Thin async wrapper over the synchronous Bedrock Converse client."""

    settings: BedrockSettings
    client: Any = None
    events: list[CallEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.client is None:
            import boto3  # imported lazily so offline tests need no AWS setup

            self.client = boto3.client(
                "bedrock-runtime", region_name=self.settings.region
            )

    def drain_events(self) -> list[CallEvent]:
        """Hand accumulated sanitized call records to the caller and reset."""
        drained = list(self.events)
        self.events.clear()
        return drained

    async def converse_structured(
        self,
        *,
        operation: str,
        messages: Sequence[Mapping[str, Any]],
        schema: type[ModelT],
        max_tokens: int,
        deadline: float,
        system_prompt: str = "",
    ) -> ModelT:
        """Return one schema-valid result, or raise a typed ``LLMError``.

        Order of attempts: primary model, then one repair turn if the payload
        failed validation, then the fallback model only if the failure was a
        retryable availability problem.
        """
        json_schema = schema.model_json_schema()
        model_id = self.settings.primary_model_id
        used_fallback = False
        attempt = 0

        current_messages: list[Mapping[str, Any]] = list(messages)
        repair_used = False

        while True:
            attempt += 1
            request = build_converse_request(
                model_id=model_id,
                system_prompt=system_prompt,
                messages=current_messages,
                json_schema=json_schema,
                max_tokens=max_tokens,
            )
            timeout = effective_timeout(deadline, self.settings.resolved_timeout())
            started = time.monotonic()

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self.client.converse, **request), timeout
                )
            except asyncio.TimeoutError as exc:
                self._record(
                    operation, model_id, attempt, "timeout", started, "timeout",
                    is_repair=repair_used, is_fallback_model=used_fallback,
                )
                raise LLMTimeoutError(
                    f"{operation} exceeded its {timeout:.1f}s call budget"
                ) from exc
            except Exception as exc:  # noqa: BLE001 - normalized into typed errors
                retryable = is_retryable_error(exc)
                self._record(
                    operation, model_id, attempt,
                    "retryable_error" if retryable else "error",
                    started, error_code_of(exc) or type(exc).__name__,
                    is_repair=repair_used, is_fallback_model=used_fallback,
                )
                fallback = self.settings.fallback_model_id
                if retryable and fallback and not used_fallback:
                    # Only availability failures earn a second model; schema
                    # problems must never silently switch models.
                    if remaining_seconds(deadline) <= 0:
                        raise LLMTimeoutError(
                            f"{operation} ran out of budget before fallback"
                        ) from exc
                    model_id = fallback
                    used_fallback = True
                    continue
                raise LLMUnavailableError(
                    f"{operation} call failed: {error_code_of(exc) or type(exc).__name__}"
                ) from exc

            try:
                payload = extract_tool_input(response)
                validated = schema.model_validate(payload)
            except (LLMSchemaError, ValidationError) as exc:
                self._record(
                    operation, model_id, attempt, "schema_invalid", started,
                    "schema_invalid", is_repair=repair_used,
                    is_fallback_model=used_fallback,
                )
                if repair_used:
                    raise LLMSchemaError(
                        f"{operation} output invalid after one repair attempt"
                    ) from exc
                if remaining_seconds(deadline) <= 0:
                    raise LLMTimeoutError(
                        f"{operation} had no budget left for a repair attempt"
                    ) from exc
                repair_used = True
                current_messages = build_repair_messages(
                    messages,
                    payload if isinstance(exc, ValidationError) else {},
                    str(exc),
                )
                continue

            self._record(
                operation, model_id, attempt, "ok", started,
                is_repair=repair_used, is_fallback_model=used_fallback,
            )
            return validated

    def _record(
        self,
        operation: str,
        model_id: str,
        attempt: int,
        status: str,
        started: float,
        error_category: str | None = None,
        *,
        is_repair: bool = False,
        is_fallback_model: bool = False,
    ) -> None:
        self.events.append(
            CallEvent(
                operation=operation,
                model_id=model_id,
                attempt=attempt,
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_category=error_category,
                is_repair=is_repair,
                is_fallback_model=is_fallback_model,
            )
        )
