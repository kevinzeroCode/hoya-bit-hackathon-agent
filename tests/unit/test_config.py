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
    assert snapshot.optional_key_presence["CRYPTOPANIC_API_TOKEN"] is True
    assert snapshot.optional_key_presence["HTTP_CONNECT_TIMEOUT_SECONDS"] is False
    # evidence-contracts.md §14 requires non-secret operational settings to be
    # reproducible from the artifact, so the read timeout is now recorded by
    # value. Only credentials and the optional model ID stay presence-only.
    assert snapshot.http_read_timeout_seconds == 33.0


def test_required_settings_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, "AWS_REGION": "  "})




# ===========================================================================
# Corrective regression tests.
#
# Finding B (MAX_QUESTION_LENGTH / CLOCK_TOLERANCE_SECONDS env-backed),
# Finding C (SecretStr token), MAX_EVIDENCE_FOR_ARBITER 20..30 bounds, and
# Finding D's composition requirement.
# ===========================================================================

from pydantic import SecretStr  # noqa: E402

from hoya_agent.config import OPTIONAL_ENV_NAMES  # noqa: E402
from hoya_agent.models import ARTIFACT_FILENAMES, DataMode, RunConfigSnapshot  # noqa: E402

TOKEN = "super-secret-cryptopanic-token"


# --- Finding B: both keys are environment-backed --------------------------


def test_new_optional_keys_are_registered_as_optional_env_names() -> None:
    assert "MAX_QUESTION_LENGTH" in OPTIONAL_ENV_NAMES
    assert "CLOCK_TOLERANCE_SECONDS" in OPTIONAL_ENV_NAMES


def test_max_question_length_defaults_to_500() -> None:
    assert Settings.from_env(REQUIRED_ENV).max_question_length == 500


def test_clock_tolerance_defaults_to_60_seconds() -> None:
    assert Settings.from_env(REQUIRED_ENV).clock_tolerance_seconds == 60


def test_max_question_length_is_parsed_from_the_environment() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "MAX_QUESTION_LENGTH": "750"})

    assert settings.max_question_length == 750


def test_clock_tolerance_is_parsed_from_the_environment() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CLOCK_TOLERANCE_SECONDS": "120"})

    assert settings.clock_tolerance_seconds == 120


def test_clock_tolerance_is_an_integer_not_a_float() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CLOCK_TOLERANCE_SECONDS": "90"})

    assert isinstance(settings.clock_tolerance_seconds, int)


@pytest.mark.parametrize("raw", ["49", "2001", "0", "-1"])
def test_max_question_length_rejects_out_of_bounds(raw: str) -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, "MAX_QUESTION_LENGTH": raw})


@pytest.mark.parametrize("raw", ["50", "500", "2000"])
def test_max_question_length_accepts_boundaries(raw: str) -> None:
    assert Settings.from_env(
        {**REQUIRED_ENV, "MAX_QUESTION_LENGTH": raw}
    ).max_question_length == int(raw)


@pytest.mark.parametrize("raw", ["-1", "301"])
def test_clock_tolerance_rejects_out_of_bounds(raw: str) -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, "CLOCK_TOLERANCE_SECONDS": raw})


@pytest.mark.parametrize("raw", ["0", "60", "300"])
def test_clock_tolerance_accepts_boundaries_including_zero(raw: str) -> None:
    """Zero tolerance is a legitimate configuration, unlike a timeout."""
    assert Settings.from_env(
        {**REQUIRED_ENV, "CLOCK_TOLERANCE_SECONDS": raw}
    ).clock_tolerance_seconds == int(raw)


# --- MAX_EVIDENCE_FOR_ARBITER must stay inside the 20..30 window ----------


def test_max_evidence_rejects_nineteen() -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, "MAX_EVIDENCE_FOR_ARBITER": "19"})


def test_max_evidence_accepts_twenty() -> None:
    assert Settings.from_env(
        {**REQUIRED_ENV, "MAX_EVIDENCE_FOR_ARBITER": "20"}
    ).max_evidence_for_arbiter == 20


def test_max_evidence_accepts_thirty() -> None:
    assert Settings.from_env(
        {**REQUIRED_ENV, "MAX_EVIDENCE_FOR_ARBITER": "30"}
    ).max_evidence_for_arbiter == 30


def test_max_evidence_rejects_thirty_one() -> None:
    with pytest.raises(ValueError):
        Settings.from_env({**REQUIRED_ENV, "MAX_EVIDENCE_FOR_ARBITER": "31"})


# --- Finding C: the token is a SecretStr ---------------------------------


def test_token_is_stored_as_a_secret_str() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CRYPTOPANIC_API_TOKEN": TOKEN})

    assert isinstance(settings.cryptopanic_api_token, SecretStr)


def test_token_requires_explicit_get_secret_value() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CRYPTOPANIC_API_TOKEN": TOKEN})

    assert settings.cryptopanic_api_token.get_secret_value() == TOKEN
    assert TOKEN not in str(settings.cryptopanic_api_token)


def test_token_absent_is_none_not_empty_secret() -> None:
    assert Settings.from_env(REQUIRED_ENV).cryptopanic_api_token is None


def test_token_does_not_appear_in_settings_repr_or_str() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CRYPTOPANIC_API_TOKEN": TOKEN})

    assert TOKEN not in repr(settings)
    assert TOKEN not in str(settings)


def test_token_does_not_appear_in_a_model_dump() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CRYPTOPANIC_API_TOKEN": TOKEN})

    assert TOKEN not in settings.model_dump_json()


def test_token_does_not_appear_in_a_validation_error() -> None:
    """A bad neighbouring value must not cause the token to be echoed."""
    with pytest.raises(ValueError) as excinfo:
        Settings.from_env(
            {
                **REQUIRED_ENV,
                "CRYPTOPANIC_API_TOKEN": TOKEN,
                "MAX_EVIDENCE_FOR_ARBITER": "99",
            }
        )

    assert TOKEN not in str(excinfo.value)
    assert TOKEN not in repr(excinfo.value)


def test_token_does_not_appear_in_the_snapshot() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "CRYPTOPANIC_API_TOKEN": TOKEN})

    snapshot = settings.sanitized_snapshot(request())

    assert TOKEN not in snapshot.model_dump_json()
    assert snapshot.optional_key_presence["CRYPTOPANIC_API_TOKEN"] is True


# --- Finding D: the snapshot composes directly ---------------------------


def test_sanitized_snapshot_returns_a_valid_run_config_snapshot() -> None:
    settings = Settings.from_env(REQUIRED_ENV)

    snapshot = settings.sanitized_snapshot(request())

    assert isinstance(snapshot, RunConfigSnapshot)
    RunConfigSnapshot.model_validate(snapshot.model_dump())


def test_snapshot_carries_every_reproducibility_setting_without_remapping() -> None:
    settings = Settings.from_env(
        {
            **REQUIRED_ENV,
            "HTTP_CONNECT_TIMEOUT_SECONDS": "6",
            "HTTP_READ_TIMEOUT_SECONDS": "21",
            "MAX_EVIDENCE_FOR_ARBITER": "22",
            "LLM_CALL_TIMEOUT_SECONDS": "30",
            "ALLOW_RECORDED_DEMO_FALLBACK": "true",
            "LOG_LEVEL": "WARNING",
            "MAX_QUESTION_LENGTH": "600",
            "CLOCK_TOLERANCE_SECONDS": "45",
        }
    )

    snapshot = settings.sanitized_snapshot(request())

    assert snapshot.http_connect_timeout_seconds == 6.0
    assert snapshot.http_read_timeout_seconds == 21.0
    assert snapshot.max_evidence_for_arbiter == 22
    assert snapshot.llm_call_timeout_seconds == 30.0
    assert snapshot.allow_recorded_demo_fallback is True
    assert snapshot.log_level == "WARNING"
    assert snapshot.max_question_length == 600
    assert snapshot.clock_tolerance_seconds == 45
    assert snapshot.aws_region == REQUIRED_ENV["AWS_REGION"]
    assert snapshot.bedrock_primary_model_id == REQUIRED_ENV["BEDROCK_PRIMARY_MODEL_ID"]


def test_snapshot_carries_the_sanitized_request_and_frozen_cutoff() -> None:
    req = request()

    snapshot = Settings.from_env(REQUIRED_ENV).sanitized_snapshot(req)

    assert snapshot.question == req.question
    assert snapshot.assets == req.assets
    assert snapshot.analysis_as_of == req.analysis_as_of
    assert snapshot.deadline_seconds == req.deadline_seconds


def test_snapshot_records_requested_and_effective_modes() -> None:
    snapshot = Settings.from_env(REQUIRED_ENV).sanitized_snapshot(request())

    assert snapshot.requested_run_mode is RunMode.official
    assert snapshot.effective_run_mode is RunMode.official
    assert isinstance(snapshot.requested_data_mode, DataMode)
    assert isinstance(snapshot.effective_data_mode, DataMode)


def test_snapshot_accepts_an_explicit_effective_data_mode() -> None:
    snapshot = Settings.from_env(REQUIRED_ENV).sanitized_snapshot(
        request(),
        requested_data_mode=DataMode.live,
        effective_data_mode=DataMode.recorded_fallback,
    )

    assert snapshot.requested_data_mode is DataMode.live
    assert snapshot.effective_data_mode is DataMode.recorded_fallback


def test_snapshot_artifact_checksums_accept_only_fixed_names() -> None:
    snapshot = Settings.from_env(REQUIRED_ENV).sanitized_snapshot(
        request(), artifact_checksums={name: "a" * 64 for name in ARTIFACT_FILENAMES}
    )

    assert set(snapshot.artifact_checksums) == set(ARTIFACT_FILENAMES)


# --- validate_request enforces the configured maximum -------------------


def test_validate_request_accepts_a_question_at_the_configured_limit() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "MAX_QUESTION_LENGTH": "50"})
    req = AnalysisRequest(
        question="x" * 50,
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 5, tzinfo=UTC),
        run_mode=RunMode.official,
        run_id="run_20260801_120500_test",
    )

    settings.validate_request(req)


def test_validate_request_rejects_a_question_over_the_configured_limit() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "MAX_QUESTION_LENGTH": "50"})
    req = AnalysisRequest(
        question="x" * 51,
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 5, tzinfo=UTC),
        run_mode=RunMode.official,
        run_id="run_20260801_120500_test",
    )

    with pytest.raises(ValueError):
        settings.validate_request(req)


def test_validate_request_counts_unicode_code_points_not_bytes() -> None:
    """A CJK question must not be rejected for its UTF-8 byte length."""
    settings = Settings.from_env({**REQUIRED_ENV, "MAX_QUESTION_LENGTH": "50"})
    req = AnalysisRequest(
        question="市" * 50,
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 5, tzinfo=UTC),
        run_mode=RunMode.official,
        run_id="run_20260801_120500_test",
    )

    settings.validate_request(req)


def test_validate_request_measures_the_stripped_question() -> None:
    settings = Settings.from_env({**REQUIRED_ENV, "MAX_QUESTION_LENGTH": "50"})
    req = AnalysisRequest(
        question="   " + "x" * 50 + "   ",
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 5, tzinfo=UTC),
        run_mode=RunMode.official,
        run_id="run_20260801_120500_test",
    )

    settings.validate_request(req)
