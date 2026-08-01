"""One live run through both baseline paths — the Silver evidence generator.

Silver needs two independent checks and a fallback-only execution does not count:

1. `--mode live`     one run using the designated baseline market *and* research
                     paths with a schema-valid Bedrock result;
2. `--mode fallback` a second run with Bedrock forced to fail, which must still
                     produce four honest artifacts labelled as degraded.

Usage (PowerShell):

    $env:AWS_REGION = "us-west-2"
    $env:BEDROCK_PRIMARY_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    python scripts/live_silver_run.py --mode live --asset BTC
    python scripts/live_silver_run.py --mode fallback --asset BTC

Prints the run id, terminal state, evidence counts, source coverage and the four
artifact paths — the exact fields `docs/rehearsals/run-log.md` wants. Never prints
credentials, tokens or prompt bodies.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings, LLMError
from hoya_agent.application import (
    ApplicationService,
    build_request,
    build_research_pipeline,
    build_research_tool_registry,
)
from hoya_agent.clock import SystemClock
from hoya_agent.models import Asset, RunMode

ARTIFACTS = ("run_config.json", "execution_log.jsonl", "evidence.json", "final_report.md")


class FailingLLM:
    """Forces the deterministic fallback without touching the network."""

    async def converse_structured(self, **kwargs: object):
        del kwargs
        raise LLMError("forced failure for the Silver fallback check")


def _llm(mode: str) -> object:
    if mode == "fallback":
        return FailingLLM()
    region = os.environ.get("AWS_REGION", "us-west-2")
    model_id = os.environ.get("BEDROCK_PRIMARY_MODEL_ID")
    if not model_id:
        raise SystemExit("BEDROCK_PRIMARY_MODEL_ID must be set for a live run")
    return BedrockLLMClient(
        settings=BedrockSettings(
            region=region,
            primary_model_id=model_id,
            fallback_model_id=os.environ.get("BEDROCK_FALLBACK_MODEL_ID") or None,
        )
    )


async def _run(mode: str, asset: Asset, question: str, artifact_root: Path) -> int:
    clock = SystemClock()
    now = clock.now_utc()
    # `official` freezes its own cutoff and forbids fixtures; this script is a
    # rehearsal, so it must not claim that label.
    request = build_request(
        question=question,
        assets=[asset],
        run_mode=RunMode.rehearsal,
        now=now,
        run_id_suffix=f"s{now.strftime('%H%M%S')[-4:]}",
    )
    # The registry owns the one shared AsyncClient for this run, so the connection
    # pool is closed deterministically instead of leaking into interpreter shutdown.
    registry = build_research_tool_registry(
        cryptopanic_api_token=os.environ.get("CRYPTOPANIC_API_TOKEN")
    )
    pipeline = build_research_pipeline(
        clock=clock,
        llm=_llm(mode),
        tool_registry=registry,
    )
    service = ApplicationService(
        clock=clock,
        pipeline=pipeline,
        artifact_root=artifact_root,
    )

    started = datetime.now(UTC)
    try:
        summary = await service.run(request)
    finally:
        await registry.aclose()
    elapsed = (datetime.now(UTC) - started).total_seconds()

    run_dir = artifact_root / summary.run_id
    report = {
        "mode": mode,
        "run_id": summary.run_id,
        "asset": asset.value,
        "run_mode": str(getattr(summary.run_mode, "value", summary.run_mode)),
        "terminal_state": str(getattr(summary.terminal_state, "value", summary.terminal_state)),
        "elapsed_seconds": round(elapsed, 1),
        "artifacts": {
            name: str(run_dir / name) if (run_dir / name).exists() else "MISSING"
            for name in ARTIFACTS
        },
    }

    evidence_path = run_dir / "evidence.json"
    if evidence_path.exists():
        ledger = json.loads(evidence_path.read_text(encoding="utf-8"))
        items = ledger.get("items", [])
        report["evidence_count"] = len(items)
        report["source_types"] = sorted({item.get("source_type") for item in items})
        report["independence_groups"] = sorted(
            {item.get("independence_group") for item in items}
        )
        report["conflict_indicators"] = len(ledger.get("conflict_indicators", []))

    print(json.dumps(report, ensure_ascii=False, indent=2))

    missing = [name for name, path in report["artifacts"].items() if path == "MISSING"]
    if missing:
        print(f"FAIL: missing artifacts: {', '.join(missing)}")
        return 1
    if mode == "live" and report.get("evidence_count", 0) == 0:
        print("FAIL: a live run produced no evidence")
        return 1
    print("OK: four artifacts present")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("live", "fallback"), default="live")
    parser.add_argument("--asset", default="BTC", choices=[a.value for a in Asset])
    parser.add_argument("--question", default="近期市場行為由哪些因素解釋？")
    parser.add_argument("--artifact-root", default="artifacts")
    args = parser.parse_args()

    return asyncio.run(
        _run(args.mode, Asset(args.asset), args.question, Path(args.artifact_root))
    )


if __name__ == "__main__":
    raise SystemExit(main())
