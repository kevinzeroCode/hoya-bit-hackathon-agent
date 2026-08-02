"""S11 deployment smoke test — is the thing that is running actually working?

Two independent checks, either of which can run alone:

**HTTP** — the Streamlit health endpoint answers `ok` and the app root serves a
page. Standard library only, so this half works from any machine against any
host, installed package or not.

**Artifacts** — one offline organizer-CSV run through the real
`ApplicationService`, then: the four fixed filenames exist, `run_config.json`
and `evidence.json` parse as JSON, every `execution_log.jsonl` line parses, the
report is non-empty, and **all four carry the same `run_id`**.

Run it *inside the deployed container*, because the Streamlit UI writes its
artifacts to a per-run temporary directory that no host-side process can see —
checking a host-side run would prove the host's code, not the image's::

    docker cp scripts/smoke_test.py hoya-agent:/tmp/smoke_test.py
    docker exec hoya-agent python /tmp/smoke_test.py --base-url http://localhost:8501

Usage::

    python scripts/smoke_test.py --base-url http://localhost:8501
    python scripts/smoke_test.py --http-only --base-url http://<host>:8501
    python scripts/smoke_test.py --artifacts-only

Exits non-zero with a one-line reason on the first failure. Never prints
credentials, tokens, prompt bodies or artifact contents.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HEALTH_PATH = "/_stcore/health"
DEFAULT_BASE_URL = "http://localhost:8501"
DEFAULT_TIMEOUT_SECONDS = 60.0

#: Fixed by the competition rules. Re-derived from the package when it is
#: importable, so the two can never drift apart silently.
FALLBACK_ARTIFACT_NAMES = ("run_config.json", "execution_log.jsonl", "evidence.json", "final_report.md")


class SmokeFailure(Exception):
    """A check failed. The message is the one line the operator needs."""


def _get(url: str, *, timeout: float = 10.0) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "hoya-smoke-test"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed http(s) URL
        return response.status, response.read()


def _wait_for(url: str, *, deadline_seconds: float) -> tuple[int, bytes]:
    """Poll until the endpoint answers, so container warm-up is not a failure."""
    deadline = time.monotonic() + deadline_seconds
    last_error = "no attempt made"
    delay = 0.5
    while time.monotonic() < deadline:
        try:
            return _get(url)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            time.sleep(delay)
            delay = min(delay * 2, 5.0)
    raise SmokeFailure(f"{url} never answered within {deadline_seconds:.0f}s ({last_error})")


def check_http(base_url: str, *, timeout_seconds: float) -> list[str]:
    base = base_url.rstrip("/")
    passed: list[str] = []

    status, body = _wait_for(base + HEALTH_PATH, deadline_seconds=timeout_seconds)
    text = body.decode("utf-8", errors="replace").strip()
    if status != 200:
        raise SmokeFailure(f"{HEALTH_PATH} returned HTTP {status}, expected 200")
    if text.lower() != "ok":
        raise SmokeFailure(f"{HEALTH_PATH} returned {text[:60]!r}, expected 'ok'")
    passed.append(f"{HEALTH_PATH} → 200 ok")

    status, body = _get(base + "/", timeout=20.0)
    page = body.decode("utf-8", errors="replace")
    if status != 200:
        raise SmokeFailure(f"/ returned HTTP {status}, expected 200")
    if "stApp" not in page and "streamlit" not in page.lower():
        raise SmokeFailure("/ did not serve a Streamlit page")
    passed.append(f"/ → 200, {len(body)} bytes of Streamlit HTML")

    return passed


def check_artifacts() -> list[str]:
    """One real offline run, then audit the four files it left on disk."""
    try:
        from hoya_agent.application import ApplicationService, build_request
        from hoya_agent.clock import SystemClock
        from hoya_agent.models import Asset, RunMode
        from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
        from hoya_agent.reporting.artifacts import ARTIFACT_NAMES
    except ImportError as exc:  # pragma: no cover - environment problem, not a code path
        raise SmokeFailure(f"hoya_agent is not importable here: {exc}") from exc

    import asyncio
    from datetime import datetime, timezone

    utc = timezone.utc
    # The organizer dataset's last bar. The container points HOYA_DATA_DIR at it.
    cutoff = datetime(2026, 5, 31, tzinfo=utc)
    passed: list[str] = []

    with tempfile.TemporaryDirectory(prefix="hoya-smoke-") as root:
        clock = SystemClock()
        request = build_request(
            question="市場狀況與資料整合",
            assets=[Asset.BTC],
            run_mode=RunMode.rehearsal,
            now=clock.now_utc(),
            run_id_suffix="smoke",
            analysis_as_of=cutoff,
        )
        service = ApplicationService(
            artifact_root=Path(root),
            clock=clock,
            pipeline=OrganizerCsvPipeline(analysis_date=cutoff.date()),
            configured_sources=["public_market_data"],
        )
        summary = asyncio.run(service.run(request))
        run_dir = Path(summary.artifact_dir)

        names = tuple(ARTIFACT_NAMES) or FALLBACK_ARTIFACT_NAMES
        on_disk = sorted(path.name for path in run_dir.iterdir())
        if on_disk != sorted(names):
            raise SmokeFailure(f"expected artifacts {sorted(names)}, found {on_disk}")
        passed.append(f"four fixed artifacts written ({', '.join(sorted(names))})")

        config_text = (run_dir / "run_config.json").read_text(encoding="utf-8")
        try:
            config = json.loads(config_text)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"run_config.json is not valid JSON: {exc}") from exc
        run_id = config.get("run_id")
        if not run_id:
            raise SmokeFailure("run_config.json carries no run_id")

        try:
            ledger = json.loads((run_dir / "evidence.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"evidence.json is not valid JSON: {exc}") from exc

        log_lines = (run_dir / "execution_log.jsonl").read_text(encoding="utf-8").splitlines()
        if not log_lines:
            raise SmokeFailure("execution_log.jsonl is empty")
        log_run_ids = set()
        for number, line in enumerate(log_lines, start=1):
            try:
                log_run_ids.add(json.loads(line).get("run_id"))
            except json.JSONDecodeError as exc:
                raise SmokeFailure(f"execution_log.jsonl line {number} is not valid JSON: {exc}") from exc
        passed.append(
            f"all artifacts parse ({len(log_lines)} log events, "
            f"{len(ledger.get('items', []))} evidence items)"
        )

        report = (run_dir / "final_report.md").read_text(encoding="utf-8")
        if not report.strip():
            raise SmokeFailure("final_report.md is empty")

        identities = {run_id, ledger.get("run_id"), *log_run_ids}
        if identities != {run_id}:
            raise SmokeFailure(f"artifacts disagree on run_id: {sorted(str(i) for i in identities)}")
        if run_id not in report:
            raise SmokeFailure("final_report.md does not carry its own run_id")
        passed.append(f"all four artifacts share run_id {run_id}")

    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Streamlit base URL")
    parser.add_argument("--http-only", action="store_true", help="skip the artifact run")
    parser.add_argument("--artifacts-only", action="store_true", help="skip the HTTP checks")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="seconds to wait for the health endpoint (container warm-up)",
    )
    args = parser.parse_args()

    if args.http_only and args.artifacts_only:
        print("FAIL: --http-only and --artifacts-only are mutually exclusive")
        return 2

    checks: list[tuple[str, object]] = []
    if not args.artifacts_only:
        checks.append(("http", lambda: check_http(args.base_url, timeout_seconds=args.timeout)))
    if not args.http_only:
        checks.append(("artifacts", check_artifacts))

    for label, check in checks:
        try:
            for line in check():  # type: ignore[operator]
                print(f"  ok   [{label}] {line}")
        except SmokeFailure as exc:
            print(f"  FAIL [{label}] {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001 - a smoke test reports, it does not raise
            print(f"  FAIL [{label}] unexpected {exc.__class__.__name__}: {exc}")
            return 1

    print(f"\nSMOKE OK ({', '.join(label for label, _ in checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
