from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.config import Settings
from hoya_agent.models import AnalysisRequest, Asset, RunMode

REQUIRED_ENV = {
    "AWS_REGION": "ap-northeast-1",
    "BEDROCK_PRIMARY_MODEL_ID": "anthropic.primary",
    "ARTIFACT_ROOT": "artifacts",
}


def request() -> AnalysisRequest:
    now = datetime(2026, 8, 1, 4, 5, tzinfo=UTC)
    return AnalysisRequest(
        question="分析 BTC 市場",
        assets=[Asset.BTC],
        requested_at=now,
        analysis_as_of=now,
        run_mode=RunMode.official,
        run_id="run_20260801_120500_test",
    )


def test_settings_parse_locked_environment_names() -> None:
    settings = Settings.from_env(
        {
            **REQUIRED_ENV,
            "BEDROCK_FALLBACK_MODEL_ID": "anthropic.fallback",
            "CRYPTOPANIC_API_TOKEN": "top-secret",
            "HTTP_CONNECT_TIMEOUT_SECONDS": "7.5",
            "HTTP_READ_TIMEOUT_SECONDS": "20",
            "MAX_EVIDENCE_FOR_ARBITER": "24",
            "LLM_CALL_TIMEOUT_SECONDS": "40",
            "ALLOW_RECORDED_DEMO_FALLBACK": "true",
            "LOG_LEVEL": "debug",
        }
    )

    assert settings.aws_region == "ap-northeast-1"
    assert settings.max_evidence_for_arbiter == 24
    assert settings.llm_call_timeout_seconds == 40
    assert settings.allow_recorded_demo_fallback is True
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("name", "value"),
    [("MAX_EVIDENCE_FOR_ARBITER", "31"), ("LLM_CALL_TIMEOUT_SECONDS", "46")],
)
def test_settings_enforce_hard_caps(name: str, value: str) -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, name: value})


def test_sanitized_snapshot_never_contains_optional_values_or_secrets() -> None:
    secret = "do-not-leak-this-token"
    fallback = "do-not-leak-this-model-id"
    settings = Settings.from_env(
        {
            **REQUIRED_ENV,
            "BEDROCK_FALLBACK_MODEL_ID": fallback,
            "CRYPTOPANIC_API_TOKEN": secret,
            "HTTP_READ_TIMEOUT_SECONDS": "33",
        }
    )

    snapshot = settings.sanitized_snapshot(request())
    payload = snapshot.model_dump_json()

    assert secret not in payload
    assert fallback not in payload
    assert "33" not in payload
    assert snapshot.optional_key_presence["CRYPTOPANIC_API_TOKEN"] is True
    assert snapshot.optional_key_presence["HTTP_CONNECT_TIMEOUT_SECONDS"] is False


def test_required_settings_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, "AWS_REGION": "  "})

