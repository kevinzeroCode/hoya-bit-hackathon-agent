"""Tests for the evidence.json artifact serializer."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from evidence.evidence_json import build_evidence_payload, dump_evidence_json
from evidence.types import EvidenceItem, EvidenceLedger

UTC = timezone.utc


def _ledger() -> EvidenceLedger:
    item = EvidenceItem(
        evidence_id="ev_001", content_hash="abc123", asset="BTC", source_type="market",
        source_name="public_market_data", source_url=None,
        published_at=datetime(2026, 5, 31, tzinfo=UTC), fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
        query_or_parameters="metric=return_14d; credentials removed",
        content_reference="14-bar return", normalized_fact="BTC 近 14 日報酬 -4.88%",
        reliability="high", independence_group="organizer-public-market-data",
        metric_name="return_14d", metric_value=-0.0488,
    )
    return EvidenceLedger(items=[item], dropped_duplicates=2)


def test_payload_has_run_header_and_evidence():
    p = build_evidence_payload(_ledger(), asset="BTC", analysis_as_of=date(2026, 5, 31), run_id="r1")
    assert p["run_mode"] == "rehearsal"          # never defaults to official
    assert p["asset"] == "BTC"
    assert p["summary"]["evidence_count"] == 1
    assert p["summary"]["dropped_duplicates"] == 2
    assert p["evidence"][0]["evidence_id"] == "ev_001"


def test_datetimes_are_iso_strings_and_round_trip():
    p = build_evidence_payload(_ledger(), asset="BTC", analysis_as_of=date(2026, 5, 31), run_id="r1")
    text = json.dumps(p)  # must be JSON-serializable without a custom default here
    assert "2026-05-31" in p["evidence"][0]["published_at"]
    assert json.loads(text)["run_id"] == "r1"


def test_rejects_bad_run_mode():
    with pytest.raises(ValueError):
        build_evidence_payload(_ledger(), asset="BTC", analysis_as_of=date(2026, 5, 31),
                               run_id="r1", run_mode="official-ish")


def test_dump_writes_file(tmp_path):
    out = tmp_path / "evidence.json"
    dump_evidence_json(_ledger(), out, asset="BTC", analysis_as_of=date(2026, 5, 31), run_id="r1")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["evidence"][0]["reliability"] == "high"
    # no secrets leaked
    assert "credentials removed" in data["evidence"][0]["query_or_parameters"]
