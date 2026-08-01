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
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
    try:
        result = await llm.converse_structured(
            operation="arbiter",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                "Return an insufficient-data result as JSON with "
                                "direct_answer set and insufficient_data true."
                            )
                        }
                    ],
                }
            ],
            schema=ArbiterGeneration,
            max_tokens=2000,
            deadline=time.monotonic() + 60,
            system_prompt=load_prompt("arbiter").body,
        )
        print("\n[OK] Arbiter schema converse succeeded:")
        print(result.model_dump())
    except Exception as exc:  # noqa: BLE001 - we want the full chain
        print(f"\n[FAILED] {type(exc).__name__}: {exc}")
        cause = exc.__cause__
        if cause is not None:
            print("\n--- underlying cause ---")
            traceback.print_exception(type(cause), cause, cause.__traceback__)


if __name__ == "__main__":
    asyncio.run(main())
