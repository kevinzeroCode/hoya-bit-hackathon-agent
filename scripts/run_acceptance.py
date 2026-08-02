"""S10 Gold local Exit driver — two different assets, two independent runs.

The automated gate lives in `tests/acceptance/`. This script is the other half:
it performs the two runs whose real run IDs, durations and artifact paths go
into `docs/rehearsals/run-log.md`. A test proves the contract; this proves the
runs happened.

    # offline baseline (organizer CSV) — no network, no credentials
    python scripts/run_acceptance.py

    # same two runs against the live baseline paths + Bedrock reasoning
    $env:AWS_REGION = "us-west-2"
    $env:BEDROCK_PRIMARY_MODEL_ID = "<inference-profile id>"
    python scripts/run_acceptance.py --live

    # paste-ready run-log rows
    python scripts/run_acceptance.py --markdown

The two assets are run **separately, one asset each**. This gate proves the
pipeline is coin-agnostic; the dual-asset comparison has its own gate and
neither substitutes for the other. Never prints credentials, tokens or prompts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hoya_agent.application import (  # noqa: E402
    ApplicationService,
    build_request,
    build_research_pipeline,
    build_research_tool_registry,
)
from hoya_agent.clock import SystemClock  # noqa: E402
from hoya_agent.models import Asset, RunMode  # noqa: E402
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline  # noqa: E402
from hoya_agent.reporting.artifacts import ARTIFACT_NAMES  # noqa: E402

#: The two assets the Gold gate requires. Additional assets are optional and
#: non-blocking; the five-coin matrix is explicitly not required.
GOLD_ASSETS = (Asset.BTC, Asset.ETH)

#: The organizer dataset ends here; the offline gate replays that frozen cutoff.
OFFLINE_CUTOFF = datetime(2026, 5, 31, tzinfo=UTC)

QUESTION = "這個資產近期的市場行為可以由哪些因素解釋？"


def _bedrock_llm():
    """Real Bedrock client for `--live`; fails loudly rather than silently offline."""
    from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings

    model_id = os.environ.get("BEDROCK_PRIMARY_MODEL_ID")
    if not model_id:
        raise SystemExit("--live needs BEDROCK_PRIMARY_MODEL_ID (and AWS credentials)")
    return BedrockLLMClient(
        settings=BedrockSettings(
            region=os.environ.get("AWS_REGION", "us-west-2"),
            primary_model_id=model_id,
            fallback_model_id=os.environ.get("BEDROCK_FALLBACK_MODEL_ID") or None,
        )
    )


async def _one_run(asset: Asset, *, live: bool, artifact_root: Path, index: int) -> dict:
    """One independent single-asset run through the public entry point."""
    clock = SystemClock()
    now = clock.now_utc()
    registry = None

    if live:
        # `official` freezes its own cutoff; this is a rehearsal and must not
        # claim the official label.
        request = build_request(
            question=QUESTION,
            assets=[asset],
            run_mode=RunMode.rehearsal,
            now=now,
            run_id_suffix=f"g{index}{asset.value[:2].lower()}",
        )
        registry = build_research_tool_registry(
            cryptopanic_api_token=os.environ.get("CRYPTOPANIC_API_TOKEN")
        )
        pipeline = build_research_pipeline(clock=clock, llm=_bedrock_llm(), tool_registry=registry)
        configured = ["public_market_data", "binance", "rss", "fear_greed"]
    else:
        request = build_request(
            question=QUESTION,
            assets=[asset],
            run_mode=RunMode.rehearsal,
            now=now,
            run_id_suffix=f"g{index}{asset.value[:2].lower()}",
            analysis_as_of=OFFLINE_CUTOFF,
        )
        pipeline = OrganizerCsvPipeline(analysis_date=OFFLINE_CUTOFF.date())
        configured = ["public_market_data"]

    service = ApplicationService(
        artifact_root=artifact_root,
        clock=clock,
        pipeline=pipeline,
        configured_sources=configured,
    )

    started = datetime.now(UTC)
    try:
        summary = await service.run(request)
    finally:
        if registry is not None:
            await registry.aclose()
    elapsed = (datetime.now(UTC) - started).total_seconds()

    run_dir = artifact_root / summary.run_id
    record: dict = {
        "asset": asset.value,
        "run_id": summary.run_id,
        "run_mode": str(getattr(summary.run_mode, "value", summary.run_mode)),
        "data_mode": str(getattr(summary.effective_data_mode, "value", summary.effective_data_mode)),
        "terminal_state": str(getattr(summary.terminal_state, "value", summary.terminal_state)),
        "elapsed_seconds": round(elapsed, 1),
        "evidence_count": summary.evidence_item_count,
        "confidence": str(getattr(summary.confidence, "value", summary.confidence)),
        "insufficient_data": summary.insufficient_data,
        "degradation_notes": list(summary.degradation_notes),
        "artifact_dir": str(run_dir),
        "artifacts": {
            name: str(run_dir / name) if (run_dir / name).exists() else "MISSING"
            for name in ARTIFACT_NAMES
        },
    }

    ledger_path = run_dir / "evidence.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        items = ledger.get("items", [])
        record["source_types"] = sorted({item.get("source_type") for item in items})
        record["independence_groups"] = sorted({item.get("independence_group") for item in items})
        record["conflict_indicators"] = len(ledger.get("conflict_indicators", []))
        record["assets_in_ledger"] = sorted({item.get("asset") for item in items if item.get("asset")})

    return record


def _check(records: list[dict]) -> list[str]:
    """Gate conditions. Returns the failures; empty means the gate passed."""
    failures: list[str] = []

    for record in records:
        missing = [name for name, path in record["artifacts"].items() if path == "MISSING"]
        if missing:
            failures.append(f"{record['asset']}: missing artifacts {', '.join(missing)}")
        if record.get("assets_in_ledger") not in (None, [], [record["asset"]]):
            failures.append(
                f"{record['asset']}: ledger carries {record['assets_in_ledger']}, "
                "a single-asset run must not"
            )

    run_ids = [record["run_id"] for record in records]
    if len(set(run_ids)) != len(run_ids):
        failures.append("the two runs share a run_id — they must be independent runs")

    assets = [record["asset"] for record in records]
    if len(set(assets)) < 2:
        failures.append("the gate needs two *different* assets")

    return failures


def _markdown(records: list[dict], *, live: bool) -> str:
    header = (
        "| 資產 | run ID | 模式 | terminal state | 時長 (s) | evidence | 獨立上游 | 降級 | artifact 目錄 |\n"
        "|---|---|---|---|---:|---:|---|---|---|"
    )
    rows = []
    for record in records:
        degradation = "；".join(record["degradation_notes"]) if record["degradation_notes"] else "—"
        groups = ", ".join(record.get("independence_groups") or []) or "—"
        rows.append(
            f"| {record['asset']} | `{record['run_id']}` | "
            f"{record['run_mode']}／{'live' if live else 'offline CSV'} | "
            f"{record['terminal_state']} | {record['elapsed_seconds']} | "
            f"{record['evidence_count']} | {groups} | {degradation} | `{record['artifact_dir']}` |"
        )
    return "\n".join([header, *rows])


async def _main(args: argparse.Namespace) -> int:
    artifact_root = Path(args.artifact_root)
    assets = [Asset(value) for value in args.assets] if args.assets else list(GOLD_ASSETS)
    if len({asset.value for asset in assets}) < 2:
        raise SystemExit("the Gold gate needs two different assets")

    records = [
        await _one_run(asset, live=args.live, artifact_root=artifact_root, index=index)
        for index, asset in enumerate(assets, start=1)
    ]

    if args.markdown:
        print(_markdown(records, live=args.live))
    else:
        print(json.dumps(records, ensure_ascii=False, indent=2))

    failures = _check(records)
    if failures:
        print("\nFAIL:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"\nOK: {len(records)} independent single-asset runs, four artifacts each")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="use the live baseline paths + Bedrock instead of the offline organizer CSV",
    )
    parser.add_argument(
        "--assets",
        nargs="+",
        choices=[asset.value for asset in Asset],
        help=f"override the two gate assets (default: {' '.join(a.value for a in GOLD_ASSETS)})",
    )
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--markdown", action="store_true", help="emit paste-ready run-log rows")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
