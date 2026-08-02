"""S10 deterministic artifact contract — what a judge actually opens.

The competition fixes four filenames and requires that they belong to *one*
run. Everything here is asserted against files on disk rather than against the
in-memory `RunSummary`, because the artifacts are the deliverable and a summary
that disagrees with them would be the bug this gate exists to catch.

Filenames come from `reporting/artifacts.ARTIFACT_NAMES`; nothing in this file
re-types them as string literals.
"""

from __future__ import annotations

import io
import json
import re
import socket
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import (
    Asset,
    EvidenceLedger,
    ExecutionEvent,
    RunMode,
    TerminalState,
)
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from hoya_agent.reporting.artifacts import (
    ARTIFACT_NAMES,
    EVIDENCE_LEDGER,
    EXECUTION_LOG,
    FINAL_REPORT,
    RUN_CONFIG,
)
from hoya_agent.reporting.renderer import REPORT_SECTION_TITLES

pytestmark = pytest.mark.acceptance

ANALYSIS_DATE = date(2026, 5, 31)
FROZEN_NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)
QUESTION = "這個資產近期的市場行為可以由哪些因素解釋？"

#: ISO-8601 instants, used to normalize provenance fetch times when comparing
#: two runs of identical inputs. See the determinism test for why.
_ISO_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")


class _FixedClock:
    def now_utc(self) -> datetime:
        return FROZEN_NOW

    def monotonic(self) -> float:
        return 1000.0


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch) -> None:
    def no_network(*args, **kwargs):  # noqa: ANN002, ANN003 - guard signature is irrelevant
        raise AssertionError("the artifact contract gate must not reach the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)


async def _run(artifact_root: Path, *, suffix: str = "art1"):
    service = ApplicationService(
        artifact_root=artifact_root,
        clock=_FixedClock(),
        pipeline=OrganizerCsvPipeline(analysis_date=ANALYSIS_DATE),
        configured_sources=["public_market_data"],
        stdout=io.StringIO(),
    )
    request = build_request(
        question=QUESTION,
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=FROZEN_NOW,
        run_id_suffix=suffix,
        analysis_as_of=FROZEN_NOW,
    )
    return await service.run(request)


@pytest.fixture
async def run_dir(tmp_path) -> Path:
    summary = await _run(tmp_path / "artifacts")
    return Path(summary.artifact_dir)


async def test_exactly_the_four_fixed_filenames_are_written(run_dir: Path) -> None:
    on_disk = sorted(path.name for path in run_dir.iterdir())
    assert on_disk == sorted(ARTIFACT_NAMES)
    assert len(ARTIFACT_NAMES) == 4, "the competition fixes four artifacts — no fifth file"


async def test_every_artifact_parses(run_dir: Path) -> None:
    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    assert isinstance(config, dict)

    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    assert ledger.items, "the offline baseline path must produce Evidence"

    lines = (run_dir / EXECUTION_LOG).read_text(encoding="utf-8").splitlines()
    assert lines, "the execution log must not be empty"
    events = [ExecutionEvent.model_validate_json(line) for line in lines]
    assert events

    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert report.strip(), "the report must not be empty"


async def test_all_four_artifacts_share_one_run_id(run_dir: Path) -> None:
    """One run, one identity — asserted across all four files, not just the summary."""
    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    run_id = config["run_id"]

    assert run_dir.name == run_id
    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    assert ledger.run_id == run_id

    lines = (run_dir / EXECUTION_LOG).read_text(encoding="utf-8").splitlines()
    assert {ExecutionEvent.model_validate_json(line).run_id for line in lines} == {run_id}

    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")
    assert run_id in report


async def test_the_terminal_state_is_explicit_and_agrees_with_the_summary(tmp_path) -> None:
    summary = await _run(tmp_path / "artifacts", suffix="art2")
    config = json.loads((Path(summary.artifact_dir) / RUN_CONFIG).read_text(encoding="utf-8"))

    assert config["terminal_status"] in {state.value for state in TerminalState}
    assert config["terminal_status"] == summary.terminal_state.value
    assert config["missing_artifacts"] == []


async def test_evidence_provenance_survives_serialization(run_dir: Path) -> None:
    """Every Evidence field a judge can audit must still be there on disk."""
    ledger = EvidenceLedger.model_validate_json((run_dir / EVIDENCE_LEDGER).read_text(encoding="utf-8"))
    for item in ledger.items:
        assert item.evidence_id.startswith("ev_")
        assert item.source_name
        assert item.independence_group
        assert item.content_hash
        assert item.fetched_at is not None
        assert item.normalized_fact


async def test_the_report_renders_the_eleven_fixed_sections_and_discloses_limits(run_dir: Path) -> None:
    report = (run_dir / FINAL_REPORT).read_text(encoding="utf-8")

    assert report.count("\n## ") == len(REPORT_SECTION_TITLES) == 11
    for index, title in enumerate(REPORT_SECTION_TITLES, start=1):
        assert f"## {index}. {title}" in report
    # The limitations section is the honesty contract; it must carry content.
    limits = report.split("## 9. 限制與資料缺口", 1)[1]
    assert limits.strip(), "限制與資料缺口 must not be an empty heading"


async def test_no_secret_bearing_field_reaches_the_artifacts(run_dir: Path) -> None:
    """Prompt bodies, tokens and credentials never leave the process."""
    config = json.loads((run_dir / RUN_CONFIG).read_text(encoding="utf-8"))
    serialized = json.dumps(config, ensure_ascii=False)
    log = (run_dir / EXECUTION_LOG).read_text(encoding="utf-8")

    for forbidden in ("aws_secret_access_token", "AKIA", "Bearer ", "sk-", "aws_secret_access_key"):
        assert forbidden not in serialized
        assert forbidden not in log


async def test_rendering_is_deterministic_for_identical_inputs(tmp_path) -> None:
    """Same question, assets, cutoff and clock → identical report and ledger.

    One field legitimately varies between two runs of the same inputs:
    `fetched_at`. It is provenance — *when this process read the source* — and
    for a CSV read that really is wall-clock now, so it is sampled from the
    system clock rather than the injected analysis cutoff. Normalizing it is
    therefore the honest comparison; asserting byte equality including it would
    be asserting that provenance is fake.

    Everything a conclusion can rest on — every metric, every Evidence ID,
    every section — must be identical.
    """
    first = await _run(tmp_path / "one", suffix="det1")
    second = await _run(tmp_path / "two", suffix="det1")

    assert first.run_id == second.run_id, "run identity is a function of the injected clock"

    def without_fetch_times(text: str) -> str:
        return _ISO_TIMESTAMP.sub("<ts>", text)

    report_one = (Path(first.artifact_dir) / FINAL_REPORT).read_text(encoding="utf-8")
    report_two = (Path(second.artifact_dir) / FINAL_REPORT).read_text(encoding="utf-8")
    assert without_fetch_times(report_one) == without_fetch_times(report_two)

    ledger_one = (Path(first.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    ledger_two = (Path(second.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    assert without_fetch_times(ledger_one) == without_fetch_times(ledger_two)


async def test_the_only_field_that_varies_between_identical_runs_is_provenance(tmp_path) -> None:
    """Pin the exception above, so a new source of drift cannot hide behind it."""
    first = await _run(tmp_path / "one", suffix="det2")
    second = await _run(tmp_path / "two", suffix="det2")

    ledger_one = EvidenceLedger.model_validate_json(
        (Path(first.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    )
    ledger_two = EvidenceLedger.model_validate_json(
        (Path(second.artifact_dir) / EVIDENCE_LEDGER).read_text(encoding="utf-8")
    )

    assert [item.evidence_id for item in ledger_one.items] == [item.evidence_id for item in ledger_two.items]
    for a, b in zip(ledger_one.items, ledger_two.items, strict=True):
        differing = {
            name
            for name in type(a).model_fields
            if getattr(a, name) != getattr(b, name)
        }
        assert differing <= {"fetched_at"}, f"unexpected nondeterminism in {differing}"
        # The content hash is what dedup relies on; it must not move with time.
        assert a.content_hash == b.content_hash
