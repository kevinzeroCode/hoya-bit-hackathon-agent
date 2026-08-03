"""CloudWatch custom metrics for the EC2 deployment — optional, additive,
never blocking (Task 21).

Publishes three run-level numbers a judge or operator would actually want on
a dashboard: whether the run completed/degraded/failed, how long it took, and
how much Evidence it gathered. Nothing here computes a new number — every
value is a parameter already available on `RunSummary` once a run finishes.

Same client-injection pattern as `adapters/s3_mirror.py` and
`adapters/bedrock.py::BedrockLLMClient`: lazily constructed only when
actually used, and injectable, so no test here needs real AWS credentials.

**Not wired into `application.py` in this change** — see
`docs/Implementation-Plan.md` §9 Task 21 for where a future change would
call `emit_run_metrics(...)` (right after `ApplicationService.run()` returns
its `RunSummary`) and why this session stopped short of that wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NAMESPACE = "HoyaAgent"


@dataclass(frozen=True)
class MetricsResult:
    published: bool
    note: str = ""


def emit_run_metrics(
    *,
    terminal_state: str,
    duration_seconds: float,
    evidence_count: int,
    namespace: str = NAMESPACE,
    client: Any = None,
) -> MetricsResult:
    """Publish `RunCompleted` (dimensioned by `terminal_state`),
    `RunDurationSeconds` and `EvidenceCount`. Never raises — a metrics
    failure must never affect the run it describes.
    """
    if client is None:
        try:
            import boto3  # imported lazily so offline tests need no AWS setup

            client = boto3.client("cloudwatch")
        except Exception as exc:  # noqa: BLE001 - any setup failure degrades, never raises
            return MetricsResult(False, f"CloudWatch client unavailable ({type(exc).__name__})")

    try:
        client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": "RunCompleted",
                    "Dimensions": [{"Name": "TerminalState", "Value": terminal_state}],
                    "Value": 1,
                    "Unit": "Count",
                },
                {
                    "MetricName": "RunDurationSeconds",
                    "Value": duration_seconds,
                    "Unit": "Seconds",
                },
                {
                    "MetricName": "EvidenceCount",
                    "Value": float(evidence_count),
                    "Unit": "Count",
                },
            ],
        )
    except Exception as exc:  # noqa: BLE001 - metrics are best-effort, never block a run
        return MetricsResult(False, f"CloudWatch publish failed ({type(exc).__name__})")
    return MetricsResult(True)
