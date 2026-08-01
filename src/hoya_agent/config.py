"""Single environment parsing boundary and sanitized run snapshots."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hoya_agent.models import AnalysisRequest, RunConfigSnapshot

OPTIONAL_ENV_NAMES = (
    "BEDROCK_FALLBACK_MODEL_ID",
    "CRYPTOPANIC_API_TOKEN",
    "HTTP_CONNECT_TIMEOUT_SECONDS",
    "HTTP_READ_TIMEOUT_SECONDS",
    "MAX_EVIDENCE_FOR_ARBITER",
    "LLM_CALL_TIMEOUT_SECONDS",
    "ALLOW_RECORDED_DEMO_FALLBACK",
    "LOG_LEVEL",
)


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"required environment variable {name} is missing or blank")
    return value


def _optional_text(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _float_value(env: Mapping[str, str], name: str, default: float, hard_max: float | None = None) -> float:
    raw = _optional_text(env, name)
    value = default if raw is None else float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    if hard_max is not None and value > hard_max:
        raise ValueError(f"{name} must not exceed {hard_max:g}")
    return value


def _int_value(env: Mapping[str, str], name: str, default: int, hard_max: int | None = None) -> int:
    raw = _optional_text(env, name)
    value = default if raw is None else int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    if hard_max is not None and value > hard_max:
        raise ValueError(f"{name} must not exceed {hard_max}")
    return value


def _bool_value(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _optional_text(env, name)
    if raw is None:
        return default
    normalized = raw.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aws_region: str
    bedrock_primary_model_id: str
    artifact_root: Path
    bedrock_fallback_model_id: str | None = None
    cryptopanic_api_token: str | None = None
    http_connect_timeout_seconds: float = 5.0
    http_read_timeout_seconds: float = 20.0
    max_evidence_for_arbiter: int = 30
    llm_call_timeout_seconds: float = 45.0
    allow_recorded_demo_fallback: bool = False
    log_level: str = "INFO"
    max_question_length: int = 2000
    clock_tolerance_seconds: float = 5.0
    optional_key_presence: dict[str, bool] = Field(
        default_factory=lambda: {name: False for name in OPTIONAL_ENV_NAMES}
    )

    @field_validator("aws_region", "bedrock_primary_model_id")
    @classmethod
    def _required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("required setting must not be blank")
        return stripped

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")
        return normalized

    @field_validator("max_evidence_for_arbiter")
    @classmethod
    def _evidence_cap(cls, value: int) -> int:
        if not 1 <= value <= 30:
            raise ValueError("MAX_EVIDENCE_FOR_ARBITER must be in [1, 30]")
        return value

    @field_validator("llm_call_timeout_seconds")
    @classmethod
    def _llm_timeout_cap(cls, value: float) -> float:
        if not 0 < value <= 45:
            raise ValueError("LLM_CALL_TIMEOUT_SECONDS must be in (0, 45]")
        return value

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            aws_region=_required(source, "AWS_REGION"),
            bedrock_primary_model_id=_required(source, "BEDROCK_PRIMARY_MODEL_ID"),
            artifact_root=Path(_required(source, "ARTIFACT_ROOT")),
            bedrock_fallback_model_id=_optional_text(source, "BEDROCK_FALLBACK_MODEL_ID"),
            cryptopanic_api_token=_optional_text(source, "CRYPTOPANIC_API_TOKEN"),
            http_connect_timeout_seconds=_float_value(source, "HTTP_CONNECT_TIMEOUT_SECONDS", 5.0),
            http_read_timeout_seconds=_float_value(source, "HTTP_READ_TIMEOUT_SECONDS", 20.0),
            max_evidence_for_arbiter=_int_value(source, "MAX_EVIDENCE_FOR_ARBITER", 30, 30),
            llm_call_timeout_seconds=_float_value(source, "LLM_CALL_TIMEOUT_SECONDS", 45.0, 45.0),
            allow_recorded_demo_fallback=_bool_value(source, "ALLOW_RECORDED_DEMO_FALLBACK", False),
            log_level=_optional_text(source, "LOG_LEVEL") or "INFO",
            optional_key_presence={name: bool(_optional_text(source, name)) for name in OPTIONAL_ENV_NAMES},
        )

    def validate_request(self, request: AnalysisRequest) -> None:
        if len(request.question) > self.max_question_length:
            raise ValueError(f"question must not exceed {self.max_question_length} characters")

    def sanitized_snapshot(self, request: AnalysisRequest) -> RunConfigSnapshot:
        self.validate_request(request)
        return RunConfigSnapshot(
            run_id=request.run_id,
            prompt_version="unknown",
            policy_version="unknown",
            requested_run_mode=request.run_mode,
            effective_run_mode=request.run_mode,
            sanitized_request={
                "question": request.question,
                "assets": [asset.value for asset in request.assets],
            },
            analysis_as_of=request.analysis_as_of,
            deadline_seconds=request.deadline_seconds,
            configured_sources=["organizer_csv", "baseline_research", "bedrock"],
            optional_keys_present=dict(self.optional_key_presence),
        )
