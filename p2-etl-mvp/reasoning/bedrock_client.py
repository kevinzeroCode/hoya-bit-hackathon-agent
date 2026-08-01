"""Amazon Bedrock implementation of LLMClient — the competition target.

Calls Claude on Bedrock via boto3 `bedrock-runtime` `invoke_model` with the
Anthropic Messages request body. Auth uses the **standard AWS credential chain**,
so nothing is hard-coded — any of these work without code changes:
  - a Bedrock API key   → env `AWS_BEARER_TOKEN_BEDROCK`
  - workshop temp creds → env `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`
  - an EC2 IAM role     → instance profile (nothing to set)

Model id and region come from the environment; swap `GptClient` → `BedrockClient`
at the call site (both satisfy `LLMClient`).

    $env:AWS_REGION       = "us-west-2"
    $env:BEDROCK_MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"   # from 模型目錄
    $env:AWS_BEARER_TOKEN_BEDROCK = "..."        # or use IAM role / temp creds

`boto3` is a declared runtime dependency; it is imported lazily so tests (which
inject a fake client) never require it or the network.
"""

from __future__ import annotations

import json
import os

_ANTHROPIC_VERSION = "bedrock-2023-05-31"


class BedrockClient:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        region: str | None = None,
        max_tokens: int = 1024,
        timeout: float = 45.0,
        client=None,  # inject a fake bedrock-runtime client in tests
    ) -> None:
        self._model_id = model_id or os.getenv("BEDROCK_MODEL_ID")
        if not self._model_id:
            raise ValueError(
                "model_id required: pass model_id=... or set BEDROCK_MODEL_ID "
                "(copy the Claude model id from Bedrock 模型目錄)"
            )
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            import boto3  # lazy: not needed for tests
            from botocore.config import Config

            resolved_region = (
                region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2"
            )
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=resolved_region,
                config=Config(
                    read_timeout=timeout, connect_timeout=10,
                    retries={"max_attempts": 2, "mode": "standard"},  # ≤1 retry
                ),
            )

    def complete(self, *, system: str, user: str) -> str:
        body = {
            "anthropic_version": _ANTHROPIC_VERSION,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        resp = self._client.invoke_model(modelId=self._model_id, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        return "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
