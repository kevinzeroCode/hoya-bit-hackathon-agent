"""S3 artifact mirroring — optional, additive, never blocking (Task 21).

Mirrors a completed run's artifacts to S3 after the local write already
succeeded. Mirroring must never become a dependency of artifact completion: a
run always finishes and writes its four/five artifacts locally first (see
`reporting/artifacts.py`); this is a best-effort copy afterward, and any
failure (missing credentials, unreachable bucket, network down) degrades to a
returned failure note rather than raising or blocking the run.

Structured the same way `adapters/bedrock.py::BedrockLLMClient` handles its
boto3 client: lazily constructed only when actually used, and injectable, so
no test here needs real AWS credentials or network access, and this module
never becomes a hard dependency for anyone running fully offline.

**Not wired into `application.py`/`orchestration/pipeline.py` in this
change** — see `docs/Implementation-Plan.md` §9 Task 21 for why (this
session has no live AWS access to verify a real upload) and where a future
change would call `mirror_artifacts(run_dir, bucket=...)` once a run's local
write finishes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MirrorResult:
    uploaded: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failed


def mirror_artifacts(
    run_dir: Path,
    *,
    bucket: str,
    prefix: str = "",
    client: Any = None,
) -> MirrorResult:
    """Upload every file already written in `run_dir` to
    `s3://bucket/prefix/<run_dir.name>/...`. Never raises.

    `run_dir.name` (the run_id) is always the last path segment before the
    filenames, so two runs never collide in the bucket even if this is
    called concurrently for both.
    """
    if client is None:
        try:
            import boto3  # imported lazily so offline tests need no AWS setup

            client = boto3.client("s3")
        except Exception as exc:  # noqa: BLE001 - any setup failure degrades, never raises
            return MirrorResult(
                notes=(f"S3 client unavailable ({type(exc).__name__}); mirroring skipped",)
            )

    if not run_dir.is_dir():
        return MirrorResult(notes=(f"{run_dir} is not a directory; nothing to mirror",))

    run_id = run_dir.name
    key_prefix = f"{prefix.strip('/')}/{run_id}" if prefix.strip("/") else run_id
    uploaded: list[str] = []
    failed: list[str] = []
    for path in sorted(run_dir.iterdir()):
        if not path.is_file():
            continue
        key = f"{key_prefix}/{path.name}"
        try:
            client.upload_file(str(path), bucket, key)
            uploaded.append(key)
        except Exception as exc:  # noqa: BLE001 - one file failing must not abort the rest
            failed.append(f"{path.name} ({type(exc).__name__})")

    notes: list[str] = []
    if failed:
        notes.append(f"{len(failed)} file(s) failed to mirror: {'; '.join(failed)}")
    return MirrorResult(uploaded=tuple(uploaded), failed=tuple(failed), notes=tuple(notes))
