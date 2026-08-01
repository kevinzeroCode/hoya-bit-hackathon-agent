"""OpenAI GPT implementation of LLMClient — TEMPORARY dev mock only.

Reads OPENAI_API_KEY from the environment automatically (never hard-code the key).
This is a local-testing stand-in; the competition target is Bedrock (Claude) —
see the BedrockClient skeleton in llm_client.py. Swapping is a one-line change at
the call site because both satisfy the LLMClient interface.
"""

from __future__ import annotations

from openai import OpenAI


class GptClient:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._client = OpenAI()  # picks up OPENAI_API_KEY from the environment
        self._model = model

    def complete(self, *, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""
