"""Fixture loaders for the S2 reporting unit tests.

The loaders live here rather than in ``tests/conftest.py`` because that file is
owned by Task 1b (runtime seams) and does not exist yet. When 1b lands, these
two helpers can move up into the shared conftest unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hoya_agent.models import AnalysisResult, EvidenceLedger

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "vertical_slice"


def load_ledger_payload() -> dict:
    return json.loads((FIXTURE_DIR / "evidence.json").read_text(encoding="utf-8"))


def load_result_payload() -> dict:
    return json.loads((FIXTURE_DIR / "analysis_result.json").read_text(encoding="utf-8"))


@pytest.fixture
def ledger() -> EvidenceLedger:
    return EvidenceLedger.model_validate(load_ledger_payload())


@pytest.fixture
def result() -> AnalysisResult:
    return AnalysisResult.model_validate(load_result_payload())


@pytest.fixture
def fixture_source_text() -> str:
    """Raw fixture JSON text, used to prove the renderer invents no new facts."""
    return (
        (FIXTURE_DIR / "evidence.json").read_text(encoding="utf-8")
        + (FIXTURE_DIR / "analysis_result.json").read_text(encoding="utf-8")
    )
