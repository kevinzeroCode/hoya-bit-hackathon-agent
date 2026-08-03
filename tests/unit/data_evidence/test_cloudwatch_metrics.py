"""Unit tests for the optional CloudWatch run metrics (Task 21). No real AWS
credentials or network access — a fake client is injected throughout."""

from __future__ import annotations

from hoya_agent.adapters.cloudwatch_metrics import NAMESPACE, emit_run_metrics


class FakeCloudWatchClient:
    def __init__(self, *, raise_on_publish: bool = False) -> None:
        self.calls: list[dict] = []
        self._raise_on_publish = raise_on_publish

    def put_metric_data(self, **kwargs):
        if self._raise_on_publish:
            raise RuntimeError("simulated CloudWatch outage")
        self.calls.append(kwargs)


def test_publishes_the_three_run_level_metrics():
    client = FakeCloudWatchClient()

    result = emit_run_metrics(
        terminal_state="degraded", duration_seconds=42.5, evidence_count=6, client=client
    )

    assert result.published is True
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["Namespace"] == NAMESPACE
    names = {m["MetricName"] for m in call["MetricData"]}
    assert names == {"RunCompleted", "RunDurationSeconds", "EvidenceCount"}
    run_completed = next(m for m in call["MetricData"] if m["MetricName"] == "RunCompleted")
    assert run_completed["Dimensions"] == [{"Name": "TerminalState", "Value": "degraded"}]


def test_custom_namespace_is_respected():
    client = FakeCloudWatchClient()
    emit_run_metrics(
        terminal_state="completed",
        duration_seconds=10.0,
        evidence_count=1,
        namespace="CustomNS",
        client=client,
    )
    assert client.calls[0]["Namespace"] == "CustomNS"


def test_publish_failure_degrades_without_raising():
    client = FakeCloudWatchClient(raise_on_publish=True)
    result = emit_run_metrics(
        terminal_state="failed", duration_seconds=5.0, evidence_count=0, client=client
    )
    assert result.published is False
    assert "CloudWatch publish failed" in result.note


def test_client_construction_failure_degrades_without_raising(monkeypatch):
    import sys
    import types

    fake_boto3 = types.SimpleNamespace(
        client=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no AWS credentials"))
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    result = emit_run_metrics(terminal_state="completed", duration_seconds=1.0, evidence_count=1)

    assert result.published is False
    assert "unavailable" in result.note
