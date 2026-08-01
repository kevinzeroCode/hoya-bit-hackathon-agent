"""Local artifact writer: fixed filenames, atomic writes, honest missing-file disclosure.

Filenames are fixed by the competition rules and are never chosen by a prompt.
Every write uses a temporary file in the *same* directory followed by
`os.replace`, because a cross-directory rename is not atomic on every filesystem.

Failure honesty (design.md §12.1) is the reason this module returns booleans
instead of raising: a partial run must still finish and disclose exactly which
fixed filename is missing and why, both on stdout and in whichever of
`execution_log.jsonl` / `run_config.json` is still writable. The system never
claims an unwritten artifact exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from hoya_agent.models import ExecutionEvent, TerminalState

RUN_CONFIG = "run_config.json"
EXECUTION_LOG = "execution_log.jsonl"
EVIDENCE_LEDGER = "evidence.json"
FINAL_REPORT = "final_report.md"

#: Write order is also the resilience order: config first, report last.
ARTIFACT_NAMES: tuple[str, ...] = (RUN_CONFIG, EXECUTION_LOG, EVIDENCE_LEDGER, FINAL_REPORT)

_TMP_PREFIX = ".tmp-"


@dataclass(frozen=True)
class ArtifactWriteFailure:
    name: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "reason": self.reason}


class LocalArtifactStore:
    """Writes the four fixed artifacts under one run directory."""

    def __init__(self, run_dir: Path, *, stdout: TextIO | None = None) -> None:
        self.run_dir = Path(run_dir)
        self._stdout: TextIO = stdout if stdout is not None else sys.stdout
        self._written: dict[str, Path] = {}
        self._failures: list[ArtifactWriteFailure] = []
        self.directory_writable = self._ensure_directory()

    # -- public API ---------------------------------------------------------

    @property
    def failures(self) -> list[ArtifactWriteFailure]:
        return list(self._failures)

    def artifact_paths(self) -> dict[str, str]:
        return {name: str(path) for name, path in self._written.items()}

    def missing_artifacts(self) -> list[str]:
        return [name for name in ARTIFACT_NAMES if name not in self._written]

    def checksums(self) -> dict[str, str]:
        digests: dict[str, str] = {}
        for name, path in self._written.items():
            try:
                digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:  # pragma: no cover - disclosed, not swallowed
                self._record_failure(name, f"checksum unavailable: {exc.__class__.__name__}")
        return digests

    def write_text(self, name: str, text: str) -> bool:
        self._require_fixed_name(name)
        return self._atomic_write(name, text.encode("utf-8"))

    def write_json(self, name: str, payload: object) -> bool:
        self._require_fixed_name(name)
        body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False, default=str)
        return self._atomic_write(name, (body + "\n").encode("utf-8"))

    def append_event(self, event: ExecutionEvent) -> bool:
        """Append and flush one execution-log line so the log is readable mid-run."""
        if not self.directory_writable:
            self._record_failure(EXECUTION_LOG, "artifact directory is not writable")
            return False
        line = event.model_dump_json(exclude_none=False)
        path = self.run_dir / EXECUTION_LOG
        try:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            self._record_failure(EXECUTION_LOG, f"{exc.__class__.__name__}: {exc.strerror or exc}")
            return False
        self._written[EXECUTION_LOG] = path
        return True

    def disclose_missing(self, terminal_state: TerminalState) -> None:
        """Name every missing fixed artifact on stdout and in whatever remains writable."""
        missing = self.missing_artifacts()
        if not missing:
            return
        reasons = {failure.name: failure.reason for failure in self._failures}
        detail = ", ".join(f"{name} ({reasons.get(name, 'not written')})" for name in missing)
        self._print(
            f"[artifact] missing artifacts for run directory {self.run_dir}: {detail}"
            f" | terminal_state={terminal_state.value}"
        )

    # -- internals ----------------------------------------------------------

    def _ensure_directory(self) -> bool:
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._print(
                f"[artifact] artifact write failed: run directory {self.run_dir} is not writable"
                f" ({exc.__class__.__name__}); missing artifacts: {', '.join(ARTIFACT_NAMES)}"
            )
            return False
        return True

    def _require_fixed_name(self, name: str) -> None:
        if name not in ARTIFACT_NAMES:
            raise ValueError(
                f"{name!r} is not one of the fixed artifact filenames {ARTIFACT_NAMES}"
            )

    def _atomic_write(self, name: str, payload: bytes) -> bool:
        if not self.directory_writable:
            self._record_failure(name, "artifact directory is not writable")
            return False

        target = self.run_dir / name
        tmp = self.run_dir / f"{_TMP_PREFIX}{name}"
        try:
            with tmp.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            self._record_failure(name, f"{exc.__class__.__name__}: {exc.strerror or exc}")
            return False
        self._written[name] = target
        return True

    def _record_failure(self, name: str, reason: str) -> None:
        self._failures.append(ArtifactWriteFailure(name=name, reason=reason))
        self._print(f"[artifact] artifact write failed: {name} ({reason})")
        self._log_failure(name, reason)

    def _log_failure(self, name: str, reason: str) -> None:
        """Record the failure in the execution log when the log itself still works."""
        if name == EXECUTION_LOG or not self.directory_writable:
            return
        path = self.run_dir / EXECUTION_LOG
        entry = {
            "schema_version": "1.0",
            "event_type": "artifact_write_failed",
            "status": "failed",
            "artifact": name,
            "error_category": "artifact_write",
            "message": reason,
        }
        try:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                handle.flush()
        except OSError:
            # The log is unavailable too; stdout already carries the disclosure.
            return
        self._written[EXECUTION_LOG] = path

    def _print(self, message: str) -> None:
        print(message, file=self._stdout, flush=True)
