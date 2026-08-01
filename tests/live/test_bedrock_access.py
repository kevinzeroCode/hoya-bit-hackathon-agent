"""Live Bedrock access: the one call that has never happened through this code path.

S0 proved the account can reach a model via `invoke_model`. This suite proves the
*shipped* path: `adapters/bedrock.py` → Converse → forced `toolConfig` → a
schema-valid Pydantic model. Those are different code paths, and only this one is
used by the run.

Manual only:

    $env:RUN_LIVE_TESTS = "1"
    python -m pytest tests/live -m live -vv -s

Costs a few tokens per test. Never records credentials, request headers, or full
prompts — only model id, latency and attempt count, exactly as the execution log
contract allows.
"""

from __future__ import annotations

import os

import pytest

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings, LLMError
from hoya_agent.reasoning.arbiter_output import ArbiterOutput

pytestmark = pytest.mark.live

REGION = os.environ.get("AWS_REGION", "us-west-2")
PRIMARY = os.environ.get("BEDROCK_PRIMARY_MODEL_ID", "")
FALLBACK = os.environ.get("BEDROCK_FALLBACK_MODEL_ID") or None

# Deadline in `time.monotonic()` terms; generous because this is a manual probe,
# still bounded by the adapter's own 45-second cap.
def _deadline() -> float:
    import time

    return time.monotonic() + 40.0


def _client(model_id: str) -> BedrockLLMClient:
    return BedrockLLMClient(
        settings=BedrockSettings(region=REGION, primary_model_id=model_id)
    )


def _requires_model(model_id: str) -> None:
    if not model_id:
        pytest.skip("BEDROCK_PRIMARY_MODEL_ID is not configured")


async def test_primary_model_returns_a_schema_valid_arbiter_output() -> None:
    """The Silver-relevant probe: real Converse, forced tool use, validated model."""
    _requires_model(PRIMARY)
    client = _client(PRIMARY)

    result = await client.converse_structured(
        operation="arbiter",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            "Evidence: ev_001 — BTC's 14-day return was -4.88% through "
                            "2026-05-31 UTC (organizer daily OHLCV, reliability high).\n"
                            "Produce one fact claim cl_001 citing ev_001 with stance "
                            "supports, answer in Traditional Chinese, and give no "
                            "buy/sell advice."
                        )
                    }
                ],
            }
        ],
        schema=ArbiterOutput,
        max_tokens=2000,
        deadline=_deadline(),
        system_prompt=(
            "You are a cautious crypto market analyst. Use only the supplied evidence. "
            "Cite evidence ids. Never give investment advice."
        ),
    )

    assert isinstance(result, ArbiterOutput)
    assert result.direct_answer.strip()
    assert result.confidence in ("high", "medium", "low")
    # Anything the model claims must cite evidence that was actually supplied.
    for link in result.claim_evidence_links:
        assert link.evidence_id == "ev_001"

    events = client.drain_events()
    assert events, "each call must leave a sanitized execution record"
    recorded = " ".join(str(event) for event in events)
    for secret_marker in ("aws_access_key", "Authorization", "auth_token"):
        assert secret_marker not in recorded


async def test_call_events_carry_model_and_latency_but_no_prompt_text() -> None:
    _requires_model(PRIMARY)
    client = _client(PRIMARY)

    await client.converse_structured(
        operation="arbiter",
        messages=[{"role": "user", "content": [{"text": "Evidence: ev_001 — BTC fell."}]}],
        schema=ArbiterOutput,
        max_tokens=800,
        deadline=_deadline(),
        system_prompt="Answer in Traditional Chinese. Cite ev_001. No advice.",
    )

    event = client.drain_events()[0]
    assert getattr(event, "model_id", "") == PRIMARY
    assert getattr(event, "latency_ms", 0) >= 0
    rendered = str(event)
    assert "Evidence: ev_001" not in rendered, "prompt bodies must never be logged"


@pytest.mark.skipif(not FALLBACK, reason="BEDROCK_FALLBACK_MODEL_ID is not configured")
async def test_optional_fallback_model_is_reachable() -> None:
    """Probed independently; unavailability must not block Bronze or Silver."""
    client = _client(FALLBACK or "")

    try:
        result = await client.converse_structured(
            operation="arbiter",
            messages=[{"role": "user", "content": [{"text": "Evidence: ev_001 — BTC fell."}]}],
            schema=ArbiterOutput,
            max_tokens=800,
            deadline=_deadline(),
            system_prompt="Answer in Traditional Chinese. Cite ev_001. No advice.",
        )
    except LLMError as exc:
        pytest.skip(f"fallback model unavailable, which is non-blocking: {type(exc).__name__}")
    assert isinstance(result, ArbiterOutput)
