"""Single environment parsing boundary and sanitized run snapshots."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from hoya_agent.models import (
    AnalysisRequest,
    DataMode,
    RunConfigSnapshot,
    RunMode,
    TerminalState,
)

OPTIONAL_ENV_NAMES = (
    "BEDROCK_FALLBACK_MODEL_ID",
    "CRYPTOPANIC_API_TOKEN",
    "HTTP_CONNECT_TIMEOUT_SECONDS",
    "HTTP_READ_TIMEOUT_SECONDS",
    "MAX_EVIDENCE_FOR_ARBITER",
    "LLM_CALL_TIMEOUT_SECONDS",
    "ALLOW_RECORDED_DEMO_FALLBACK",
    "LOG_LEVEL",
    "MAX_QUESTION_LENGTH",
    "CLOCK_TOLERANCE_SECONDS",
)

#: Arbiter input window, per requirements.md AC 6.5.
MIN_EVIDENCE_FOR_ARBITER = 20
MAX_EVIDENCE_FOR_ARBITER_LIMIT = 30

#: Question length bound, per evidence-contracts.md §2.
MIN_QUESTION_LENGTH = 50
MAX_QUESTION_LENGTH_LIMIT = 2000

#: Clock tolerance bound, per evidence-contracts.md §3.
MIN_CLOCK_TOLERANCE_SECONDS = 0
MAX_CLOCK_TOLERANCE_SECONDS = 300


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


def _bounded_int(
    env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int
) -> int:
    """Parse an integer that must sit inside an inclusive range.

    Separate from :func:`_int_value` because a legitimate configured value here
    may be zero (clock tolerance), which a positivity check would reject.
    """
    raw = _optional_text(env, name)
    value = default if raw is None else int(raw)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be within {minimum}..{maximum} inclusive")
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
    cryptopanic_api_token: SecretStr | None = None
    http_connect_timeout_seconds: float = 5.0
    http_read_timeout_seconds: float = 20.0
    max_evidence_for_arbiter: int = 30
    llm_call_timeout_seconds: float = 45.0
    allow_recorded_demo_fallback: bool = False
    log_level: str = "INFO"
    max_question_length: int = 500
    clock_tolerance_seconds: int = 60
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
        # requirements.md AC 6.5 fixes the Arbiter input window at 20..30.
        if not MIN_EVIDENCE_FOR_ARBITER <= value <= MAX_EVIDENCE_FOR_ARBITER_LIMIT:
            raise ValueError(
                "MAX_EVIDENCE_FOR_ARBITER must be in "
                f"[{MIN_EVIDENCE_FOR_ARBITER}, {MAX_EVIDENCE_FOR_ARBITER_LIMIT}]"
            )
        return value

    @field_validator("max_question_length")
    @classmethod
    def _question_length_bounds(cls, value: int) -> int:
        if not MIN_QUESTION_LENGTH <= value <= MAX_QUESTION_LENGTH_LIMIT:
            raise ValueError(
                "MAX_QUESTION_LENGTH must be within "
                f"{MIN_QUESTION_LENGTH}..{MAX_QUESTION_LENGTH_LIMIT} inclusive"
            )
        return value

    @field_validator("clock_tolerance_seconds")
    @classmethod
    def _clock_tolerance_bounds(cls, value: int) -> int:
        if not MIN_CLOCK_TOLERANCE_SECONDS <= value <= MAX_CLOCK_TOLERANCE_SECONDS:
            raise ValueError(
                "CLOCK_TOLERANCE_SECONDS must be within "
                f"{MIN_CLOCK_TOLERANCE_SECONDS}..{MAX_CLOCK_TOLERANCE_SECONDS} inclusive"
            )
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
        token = _optional_text(source, "CRYPTOPANIC_API_TOKEN")
        return cls(
            aws_region=_required(source, "AWS_REGION"),
            bedrock_primary_model_id=_required(source, "BEDROCK_PRIMARY_MODEL_ID"),
            artifact_root=Path(_required(source, "ARTIFACT_ROOT")),
            bedrock_fallback_model_id=_optional_text(source, "BEDROCK_FALLBACK_MODEL_ID"),
            cryptopanic_api_token=None if token is None else SecretStr(token),
            http_connect_timeout_seconds=_float_value(source, "HTTP_CONNECT_TIMEOUT_SECONDS", 5.0),
            http_read_timeout_seconds=_float_value(source, "HTTP_READ_TIMEOUT_SECONDS", 20.0),
            max_evidence_for_arbiter=_bounded_int(
                source,
                "MAX_EVIDENCE_FOR_ARBITER",
                30,
                MIN_EVIDENCE_FOR_ARBITER,
                MAX_EVIDENCE_FOR_ARBITER_LIMIT,
            ),
            llm_call_timeout_seconds=_float_value(source, "LLM_CALL_TIMEOUT_SECONDS", 45.0, 45.0),
            allow_recorded_demo_fallback=_bool_value(source, "ALLOW_RECORDED_DEMO_FALLBACK", False),
            log_level=_optional_text(source, "LOG_LEVEL") or "INFO",
            max_question_length=_bounded_int(
                source,
                "MAX_QUESTION_LENGTH",
                500,
                MIN_QUESTION_LENGTH,
                MAX_QUESTION_LENGTH_LIMIT,
            ),
            clock_tolerance_seconds=_bounded_int(
                source,
                "CLOCK_TOLERANCE_SECONDS",
                60,
                MIN_CLOCK_TOLERANCE_SECONDS,
                MAX_CLOCK_TOLERANCE_SECONDS,
            ),
            optional_key_presence={name: bool(_optional_text(source, name)) for name in OPTIONAL_ENV_NAMES},
        )

    def validate_request(self, request: AnalysisRequest) -> None:
        """Enforce the configured question bound at the request boundary.

        Counts Unicode code points on the already-stripped question, so a
        Traditional Chinese question is not penalised for its UTF-8 byte length.
        """
        if len(request.question.strip()) > self.max_question_length:
            raise ValueError(
                f"question must not exceed {self.max_question_length} characters"
            )

    def sanitized_snapshot(
        self,
        request: AnalysisRequest,
        *,
        requested_data_mode: DataMode = DataMode.live,
        effective_data_mode: DataMode | None = None,
        effective_run_mode: RunMode | None = None,
        prompt_versions: Mapping[str, str] | None = None,
        stage_durations_ms: Mapping[str, int] | None = None,
        source_identifiers: Sequence[str] | None = None,
        used_llm_fallback_model: bool = False,
        used_cache: bool = False,
        has_stale_evidence: bool = False,
        used_recorded_demo_fallback: bool = False,
        terminal_status: TerminalState | None = None,
        artifact_checksums: Mapping[str, str] | None = None,
    ) -> RunConfigSnapshot:
        """Build the complete ``run_config.json`` payload.

        Every configuration field is passed straight through: the snapshot is a
        superset of the sanitized settings, so no filtering, dropping, or key
        remapping is needed. Credentials and the optional fallback model ID are
        represented only by ``optional_key_presence`` booleans.
        """
        self.validate_request(request)
        cutoff = request.analysis_as_of
        if cutoff is None:
            raise ValueError(
                "analysis_as_of must be frozen before snapshotting; "
                "build the RunContext first"
            )
        return RunConfigSnapshot(
            run_id=request.run_id,
            question=request.question,
            assets=list(request.assets),
            analysis_as_of=cutoff,
            deadline_seconds=request.deadline_seconds,
            requested_run_mode=request.run_mode,
            effective_run_mode=effective_run_mode or request.run_mode,
            requested_data_mode=requested_data_mode,
            effective_data_mode=effective_data_mode or requested_data_mode,
            prompt_versions=dict(prompt_versions or {}),
            stage_durations_ms=dict(stage_durations_ms or {}),
            aws_region=self.aws_region,
            bedrock_primary_model_id=self.bedrock_primary_model_id,
            artifact_root=str(self.artifact_root),
            source_identifiers=list(source_identifiers or []),
            http_connect_timeout_seconds=self.http_connect_timeout_seconds,
            http_read_timeout_seconds=self.http_read_timeout_seconds,
            max_evidence_for_arbiter=self.max_evidence_for_arbiter,
            llm_call_timeout_seconds=self.llm_call_timeout_seconds,
            allow_recorded_demo_fallback=self.allow_recorded_demo_fallback,
            log_level=self.log_level,
            max_question_length=self.max_question_length,
            clock_tolerance_seconds=self.clock_tolerance_seconds,
            optional_key_presence=dict(self.optional_key_presence),
            used_llm_fallback_model=used_llm_fallback_model,
            used_cache=used_cache,
            has_stale_evidence=has_stale_evidence,
            used_recorded_demo_fallback=used_recorded_demo_fallback,
            terminal_status=terminal_status,
            artifact_checksums=dict(artifact_checksums or {}),
        )
