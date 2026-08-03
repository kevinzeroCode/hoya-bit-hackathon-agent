"""Unit tests for the optional S3 artifact mirroring (Task 21). No real AWS
credentials or network access — a fake client is injected throughout."""

from __future__ import annotations

from pathlib import Path

from hoya_agent.adapters.s3_mirror import mirror_artifacts


class FakeS3Client:
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.uploads: list[tuple[str, str, str]] = []
        self._fail_on = fail_on or set()

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        if Path(filename).name in self._fail_on:
            raise RuntimeError("simulated upload failure")
        self.uploads.append((filename, bucket, key))


def _run_dir(tmp_path: Path, *, files: dict[str, str]) -> Path:
    run_dir = tmp_path / "run_20260803_000000_test"
    run_dir.mkdir()
    for name, content in files.items():
        (run_dir / name).write_text(content, encoding="utf-8")
    return run_dir


def test_mirrors_every_file_under_the_run_id_prefix(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path, files={"run_config.json": "{}", "final_report.md": "# x"})
    client = FakeS3Client()

    result = mirror_artifacts(run_dir, bucket="hoya-artifacts", prefix="runs", client=client)

    assert result.ok
    assert set(result.uploaded) == {
        "runs/run_20260803_000000_test/run_config.json",
        "runs/run_20260803_000000_test/final_report.md",
    }
    assert {bucket for _, bucket, _ in client.uploads} == {"hoya-artifacts"}


def test_no_prefix_uses_the_run_id_alone(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path, files={"evidence.json": "{}"})
    client = FakeS3Client()

    result = mirror_artifacts(run_dir, bucket="hoya-artifacts", client=client)

    assert result.uploaded == ("run_20260803_000000_test/evidence.json",)


def test_one_file_failing_does_not_abort_the_rest(tmp_path: Path) -> None:
    run_dir = _run_dir(
        tmp_path, files={"run_config.json": "{}", "final_report.md": "# x", "evidence.json": "{}"}
    )
    client = FakeS3Client(fail_on={"final_report.md"})

    result = mirror_artifacts(run_dir, bucket="hoya-artifacts", client=client)

    assert not result.ok
    assert len(result.uploaded) == 2
    assert any("final_report.md" in f for f in result.failed)
    assert result.notes  # the failure is disclosed, not silent


def test_missing_run_directory_degrades_without_raising(tmp_path: Path) -> None:
    result = mirror_artifacts(tmp_path / "does-not-exist", bucket="b", client=FakeS3Client())
    assert result.uploaded == ()
    assert result.notes


def test_client_construction_failure_degrades_without_raising(tmp_path: Path, monkeypatch) -> None:
    """Simulates the offline/no-credentials case: boto3.client() itself
    raises before any upload is attempted."""
    import sys
    import types

    fake_boto3 = types.SimpleNamespace(
        client=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no AWS credentials"))
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    run_dir = _run_dir(tmp_path, files={"run_config.json": "{}"})
    result = mirror_artifacts(run_dir, bucket="b")

    assert result.uploaded == ()
    assert "unavailable" in result.notes[0]
