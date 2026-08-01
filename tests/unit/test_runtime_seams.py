from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from hoya_agent.clock import build_run_context
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    RawSourceRecord,
    ResearchPlan,
    ResearchStep,
    RunMode,
    SourceType,
    WorkerResult,
    WorkerStatus,
)
from hoya_agent.ports import StaticToolRegistry


class FixedClock:
    def __init__(self, now: datetime, monotonic: float = 100.0) -> None:
        self._now = now
        self._monotonic = monotonic

    def now_utc(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic


def make_request(mode: RunMode, analysis_as_of: datetime) -> AnalysisRequest:
    return AnalysisRequest(
        question="分析 BTC 市場",
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 0, tzinfo=UTC),
        analysis_as_of=analysis_as_of,
        deadline_seconds=900,
        run_mode=mode,
        run_id="run_20260801_120000_test",
    )


def test_official_context_freezes_cutoff_from_injected_clock() -> None:
    clock_now = datetime(2026, 8, 1, 4, 5, tzinfo=UTC)
    supplied = datetime(2020, 1, 1, tzinfo=UTC)

    context = build_run_context(make_request(RunMode.official, supplied), FixedClock(clock_now))

    assert context.analysis_as_of == clock_now
    assert context.request.analysis_as_of == clock_now
    assert context.deadline_monotonic == 1000.0
    with pytest.raises(ValidationError):
        context.analysis_as_of = supplied


def test_rehearsal_context_preserves_requested_cutoff() -> None:
    cutoff = datetime(2026, 7, 1, tzinfo=UTC)
    context = build_run_context(
        make_request(RunMode.rehearsal, cutoff),
        FixedClock(datetime(2026, 8, 1, tzinfo=UTC)),
    )
    assert context.analysis_as_of == cutoff


def test_raw_source_record_requires_utc_and_nonblank_content() -> None:
    with pytest.raises(ValidationError):
        RawSourceRecord(
            record_id="rec_001",
            source_name="Example",
            source_type=SourceType.news,
            source_url="https://example.com/story",
            published_at=None,
            fetched_at=datetime(2026, 8, 1),
            title="title",
            content="content",
            query_or_parameters="BTC",
        )


def test_research_plan_matches_reasoning_contract() -> None:
    plan = ResearchPlan(
        plan_version="planner-v1",
        assets=[Asset.BTC],
        question_summary="BTC 市場",
        lookback_days=14,
        required_evidence_types=[SourceType.market, SourceType.news],
        planned_steps=[
            ResearchStep(step_id="s1", tool_operation="market.daily", rationale="價格證據")
        ],
    )
    assert plan.planned_steps[0].tool_operation == "market.daily"


def test_worker_result_has_only_terminal_worker_statuses() -> None:
    result = WorkerResult(status=WorkerStatus.completed)
    assert result.status is WorkerStatus.completed
    with pytest.raises(ValidationError):
        WorkerResult(status="cancelled")


@pytest.mark.asyncio
async def test_static_tool_registry_rejects_unallowlisted_operation_before_invocation() -> None:
    calls: list[dict[str, object]] = []

    async def fetch(**params: object) -> object:
        calls.append(params)
        return ["ok"]

    registry = StaticToolRegistry({"market.daily": fetch})

    with pytest.raises(PermissionError):
        await registry.invoke("evil.dynamic", payload="external content")
    assert calls == []
    assert registry.operations() == ("market.daily",)


@pytest.mark.asyncio
async def test_static_tool_registry_cannot_be_mutated_by_retrieved_content() -> None:
    async def fetch(**params: object) -> object:
        params["register"] = "evil.dynamic"
        return params

    source_mapping = {"market.daily": fetch}
    registry = StaticToolRegistry(source_mapping)
    source_mapping["evil.dynamic"] = fetch

    await registry.invoke("market.daily", register="ignored")
    assert registry.operations() == ("market.daily",)
    assert not registry.is_allowed("evil.dynamic")




# ===========================================================================
# Corrective regression tests.
#
# Finding A: all four analysis_as_of behaviours, including omission.
# Finding F: adapter seams return SourceResult and are structurally
#            substitutable for the generic SourceAdapter.
# Plus FixedClock.advance() monotonicity.
# ===========================================================================

import inspect  # noqa: E402

from tests.fakes import (  # noqa: E402
    FakeMarketDataAdapter,
    FakeResearchSourceAdapter,
)
from tests.fakes import FixedClock as ReusableFixedClock  # noqa: E402

from hoya_agent.models import (  # noqa: E402
    DataMode,
    SourceResult,
    SourceStatus,
)
from hoya_agent.ports import (  # noqa: E402
    MarketDataAdapter,
    ResearchSourceAdapter,
    SourceAdapter,
)

_CLOCK_NOW = datetime(2026, 8, 1, 4, 5, tzinfo=UTC)
_SUPPLIED = datetime(2026, 7, 1, tzinfo=UTC)


def make_request_without_cutoff(mode: RunMode) -> AnalysisRequest:
    """A request that omits analysis_as_of entirely (evidence-contracts §2)."""
    return AnalysisRequest(
        question="分析 BTC 市場",
        assets=[Asset.BTC],
        requested_at=datetime(2026, 8, 1, 4, 0, tzinfo=UTC),
        deadline_seconds=900,
        run_mode=mode,
        run_id="run_20260801_120000_test",
    )


# --- Finding A: the four cutoff behaviours --------------------------------


def test_official_omitting_cutoff_freezes_the_injected_clock() -> None:
    context = build_run_context(
        make_request_without_cutoff(RunMode.official), FixedClock(_CLOCK_NOW)
    )

    assert context.analysis_as_of == _CLOCK_NOW
    assert context.request.analysis_as_of == _CLOCK_NOW


def test_official_supplying_cutoff_still_ignores_it() -> None:
    context = build_run_context(
        make_request(RunMode.official, _SUPPLIED), FixedClock(_CLOCK_NOW)
    )

    assert context.analysis_as_of == _CLOCK_NOW


@pytest.mark.parametrize("mode", [RunMode.rehearsal, RunMode.demo])
def test_rehearsal_and_demo_preserve_an_explicit_cutoff(mode: RunMode) -> None:
    context = build_run_context(make_request(mode, _SUPPLIED), FixedClock(_CLOCK_NOW))

    assert context.analysis_as_of == _SUPPLIED


@pytest.mark.parametrize("mode", [RunMode.rehearsal, RunMode.demo])
def test_rehearsal_and_demo_without_cutoff_use_the_injected_clock(mode: RunMode) -> None:
    context = build_run_context(
        make_request_without_cutoff(mode), FixedClock(_CLOCK_NOW)
    )

    assert context.analysis_as_of == _CLOCK_NOW
    assert context.request.analysis_as_of == _CLOCK_NOW


def test_effective_context_cutoff_is_always_a_real_strict_utc_datetime() -> None:
    for mode in (RunMode.official, RunMode.rehearsal, RunMode.demo):
        context = build_run_context(
            make_request_without_cutoff(mode), FixedClock(_CLOCK_NOW)
        )
        assert context.analysis_as_of is not None
        assert context.analysis_as_of.utcoffset() == timedelta(0)


def test_effective_context_cutoff_is_immutable() -> None:
    context = build_run_context(
        make_request_without_cutoff(RunMode.official), FixedClock(_CLOCK_NOW)
    )

    with pytest.raises(ValidationError):
        context.analysis_as_of = _SUPPLIED


def test_build_run_context_rejects_a_non_utc_clock() -> None:
    class BadClock:
        def now_utc(self) -> datetime:
            return datetime(2026, 8, 1, 4, 5, tzinfo=timezone(timedelta(hours=8)))

        def monotonic(self) -> float:
            return 100.0

    with pytest.raises(ValueError):
        build_run_context(make_request_without_cutoff(RunMode.official), BadClock())


# --- FixedClock monotonicity ---------------------------------------------


def test_reusable_fixed_clock_rejects_negative_advance() -> None:
    """A monotonic reading must never be able to go backwards."""
    clock = ReusableFixedClock(_CLOCK_NOW, monotonic_value=100.0)

    with pytest.raises(ValueError):
        clock.advance(-1)


def test_reusable_fixed_clock_advances_both_readings() -> None:
    clock = ReusableFixedClock(_CLOCK_NOW, monotonic_value=100.0)

    clock.advance(30)

    assert clock.monotonic() == 130.0
    assert clock.now_utc() == _CLOCK_NOW + timedelta(seconds=30)


def test_reusable_fixed_clock_allows_zero_advance() -> None:
    clock = ReusableFixedClock(_CLOCK_NOW, monotonic_value=100.0)

    clock.advance(0)

    assert clock.monotonic() == 100.0


# --- Finding F: adapter seams return SourceResult ------------------------


def test_market_adapter_is_structurally_substitutable_for_source_adapter() -> None:
    adapter = FakeMarketDataAdapter()

    assert isinstance(adapter, MarketDataAdapter)
    assert isinstance(adapter, SourceAdapter)


def test_research_adapter_is_structurally_substitutable_for_source_adapter() -> None:
    adapter = FakeResearchSourceAdapter()

    assert isinstance(adapter, ResearchSourceAdapter)
    assert isinstance(adapter, SourceAdapter)


def test_market_adapter_protocol_returns_source_result() -> None:
    """The seam itself, not just the fake, must promise a SourceResult."""
    for method in ("fetch_daily_bars", "fetch_snapshot"):
        annotation = inspect.signature(
            getattr(MarketDataAdapter, method)
        ).return_annotation
        assert "SourceResult" in str(annotation), f"{method} -> {annotation}"


def test_research_adapter_protocol_returns_source_result() -> None:
    annotation = inspect.signature(ResearchSourceAdapter.fetch).return_annotation

    assert "SourceResult" in str(annotation)


def test_generic_source_adapter_protocol_returns_source_result() -> None:
    annotation = inspect.signature(SourceAdapter.fetch).return_annotation

    assert "SourceResult" in str(annotation)


@pytest.mark.asyncio
async def test_fake_market_adapter_yields_a_source_result_envelope() -> None:
    result = await FakeMarketDataAdapter().fetch_daily_bars(asset=Asset.BTC)

    assert isinstance(result, SourceResult)
    assert result.status is SourceStatus.ok


@pytest.mark.asyncio
async def test_fake_market_adapter_snapshot_yields_source_result() -> None:
    result = await FakeMarketDataAdapter().fetch_snapshot(asset=Asset.BTC)

    assert isinstance(result, SourceResult)


@pytest.mark.asyncio
async def test_fake_research_adapter_yields_records_in_a_source_result() -> None:
    records = [
        RawSourceRecord(
            record_id="rec_001",
            source_name="Example",
            source_type=SourceType.news,
            source_url="https://example.com/a",
            published_at=None,
            fetched_at=_CLOCK_NOW,
            title="title",
            content="content",
            query_or_parameters="currencies=BTC",
        )
    ]

    result = await FakeResearchSourceAdapter(records=records).fetch(operation="news")

    assert isinstance(result, SourceResult)
    assert result.data is not None
    assert result.data[0].record_id == "rec_001"


@pytest.mark.asyncio
async def test_fake_adapters_report_failure_as_status_not_exception() -> None:
    result = await FakeResearchSourceAdapter(status=SourceStatus.timeout).fetch(
        operation="news"
    )

    assert result.status is SourceStatus.timeout
    assert result.error_category == "timeout"
    assert result.data is None


# --- DataMode reaches the reusable summary fake path --------------------


def test_data_mode_enum_is_importable_for_downstream_owners() -> None:
    assert DataMode.live.value == "live"
    assert DataMode.fixture.value == "fixture"
    assert DataMode.recorded_fallback.value == "recorded_fallback"
