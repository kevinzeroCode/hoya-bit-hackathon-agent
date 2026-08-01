"""Tests for BedrockClient — uses an injected fake bedrock-runtime client (no boto3, no network)."""

from __future__ import annotations

import json

import pytest

from reasoning.bedrock_client import BedrockClient
from reasoning.research_extractor import NewsRecord, extract_news_facts

_GOOD = '{"relevant": true, "event_type": "etf_flow", "facts": ["現貨 BTC ETF 淨流入創高"]}'


class _FakeBody:
    def __init__(self, data: dict) -> None:
        self._raw = json.dumps(data).encode("utf-8")

    def read(self) -> bytes:
        return self._raw


class _FakeBedrock:
    """Mimics boto3 bedrock-runtime: invoke_model(modelId=, body=) -> {'body': stream}."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.last_body: dict | None = None
        self.last_model: str | None = None

    def invoke_model(self, *, modelId: str, body: str):
        self.last_model = modelId
        self.last_body = json.loads(body)
        return {"body": _FakeBody({"content": [{"type": "text", "text": self._text}]})}


def test_requires_model_id(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    with pytest.raises(ValueError):
        BedrockClient(client=_FakeBedrock("x"))


def test_complete_sends_messages_body_and_returns_text():
    fake = _FakeBedrock(_GOOD)
    llm = BedrockClient(model_id="anthropic.claude-x", client=fake)
    out = llm.complete(system="you are analyst", user="headline text")
    assert out == _GOOD
    assert fake.last_model == "anthropic.claude-x"
    assert fake.last_body["anthropic_version"] == "bedrock-2023-05-31"
    assert fake.last_body["system"] == "you are analyst"
    assert fake.last_body["messages"][0] == {"role": "user", "content": "headline text"}
    assert fake.last_body["max_tokens"] > 0


def test_concatenates_multiple_text_blocks():
    class _MultiBlock(_FakeBedrock):
        def invoke_model(self, *, modelId, body):
            return {"body": _FakeBody({"content": [
                {"type": "text", "text": "A"}, {"type": "text", "text": "B"},
            ]})}

    llm = BedrockClient(model_id="m", client=_MultiBlock(""))
    assert llm.complete(system="s", user="u") == "AB"


def test_satisfies_llmclient_in_the_extractor():
    # Proves BedrockClient is a drop-in for the news extractor (same as GptClient/FakeLLM).
    fake = _FakeBedrock(_GOOD)
    llm = BedrockClient(model_id="m", client=fake)
    from datetime import datetime, timezone
    rec = NewsRecord(asset="BTC", title="Bitcoin ETF sees record inflows", body="<p>...</p>",
                     source_name="CoinDesk", publisher_domain="coindesk.com",
                     source_url="https://x", published_at=datetime(2026, 5, 30, tzinfo=timezone.utc))
    result = extract_news_facts([rec], llm=llm)
    assert result.status == "completed"
    assert result.drafts and result.drafts[0].reliability == "low"
