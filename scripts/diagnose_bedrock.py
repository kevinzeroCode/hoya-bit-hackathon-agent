r"""Diagnose why the Arbiter's Bedrock call fails, printing the REAL underlying
error (the pipeline wraps it as LLMUnavailableError and hides the cause).

Run with your Bedrock env set (never paste the key anywhere):
    $env:AWS_REGION="us-west-2"
    $env:BEDROCK_PRIMARY_MODEL_ID="us.anthropic.claude-haiku-4-5-20251001-v1:0"
    # + credentials (AWS_BEARER_TOKEN_BEDROCK / aws configure)
    $env:PYTHONPATH="$PWD\src"
    python scripts/diagnose_bedrock.py

Prints the raw boto/Converse exception so we can tell schema vs creds vs model.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Run with zero setup: put src/ on the path so `hoya_agent` imports without PYTHONPATH.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hoya_agent.adapters.bedrock import BedrockLLMClient, BedrockSettings  # noqa: E402
from hoya_agent.reasoning.prompt_library import load_prompt  # noqa: E402
from hoya_agent.reasoning.schemas import ArbiterGeneration  # noqa: E402


async def main() -> None:
    region = os.environ.get("AWS_REGION", "us-west-2")
    model_id = os.environ.get(
        "BEDROCK_PRIMARY_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    print(f"region={region}  model={model_id}")
    print(f"AWS_BEARER_TOKEN_BEDROCK set: {bool(os.getenv('AWS_BEARER_TOKEN_BEDROCK'))}")
    print(f"AWS_ACCESS_KEY_ID set: {bool(os.getenv('AWS_ACCESS_KEY_ID'))}")

    llm = BedrockLLMClient(settings=BedrockSettings(region=region, primary_model_id=model_id))
    # A realistic-sized arbiter payload, called 3x to catch intermittent throttling.
    big_text = (
        "You are the Arbiter. Analyse the following evidence and return a full "
        "structured result with claims, links and rationale.\n"
        + "\n".join(
            f"ev_{i:03d}: BTC market metric value {i} as of 2026-07-31 (reliability high)"
            for i in range(1, 7)
        )
    )
    ok = 0
    for attempt in range(1, 4):
        started = time.monotonic()
        try:
            await llm.converse_structured(
                operation="arbiter",
                messages=[{"role": "user", "content": [{"text": big_text}]}],
                schema=ArbiterGeneration,
                max_tokens=3000,
                deadline=time.monotonic() + 60,
                system_prompt=load_prompt("arbiter").body,
            )
            ok += 1
            print(f"[call {attempt}] OK ({time.monotonic() - started:.1f}s)")
        except Exception as exc:  # noqa: BLE001 - we want the full chain
            print(f"[call {attempt}] FAILED after {time.monotonic() - started:.1f}s: "
                  f"{type(exc).__name__}: {exc}")
            cause = exc.__cause__
            if cause is not None:
                print(f"    underlying: {type(cause).__name__}: {str(cause)[:300]}")
    print(f"\nsummary: {ok}/3 succeeded")


if __name__ == "__main__":
    asyncio.run(main())
