"""Official mode admits nothing but live sources.

`official` is the judged run: no fixtures, no recorded bundles, no canned answers.
Most of that promise is enforced by absence, and absence is only trustworthy if a
test asserts it — so this file checks the *code*, not just behaviour:

- production modules never import or read the test fixture tree;
- no recorded-response loader exists at all, so `official` cannot reach one even by
  accident (the capability is honestly unimplemented rather than quietly available);
- a research adapter in `official` mode really performs its fetch instead of
  short-circuiting to stored data;
- an `official` run may never label its data mode as `recorded_fallback`.
"""

from __future__ import annotations

import pathlib
import re
from datetime import UTC, datetime

import httpx
import pytest
from tests.fakes import FixedClock

from hoya_agent.adapters.port_adapters import RssResearchAdapter
from hoya_agent.application import build_request
from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    Asset,
    DataMode,
    RunConfigSnapshot,
    RunMode,
    SourceStatus,
)

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "hoya_agent"
AS_OF = datetime(2026, 6, 3, tzinfo=UTC)

_FEED = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    "<item><title>Bitcoin ETF flows turn negative</title>"
    "<link>https://www.coindesk.com/markets/story</link>"
    "<pubDate>Tue, 02 Jun 2026 12:00:00 +0000</pubDate></item>"
    "</channel></rss>"
)


def _production_sources() -> list[pathlib.Path]:
    return sorted(SRC.rglob("*.py"))


def test_production_code_never_imports_the_fixture_tree() -> None:
    """Boundary gate: a fixture reachable from `src/` could serve an official run."""
    offenders = [
        path.relative_to(SRC).as_posix()
        for path in _production_sources()
        if re.search(r"\b(import\s+tests|from\s+tests)\b", path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"production code must not import tests: {offenders}"


def test_production_code_never_reads_a_fixtures_directory() -> None:
    offenders = [
        path.relative_to(SRC).as_posix()
        for path in _production_sources()
        if "tests/fixtures" in path.read_text(encoding="utf-8").replace("\\", "/")
    ]
    assert offenders == [], f"production code must not reference fixtures: {offenders}"


def test_no_recorded_response_loader_exists_in_production_code() -> None:
    """`demo` recorded fallback is documented as unimplemented; prove it is absent.

    If someone adds a loader later, this test fails and forces the run-mode gate to
    be written at the same time — which is the point.
    """
    pattern = re.compile(r"recorded_(bundle|response|fallback)\s*\(|load_recorded|replay_bundle")
    offenders = [
        path.relative_to(SRC).as_posix()
        for path in _production_sources()
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        "a recorded-response loader exists but no official-mode gate protects it: "
        f"{offenders}"
    )


async def test_official_mode_research_adapter_actually_fetches() -> None:
    """No canned short-circuit: the adapter must hit its transport in official mode."""
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=_FEED)

    request = build_request(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        run_mode=RunMode.official,  # the cutoff is frozen from the clock, never supplied
        now=AS_OF,
        run_id_suffix="off1",
    )
    context = build_run_context(request, FixedClock(AS_OF))
    adapter = RssResearchAdapter(
        feed_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
        source_name="CoinDesk",
        publisher_domain="coindesk.com",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await adapter.fetch(operation="fetch_rss_news", context=context)

    assert calls, "official mode must reach the live provider, not stored data"
    assert result.status in (SourceStatus.ok, SourceStatus.empty)
    for record in result.data or []:
        # Provenance must be the real publisher, never a fixture label.
        assert record.metadata["original_publisher"] == "coindesk.com"
        assert record.fetched_at is not None


def test_official_mode_rejects_a_caller_supplied_cutoff() -> None:
    """Replaying an old cutoff is how a stale run gets relabelled as official."""
    with pytest.raises(ValueError):
        build_request(
            question="BTC 近期市場行為？",
            assets=[Asset.BTC],
            run_mode=RunMode.official,
            now=AS_OF,
            run_id_suffix="off2",
            analysis_as_of=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_rehearsal_may_supply_a_cutoff_so_runs_stay_reproducible() -> None:
    request = build_request(
        question="BTC 近期市場行為？",
        assets=[Asset.BTC],
        run_mode=RunMode.rehearsal,
        now=AS_OF,
        run_id_suffix="reh1",
        analysis_as_of=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert request.analysis_as_of == datetime(2026, 5, 31, tzinfo=UTC)


def _snapshot_kwargs(**overrides) -> dict:
    payload = {
        "schema_version": "1.0",
        "prompt_version": "v1",
        "policy_version": "1.0",
        "run_id": "run_20260603_000000_off3",
        "run_mode": RunMode.official,
        "requested_run_mode": RunMode.official,
        "effective_run_mode": RunMode.official,
        "requested_data_mode": DataMode.live,
        "effective_data_mode": DataMode.live,
        "question": "BTC 近期市場行為？",
        "assets": [Asset.BTC],
        "analysis_as_of": AS_OF,
        "requested_at": AS_OF,
        "deadline_seconds": 900,
        "terminal_state": "completed",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("mode", [DataMode.fixture, DataMode.recorded_fallback])
def test_official_run_config_cannot_claim_fixture_or_recorded_data(mode: DataMode) -> None:
    """The artifact of record must never say an official run replayed something."""
    with pytest.raises(ValueError):
        RunConfigSnapshot(**_snapshot_kwargs(effective_data_mode=mode))
