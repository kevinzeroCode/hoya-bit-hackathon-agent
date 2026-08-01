"""Provider-agnostic LLM boundary.

Everything that needs an LLM depends only on the `LLMClient` protocol below, so
the provider is a one-line swap at the call site:

    llm = FakeLLMClient(...)      # tests (no network)
    llm = GptClient(...)          # temporary mock during local dev
    llm = BedrockClient(...)      # production — anthropic.claude-* on Amazon Bedrock

Only `complete(system, user) -> str` crosses this boundary; the caller parses and
validates the returned text. No provider-specific types leak past here.

Production note (Amazon Bedrock — the competition target):
    See `reasoning/bedrock_client.py` → `BedrockClient` (boto3 `bedrock-runtime`
    `invoke_model`; model id + region from env; standard AWS credential chain).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


class FakeLLMClient:
    """Deterministic stand-in for tests. Pass a fixed string or a function."""

    def __init__(self, response: str | Callable[[str, str], str]) -> None:
        self._response = response

    def complete(self, *, system: str, user: str) -> str:
        if callable(self._response):
            return self._response(system, user)
        return self._response
