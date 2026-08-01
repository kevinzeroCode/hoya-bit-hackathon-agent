"""Contract tests for the Bedrock Converse boundary.

These run without AWS credentials and without the shared domain contracts: the
client is generic over any Pydantic model, so a local schema stands in.
"""

from __future__ import annotations

import asyncio
import time
import unittest

from pydantic import BaseModel, ConfigDict

from hoya_agent.adapters.bedrock import (
    STRUCTURED_TOOL_NAME,
    BedrockLLMClient,
    BedrockSettings,
    LLMSchemaError,
    LLMTimeoutError,
    LLMUnavailableError,
    build_converse_request,
    build_repair_messages,
    effective_timeout,
    extract_tool_input,
    is_retryable_error,
)


class DemoResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str
    score: int


def tool_response(payload: dict, tool_name: str = STRUCTURED_TOOL_NAME) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"name": tool_name, "input": payload}}],
            }
        }
    }


def text_response(text: str = "here is my answer") -> dict:
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}}


class ThrottlingError(Exception):
    """Stands in for botocore's ThrottlingException."""

    def __init__(self) -> None:
        super().__init__("rate exceeded")
        self.response = {"Error": {"Code": "ThrottlingException"}}


class ValidationErrorFromProvider(Exception):
    """A non-retryable provider-side 4xx."""

    def __init__(self) -> None:
        super().__init__("bad request")
        self.response = {"Error": {"Code": "ValidationException"}}


class FakeConverse:
    """Replays a queued script of responses/exceptions, recording requests."""

    def __init__(self, script, delay: float = 0.0) -> None:
        self.script = list(script)
        self.delay = delay
        self.requests: list[dict] = []

    def converse(self, **request):
        self.requests.append(request)
        if self.delay:
            time.sleep(self.delay)
        if not self.script:
            raise AssertionError("FakeConverse ran out of scripted responses")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(script, *, fallback: str | None = None, delay: float = 0.0):
    fake = FakeConverse(script, delay=delay)
    client = BedrockLLMClient(
        settings=BedrockSettings(
            region="us-east-1",
            primary_model_id="anthropic.primary",
            fallback_model_id=fallback,
        ),
        client=fake,
    )
    return client, fake


def run(client, *, deadline_in: float = 30.0, max_tokens: int = 512):
    return asyncio.run(
        client.converse_structured(
            operation="arbiter",
            messages=[{"role": "user", "content": [{"text": "分析"}]}],
            schema=DemoResult,
            max_tokens=max_tokens,
            deadline=time.monotonic() + deadline_in,
            system_prompt="SYSTEM PROMPT BODY",
        )
    )


class RequestBuildingTests(unittest.TestCase):
    def test_request_forces_the_structured_tool(self):
        request = build_converse_request(
            model_id="anthropic.primary",
            system_prompt="sys",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            json_schema=DemoResult.model_json_schema(),
            max_tokens=256,
        )
        choice = request["toolConfig"]["toolChoice"]
        self.assertEqual(choice, {"tool": {"name": STRUCTURED_TOOL_NAME}})
        self.assertEqual(request["inferenceConfig"]["maxTokens"], 256)
        tools = request["toolConfig"]["tools"]
        self.assertEqual(len(tools), 1, "exactly one tool may be offered")
        self.assertIn("properties", tools[0]["toolSpec"]["inputSchema"]["json"])
        self.assertEqual(request["system"], [{"text": "sys"}])

    def test_empty_system_prompt_is_omitted_rather_than_sent_blank(self):
        """Bedrock rejects ``system[0].text`` of length 0.

        ``converse_structured`` defaults ``system_prompt`` to "", so an
        unconditional system block makes every caller that omits it fail
        client-side with ``ParamValidationError`` before the request is sent.
        Verified against the live API: "Invalid length for parameter
        system[0].text, value: 0, valid min length: 1".
        """
        request = build_converse_request(
            model_id="anthropic.primary",
            system_prompt="",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            json_schema=DemoResult.model_json_schema(),
            max_tokens=256,
        )
        self.assertNotIn("system", request)

    def test_whitespace_only_system_prompt_is_omitted(self):
        request = build_converse_request(
            model_id="anthropic.primary",
            system_prompt="   \n\t ",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            json_schema=DemoResult.model_json_schema(),
            max_tokens=256,
        )
        self.assertNotIn("system", request)

    def test_repair_message_quotes_errors_without_dropping_history(self):
        original = [{"role": "user", "content": [{"text": "原始問題"}]}]
        repaired = build_repair_messages(original, {"score": "x"}, "score must be int")
        self.assertEqual(len(repaired), len(original) + 1)
        self.assertEqual(repaired[0], original[0])
        appended = repaired[-1]["content"][0]["text"]
        self.assertIn("score must be int", appended)
        self.assertIn("不要新增證據", appended)


class ResponseParsingTests(unittest.TestCase):
    def test_extracts_tool_input(self):
        payload = {"headline": "測試", "score": 3}
        self.assertEqual(extract_tool_input(tool_response(payload)), payload)

    def test_prose_answer_is_a_schema_error(self):
        with self.assertRaises(LLMSchemaError):
            extract_tool_input(text_response())

    def test_wrong_tool_name_is_a_schema_error(self):
        with self.assertRaises(LLMSchemaError):
            extract_tool_input(tool_response({"headline": "x", "score": 1}, "other"))

    def test_missing_output_is_a_schema_error(self):
        with self.assertRaises(LLMSchemaError):
            extract_tool_input({})


class DeadlineTests(unittest.TestCase):
    def test_timeout_is_clamped_to_the_remaining_budget(self):
        now = 100.0
        self.assertAlmostEqual(effective_timeout(now + 5.0, 45.0, now), 5.0)

    def test_timeout_never_exceeds_the_hard_cap(self):
        now = 100.0
        self.assertAlmostEqual(effective_timeout(now + 600.0, 45.0, now), 45.0)

    def test_configured_cap_above_the_hard_cap_is_ignored(self):
        now = 100.0
        self.assertAlmostEqual(effective_timeout(now + 600.0, 90.0, now), 45.0)

    def test_expired_deadline_raises_before_any_call(self):
        now = 100.0
        with self.assertRaises(LLMTimeoutError):
            effective_timeout(now - 1.0, 45.0, now)

    def test_expired_deadline_prevents_the_provider_call(self):
        client, fake = make_client([tool_response({"headline": "x", "score": 1})])
        with self.assertRaises(LLMTimeoutError):
            run(client, deadline_in=-1.0)
        self.assertEqual(fake.requests, [], "no request may be sent past the deadline")

    def test_slow_call_times_out(self):
        client, _ = make_client(
            [tool_response({"headline": "x", "score": 1})], delay=0.5
        )
        with self.assertRaises(LLMTimeoutError):
            run(client, deadline_in=0.05)


class RetryClassificationTests(unittest.TestCase):
    def test_throttling_is_retryable(self):
        self.assertTrue(is_retryable_error(ThrottlingError()))

    def test_provider_validation_error_is_not_retryable(self):
        self.assertFalse(is_retryable_error(ValidationErrorFromProvider()))

    def test_schema_error_is_never_retryable(self):
        self.assertFalse(is_retryable_error(LLMSchemaError("bad")))


class ConverseStructuredTests(unittest.TestCase):
    def test_valid_first_response_is_returned(self):
        client, fake = make_client([tool_response({"headline": "整理格局", "score": 2})])
        result = run(client)
        self.assertEqual(result.headline, "整理格局")
        self.assertEqual(len(fake.requests), 1, "a valid answer needs no repair")

    def test_invalid_payload_is_repaired_once_then_succeeds(self):
        client, fake = make_client(
            [
                tool_response({"headline": "x", "score": "not-an-int"}),
                tool_response({"headline": "修正後", "score": 4}),
            ]
        )
        result = run(client)
        self.assertEqual(result.score, 4)
        self.assertEqual(len(fake.requests), 2)
        repair_turn = fake.requests[1]["messages"][-1]["content"][0]["text"]
        self.assertIn("schema", repair_turn)

    def test_prose_answer_is_repaired_once_then_succeeds(self):
        client, _ = make_client(
            [text_response(), tool_response({"headline": "修正後", "score": 1})]
        )
        self.assertEqual(run(client).headline, "修正後")

    def test_second_invalid_payload_raises_schema_error(self):
        client, fake = make_client(
            [
                tool_response({"headline": "x", "score": "bad"}),
                tool_response({"headline": "y", "score": "still-bad"}),
            ]
        )
        with self.assertRaises(LLMSchemaError):
            run(client)
        self.assertEqual(len(fake.requests), 2, "repair is attempted at most once")

    def test_extra_fields_are_rejected(self):
        client, _ = make_client(
            [
                tool_response({"headline": "x", "score": 1, "sneaky": True}),
                tool_response({"headline": "x", "score": 1, "sneaky": True}),
            ]
        )
        with self.assertRaises(LLMSchemaError):
            run(client)


class ModelFallbackTests(unittest.TestCase):
    def test_throttling_falls_back_to_the_configured_model(self):
        client, fake = make_client(
            [ThrottlingError(), tool_response({"headline": "備援", "score": 1})],
            fallback="anthropic.fallback",
        )
        self.assertEqual(run(client).headline, "備援")
        self.assertEqual(fake.requests[0]["modelId"], "anthropic.primary")
        self.assertEqual(fake.requests[1]["modelId"], "anthropic.fallback")

    def test_fallback_is_attempted_at_most_once(self):
        client, fake = make_client(
            [ThrottlingError(), ThrottlingError()], fallback="anthropic.fallback"
        )
        with self.assertRaises(LLMUnavailableError):
            run(client)
        self.assertEqual(len(fake.requests), 2)

    def test_without_a_fallback_model_throttling_raises(self):
        client, fake = make_client([ThrottlingError()])
        with self.assertRaises(LLMUnavailableError):
            run(client)
        self.assertEqual(len(fake.requests), 1)

    def test_non_retryable_error_does_not_switch_models(self):
        client, fake = make_client(
            [ValidationErrorFromProvider()], fallback="anthropic.fallback"
        )
        with self.assertRaises(LLMUnavailableError):
            run(client)
        self.assertEqual(len(fake.requests), 1, "4xx must not burn the fallback model")

    def test_schema_failure_does_not_switch_models(self):
        client, fake = make_client(
            [
                tool_response({"headline": "x", "score": "bad"}),
                tool_response({"headline": "y", "score": "bad"}),
            ],
            fallback="anthropic.fallback",
        )
        with self.assertRaises(LLMSchemaError):
            run(client)
        self.assertEqual(
            {request["modelId"] for request in fake.requests},
            {"anthropic.primary"},
            "a bad payload is the model's fault, not the endpoint's",
        )


class SanitizedLoggingTests(unittest.TestCase):
    def test_events_record_outcomes_without_prompt_or_response_text(self):
        client, _ = make_client(
            [
                ThrottlingError(),
                tool_response({"headline": "機密內容", "score": "bad"}),
                tool_response({"headline": "機密內容", "score": 1}),
            ],
            fallback="anthropic.fallback",
        )
        run(client)
        events = client.drain_events()
        self.assertEqual(
            [event.status for event in events],
            ["retryable_error", "schema_invalid", "ok"],
        )
        self.assertTrue(events[-1].is_repair)
        self.assertTrue(events[-1].is_fallback_model)
        serialized = repr(events)
        for secret in ("SYSTEM PROMPT BODY", "分析", "機密內容"):
            self.assertNotIn(secret, serialized)

    def test_drain_clears_the_buffer(self):
        client, _ = make_client([tool_response({"headline": "x", "score": 1})])
        run(client)
        self.assertTrue(client.drain_events())
        self.assertEqual(client.drain_events(), [])


if __name__ == "__main__":
    unittest.main()
