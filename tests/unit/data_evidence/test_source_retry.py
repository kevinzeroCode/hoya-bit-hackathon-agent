"""One deadline-bound retry for research sources.

Contract: at most one retry, only for transient failures, and only inside the
acquisition window that already owns the branch. A deterministic failure is never
retried as if it were a network fault — a malformed payload will be malformed
again, and a missing credential will still be missing.

The retry exists because the judged run happens once. Without it a single
transient timeout becomes a permanent source gap in the one run that counts.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from hoya_agent.adapters.port_adapters import fetch_with_single_retry
from hoya_agent.models import RawSourceRecord, SourceResult, SourceStatus, SourceType

NOW = datetime(2026, 6, 3, tzinfo=UTC)


def _result(status: SourceStatus, *, records: int = 0) -> SourceResult[list[RawSourceRecord]]:
    return SourceResult[list[RawSourceRecord]](
        source_name="TestSource",
        status=status,
        data=[
            RawSourceRecord(
                record_id=f"rec-{index}",
                source_name="TestSource",
                source_type=SourceType.news,
                fetched_at=NOW,
                content="body",
                query_or_parameters="q=1",
            )
            for index in range(records)
        ],
        fetched_at=NOW,
    )


class ScriptedAdapter:
    def __init__(self, *results) -> None:
        self._results = list(results)
        self.calls = 0

    async def fetch(self, *, operation: str, **params: object):
        del operation, params
        self.calls += 1
        if not self._results:
            raise AssertionError("adapter called more times than scripted")
        outcome = self._results.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Sleeper:
    """Records backoff instead of spending it — no real waiting in tests."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


async def test_transient_timeout_is_retried_once_and_can_succeed() -> None:
    adapter = ScriptedAdapter(_result(SourceStatus.timeout), _result(SourceStatus.ok, records=1))
    sleeper = Sleeper()

    result, notes = await fetch_with_single_retry(
        adapter, operation="fetch_rss_news", params={}, sleeper=sleeper
    )

    assert adapter.calls == 2
    assert result.status is SourceStatus.ok
    assert result.data and len(result.data) == 1
    assert any("重試" in note for note in notes)
    assert sleeper.waits and sleeper.waits[0] > 0, "backoff must be bounded but non-zero"


async def test_http_error_is_retried_once() -> None:
    adapter = ScriptedAdapter(_result(SourceStatus.http_error), _result(SourceStatus.ok, records=1))

    result, _ = await fetch_with_single_retry(
        adapter, operation="fetch_rss_news", params={}, sleeper=Sleeper()
    )

    assert adapter.calls == 2
    assert result.status is SourceStatus.ok


async def test_retry_happens_at_most_once() -> None:
    adapter = ScriptedAdapter(_result(SourceStatus.timeout), _result(SourceStatus.timeout))

    result, notes = await fetch_with_single_retry(
        adapter, operation="fetch_rss_news", params={}, sleeper=Sleeper()
    )

    assert adapter.calls == 2, "exactly one retry, never a loop"
    assert result.status is SourceStatus.timeout
    assert any("重試" in note for note in notes)


@pytest.mark.parametrize(
    "status",
    [SourceStatus.malformed, SourceStatus.rejected, SourceStatus.empty],
)
async def test_deterministic_outcomes_are_not_retried(status: SourceStatus) -> None:
    adapter = ScriptedAdapter(_result(status))

    result, notes = await fetch_with_single_retry(
        adapter, operation="fetch_cryptopanic_news", params={}, sleeper=Sleeper()
    )

    assert adapter.calls == 1
    assert result.status is status
    assert notes == []


async def test_success_never_retries() -> None:
    adapter = ScriptedAdapter(_result(SourceStatus.ok, records=2))

    result, notes = await fetch_with_single_retry(
        adapter, operation="fetch_rss_news", params={}, sleeper=Sleeper()
    )

    assert adapter.calls == 1
    assert notes == []
    assert result.status is SourceStatus.ok


async def test_cancellation_is_never_swallowed() -> None:
    adapter = ScriptedAdapter(asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await fetch_with_single_retry(
            adapter, operation="fetch_rss_news", params={}, sleeper=Sleeper()
        )

    assert adapter.calls == 1, "a cancelled acquisition window must not be retried into"


async def test_a_raising_adapter_is_retried_once_then_reported() -> None:
    adapter = ScriptedAdapter(TimeoutError("transient"), _result(SourceStatus.ok, records=1))

    result, notes = await fetch_with_single_retry(
        adapter, operation="fetch_rss_news", params={}, sleeper=Sleeper()
    )

    assert adapter.calls == 2
    assert result.status is SourceStatus.ok
    assert any("重試" in note for note in notes)


async def test_backoff_stays_within_the_configured_bound() -> None:
    adapter = ScriptedAdapter(_result(SourceStatus.timeout), _result(SourceStatus.timeout))
    sleeper = Sleeper()

    await fetch_with_single_retry(
        adapter,
        operation="fetch_rss_news",
        params={},
        sleeper=sleeper,
        backoff_seconds=0.75,
    )

    assert len(sleeper.waits) == 1
    assert 0 < sleeper.waits[0] <= 0.75, "jittered backoff must never exceed its bound"
