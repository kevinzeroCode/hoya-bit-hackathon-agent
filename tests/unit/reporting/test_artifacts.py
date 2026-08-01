"""Unit tests for the atomic artifact writer and the missing-artifact disclosure contract.

Contract sources:
- `.kiro/specs/hoya-market-agent/design.md` §12.1 — incremental persistence and
  the exact-filename disclosure rules.
- `.kiro/steering/tech.md` §9 — fixed filenames, same-directory temp file + `os.replace`.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest

from hoya_agent._provisional_seams import ExecutionEvent, TerminalState
from hoya_agent.models import RunMode
from hoya_agent.reporting.artifacts import (
    ARTIFACT_NAMES,
    EVIDENCE_LEDGER,
    EXECUTION_LOG,
    FINAL_REPORT,
    RUN_CONFIG,
    LocalArtifactStore,
)

RUN_ID = "run_20260531_000000_fx01"


def _event(event_type: str = "stage_start") -> ExecutionEvent:
    return ExecutionEvent(
        timestamp=datetime(2026, 5, 31, 0, 1, tzinfo=UTC),
        run_id=RUN_ID,
        run_mode=RunMode.rehearsal,
        stage="acquisition",
        event_type=event_type,
        status="ok",
        message="fixture event",
    )


def test_artifact_names_are_the_four_fixed_names() -> None:
    assert ARTIFACT_NAMES == (RUN_CONFIG, EXECUTION_LOG, EVIDENCE_LEDGER, FINAL_REPORT)
    assert ARTIFACT_NAMES == (
        "run_config.json",
        "execution_log.jsonl",
        "evidence.json",
        "final_report.md",
    )


def test_write_json_is_atomic_and_leaves_no_temp_file(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    assert store.write_json(EVIDENCE_LEDGER, {"run_id": RUN_ID}) is True

    written = store.run_dir / EVIDENCE_LEDGER
    assert json.loads(written.read_text(encoding="utf-8")) == {"run_id": RUN_ID}
    assert [p.name for p in store.run_dir.iterdir()] == [EVIDENCE_LEDGER]


def test_atomic_replace_happens_inside_the_same_directory(tmp_path, monkeypatch) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    seen: list[tuple[str, str]] = []
    real_replace = __import__("os").replace

    def spy(src, dst):  # noqa: ANN001 - test spy mirrors os.replace
        seen.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr("hoya_agent.reporting.artifacts.os.replace", spy)
    store.write_text(FINAL_REPORT, "# 報告\n")

    assert len(seen) == 1
    src, dst = seen[0]
    from pathlib import Path

    assert Path(src).parent == Path(dst).parent == store.run_dir


def test_rewrite_never_exposes_partial_content(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    store.write_text(FINAL_REPORT, "第一版\n")
    store.write_text(FINAL_REPORT, "第二版\n")
    assert (store.run_dir / FINAL_REPORT).read_text(encoding="utf-8") == "第二版\n"


def test_execution_log_streams_one_json_object_per_line(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    store.append_event(_event("run_start"))
    store.append_event(_event("stage_end"))

    lines = (store.run_dir / EXECUTION_LOG).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert [p["event_type"] for p in parsed] == ["run_start", "stage_end"]
    assert parsed[0]["run_id"] == RUN_ID
    assert parsed[0]["timestamp"].endswith("Z")


def test_execution_log_is_readable_before_the_run_ends(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    store.append_event(_event("run_start"))
    # Streaming means the event is flushed, not buffered until finalization.
    assert (store.run_dir / EXECUTION_LOG).read_text(encoding="utf-8").strip() != ""


def test_checksums_cover_every_written_artifact(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    store.write_json(RUN_CONFIG, {"run_id": RUN_ID})
    store.append_event(_event())
    store.write_json(EVIDENCE_LEDGER, {"items": []})
    store.write_text(FINAL_REPORT, "# 報告\n")

    checksums = store.checksums()
    assert set(checksums) == set(ARTIFACT_NAMES)
    assert all(len(digest) == 64 for digest in checksums.values())
    assert store.missing_artifacts() == []


def test_single_write_failure_names_the_exact_file_in_stdout_and_log(tmp_path) -> None:
    stdout = io.StringIO()
    store = LocalArtifactStore(tmp_path / RUN_ID, stdout=stdout)
    store.write_json(RUN_CONFIG, {"run_id": RUN_ID})
    # A directory occupying the artifact name makes the atomic replace fail.
    (store.run_dir / EVIDENCE_LEDGER).mkdir()

    assert store.write_json(EVIDENCE_LEDGER, {"items": []}) is False

    assert EVIDENCE_LEDGER in stdout.getvalue()
    assert "artifact write failed" in stdout.getvalue().lower()
    assert store.missing_artifacts() == [EVIDENCE_LEDGER, FINAL_REPORT]
    assert [f.name for f in store.failures] == [EVIDENCE_LEDGER]

    log_text = (store.run_dir / EXECUTION_LOG).read_text(encoding="utf-8")
    assert EVIDENCE_LEDGER in log_text
    assert "artifact_write_failed" in log_text
    # No temp file is left behind by the failed write.
    assert not [p for p in store.run_dir.iterdir() if p.name.startswith(".tmp")]


def test_failed_write_does_not_claim_the_artifact_exists(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID, stdout=io.StringIO())
    (store.run_dir / FINAL_REPORT).mkdir()
    store.write_text(FINAL_REPORT, "# 報告\n")

    assert FINAL_REPORT not in store.checksums()
    assert FINAL_REPORT in store.missing_artifacts()
    assert FINAL_REPORT not in store.artifact_paths()


def test_completely_unwritable_directory_discloses_all_four_names(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    stdout = io.StringIO()

    store = LocalArtifactStore(blocker / RUN_ID, stdout=stdout)

    assert store.directory_writable is False
    store.disclose_missing(TerminalState.failed)
    disclosure = stdout.getvalue()
    for name in ARTIFACT_NAMES:
        assert name in disclosure
    assert "failed" in disclosure
    assert store.missing_artifacts() == list(ARTIFACT_NAMES)
    # Writes degrade to a recorded failure rather than raising.
    assert store.write_text(FINAL_REPORT, "# 報告\n") is False
    assert store.append_event(_event()) is False


def test_unknown_artifact_name_is_rejected(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / RUN_ID)
    with pytest.raises(ValueError, match="fixed artifact"):
        store.write_text("report.pdf", "nope")
