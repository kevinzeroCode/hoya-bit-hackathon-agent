"""Opt-in Bedrock Converse structured-output gate for Silver."""

from __future__ import annotations

import os
import time
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings

pytestmark = pytest.mark.live

if os.getenv("RUN_LIVE_TESTS") != "1":
    pytest.skip("set RUN_LIVE_TESTS=1 to run live Silver checks", allow_module_level=True)


class BedrockSmokeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    summary_zh_hant: str = Field(min_length=2)


async def test_bedrock_converse_returns_schema_valid_structured_output() -> None:
    model_id = os.environ.get("BEDROCK_PRIMARY_MODEL_ID", "").strip()
    if not model_id:
        pytest.fail("BEDROCK_PRIMARY_MODEL_ID is required for the Silver live gate")
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-west-2"
    )
    client = BedrockLLMClient(
        BedrockSettings(
            region=region,
            primary_model_id=model_id,
            fallback_model_id=os.environ.get("BEDROCK_FALLBACK_MODEL_ID") or None,
            call_timeout_seconds=45.0,
        )
    )

    result = await client.converse_structured(
        operation="silver_bedrock_access",
        system_prompt=(
            "你是連線驗收器。必須呼叫指定工具並輸出 status='ok'，"
            "summary_zh_hant 使用繁體中文簡述連線成功。"
        ),
        messages=[
            {
                "role": "user",
                "content": [{"text": "執行一次 schema-valid Silver 連線驗收。"}],
            }
        ],
        schema=BedrockSmokeResult,
        max_tokens=256,
        deadline=time.monotonic() + 45.0,
    )

    assert result.status == "ok"
    assert result.summary_zh_hant
    events = client.drain_events()
    assert events
    assert events[-1].status == "ok"
    assert all(event.model_id for event in events)
