"""Single use-case entry point: one request in, four artifacts and a `RunSummary` out.

The service owns run identity, the immutable cutoff, the run directory, and the
artifact write order. It contains no adapter, provider, or UI logic, and it does
not decide stage order — that is the pipeline's job (Task 3).

Write order is the resilience design: `run_config.json` exists before any analysis
work starts, execution events stream while the run is in flight, `evidence.json`
lands as soon as the ledger exists so a reasoning failure cannot erase
traceability, and `final_report.md` is written last. When analysis is missing the
report becomes the deterministic insufficient-data report rather than a missing
file.

The application consumes the canonical runtime seams from ``models`` and
``ports``; there is no parallel provisional contract.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

import httpx

from hoya_agent.adapters.official import OFFICIAL_FEEDS
from hoya_agent.adapters.port_adapters import (
    DEFAULT_RETRY_BACKOFF_SECONDS,
    CryptoPanicResearchAdapter,
    FearGreedResearchAdapter,
    OfficialAnnouncementsResearchAdapter,
    RssResearchAdapter,
    SourceUnavailable,
    fetch_with_single_retry,
)
from hoya_agent.clock import build_run_context
from hoya_agent.evidence.policies import registered_domain
from hoya_agent.models import (
    AnalysisRequest,
    Asset,
    DataMode,
    DegradationEvent,
    EvidenceLedger,
    ExecutionEvent,
    ResearchPlan,
    RunConfigSnapshot,
    RunContext,
    RunMode,
    RunSummary,
    SourceStatus,
    TerminalState,
    project_evidence_list,
)
from hoya_agent.orchestration.pipeline import (
    AnalysisPipeline,
    DeadlineAwarePipeline,
    OrganizerCsvPipeline,
    PipelineOutcome,
)
from hoya_agent.ports import Clock, ProgressSink, StaticToolRegistry
from hoya_agent.reasoning.arbiter import Arbiter
from hoya_agent.reasoning.arbiter_output import ArbiterOutput
from hoya_agent.reasoning.planner import (
    DEFAULT_LOOKBACK_DAYS,
    Planner,
    default_plan_payload,
)
from hoya_agent.reasoning.research_agent import ResearchAgent
from hoya_agent.reasoning.research_extractor import ResearchExtraction
from hoya_agent.reporting.advice_lint import advice_violations
from hoya_agent.reporting.artifacts import (
    EVIDENCE_LEDGER,
    EVIDENCE_LIST,
    FINAL_REPORT,
    RUN_CONFIG,
    LocalArtifactStore,
)
from hoya_agent.reporting.renderer import build_insufficient_data_result, render

SCHEMA_VERSION = "1.0"
POLICY_VERSION = "1.0"
PROMPT_VERSION = "v1"

# ── Research composition (S6) ───────────────────────────────────────────────
#
# Operation names are the contract between the static registry, the Planner's
# allowlist and the fixed skip order. The pipeline does not guess which work is
# optional; the composition root declares it here, which is what makes S4's skip
# order fire in a real run instead of only in its unit tests.

#: Designated baseline research source (S0 preflight): first-party outlet RSS.
RESEARCH_OPERATION_RSS = "fetch_rss_news"
#: Best-effort per-project official announcements.
RESEARCH_OPERATION_OFFICIAL = "fetch_official_announcements"
#: Whole-market sentiment context; never a per-coin signal.
RESEARCH_OPERATION_FEAR_GREED = "fetch_fear_greed"
#: Aggregator breadth search, used to look for opposing signals.
RESEARCH_OPERATION_CRYPTOPANIC = "fetch_cryptopanic_news"

#: Never surrendered to the clock.
BASELINE_RESEARCH_OPERATIONS = (RESEARCH_OPERATION_RSS,)
#: Given up first when the acquisition window is short (after H3, which is
#: permanently disabled and therefore never scheduled at all).
OPTIONAL_CONTEXT_OPERATIONS = (
    RESEARCH_OPERATION_FEAR_GREED,
    RESEARCH_OPERATION_OFFICIAL,
)
#: Given up last, because dropping the counter-signal search costs the report its
#: opposing view.
COUNTER_SIGNAL_OPERATIONS = (RESEARCH_OPERATION_CRYPTOPANIC,)


@dataclass(frozen=True)
class NewsFeed:
    """One configured first-party outlet feed."""

    feed_url: str
    source_name: str
    publisher_domain: str


#: Coin-agnostic outlets: one feed serves all five assets, filtered by symbol.
DEFAULT_NEWS_FEEDS: tuple[NewsFeed, ...] = (
    NewsFeed(
        feed_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
        source_name="CoinDesk",
        publisher_domain="coindesk.com",
    ),
    NewsFeed(
        feed_url="https://decrypt.co/feed",
        source_name="Decrypt",
        publisher_domain="decrypt.co",
    ),
)

#: Host allowlist enforced *before* any external call. A URL outside this set is
#: rejected at construction, so no plan, prompt or feed payload can widen it.
ALLOWED_RESEARCH_HOSTS = frozenset(
    {
        "coindesk.com",
        "decrypt.co",
        "cointelegraph.com",
        "theblock.co",
        "cryptopanic.com",
        "alternative.me",
        *(config["publisher_domain"] for config in OFFICIAL_FEEDS.values()),
    }
)


def _require_allowlisted_host(url: str) -> str:
    """Reject a non-allowlisted host before it can ever be fetched."""
    host = registered_domain(url)
    if host not in ALLOWED_RESEARCH_HOSTS:
        raise ValueError(f"research host is not allowlisted: {host}")
    return host


class ResearchToolRegistry(StaticToolRegistry):
    """A static registry that also carries its own disclosure channel and HTTP client.

    The sink travels with the registry so a caller that builds its own cannot
    silently disconnect it — the alternative (a separate `note_sink` argument on
    both factories) loses every retry disclosure the moment someone passes
    `tool_registry=` on its own.

    `http_client` is the single `httpx.AsyncClient` shared by every research adapter
    in the run, per the one-client-per-run rule. The registry owns it, so the caller
    closes it with `await registry.aclose()` once the run is finished.
    """

    def __init__(
        self,
        operations: Mapping[str, object],
        *,
        note_sink: list[str],
        http_client: httpx.AsyncClient | None = None,
        owns_client: bool = False,
    ) -> None:
        super().__init__(operations)  # type: ignore[arg-type]
        self.note_sink = note_sink
        self.http_client = http_client
        self._owns_client = owns_client

    async def aclose(self) -> None:
        """Release the shared connection pool. Safe to call more than once."""
        if self._owns_client and self.http_client is not None:
            await self.http_client.aclose()
            self._owns_client = False


def build_research_tool_registry(
    *,
    news_feeds: Sequence[NewsFeed] = DEFAULT_NEWS_FEEDS,
    cryptopanic_api_token: str | None = None,
    client: httpx.AsyncClient | None = None,
    official_feed_overrides: Mapping[str, Mapping[str, str]] | None = None,
    include_optional: bool = True,
    note_sink: list[str] | None = None,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> ResearchToolRegistry:
    """Static, immutable map of research operations to port-conforming adapters.

    Every handler returns `list[RawSourceRecord]`, which is the only shape the
    frozen Research Agent consumes. A source that fails raises `SourceUnavailable`
    so the agent records it as a source gap; a source that simply has nothing to
    say returns an empty list, because a gap and a failure are different facts.

    `note_sink` receives disclosures that have no other route out — most importantly
    "this source only succeeded on the retry". A recovered source is not a failure,
    so the agent never hears about it, but a flaky source in the judged run is
    something the report must still admit.
    """
    notes = note_sink if note_sink is not None else []
    # One client for the whole run, shared by every research adapter. Created here
    # rather than per adapter so the connection pool, timeouts and user agent are
    # identical across sources.
    owns_client = client is None
    http_client: httpx.AsyncClient = client or httpx.AsyncClient(  # type: ignore[assignment]
        headers={"User-Agent": "hoya-market-agent/0.1 (research)"},
        follow_redirects=True,
        timeout=httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0),
    )
    for feed in news_feeds:
        _require_allowlisted_host(feed.feed_url)
    for config in (official_feed_overrides or OFFICIAL_FEEDS).values():
        _require_allowlisted_host(config["feed_url"])

    rss_adapters = [
        RssResearchAdapter(
            feed_url=feed.feed_url,
            source_name=feed.source_name,
            publisher_domain=feed.publisher_domain,
            client=http_client,
        )
        for feed in news_feeds
    ]

    async def _collect(adapter: object, operation: str, params: Mapping[str, object]) -> list:
        # One retry, bounded by the acquisition window that already owns the branch.
        # The judged run happens once: without this, a single transient timeout is a
        # permanent source gap in the only run that counts.
        result, retry_notes = await fetch_with_single_retry(
            adapter,
            operation=operation,
            params=params,
            backoff_seconds=retry_backoff_seconds,
        )
        notes.extend(retry_notes)
        records = list(result.data or [])
        if result.status not in (SourceStatus.ok, SourceStatus.empty):
            raise SourceUnavailable(
                operation,
                result.status,
                "; ".join([*retry_notes, result.error_category or ""]).strip("; "),
            )
        return records

    async def fetch_rss(**params: object) -> list:
        records: list = []
        failures: list[str] = []
        for adapter in rss_adapters:
            try:
                records.extend(await _collect(adapter, RESEARCH_OPERATION_RSS, params))
            except SourceUnavailable as exc:
                # One outlet failing is not the baseline failing; only a total
                # baseline outage is escalated.
                failures.append(str(exc))
        if not records and failures:
            raise SourceUnavailable(
                RESEARCH_OPERATION_RSS, SourceStatus.http_error, "; ".join(failures)
            )
        return records

    async def fetch_official(**params: object) -> list:
        adapter = OfficialAnnouncementsResearchAdapter(
            client=http_client,
            feed_overrides=dict(official_feed_overrides) if official_feed_overrides else None,
        )
        return await _collect(adapter, RESEARCH_OPERATION_OFFICIAL, params)

    async def fetch_fear_greed_op(**params: object) -> list:
        adapter = FearGreedResearchAdapter(client=http_client)
        return await _collect(adapter, RESEARCH_OPERATION_FEAR_GREED, params)

    async def fetch_cryptopanic(**params: object) -> list:
        adapter = CryptoPanicResearchAdapter(
            api_token=cryptopanic_api_token,
            client=http_client,
        )
        return await _collect(adapter, RESEARCH_OPERATION_CRYPTOPANIC, params)

    operations: dict[str, object] = {RESEARCH_OPERATION_RSS: fetch_rss}
    if include_optional:
        operations[RESEARCH_OPERATION_FEAR_GREED] = fetch_fear_greed_op
        operations[RESEARCH_OPERATION_OFFICIAL] = fetch_official
        # Without a token the adapter reports `rejected`; keeping the operation
        # registered means the gap is disclosed rather than silently absent.
        operations[RESEARCH_OPERATION_CRYPTOPANIC] = fetch_cryptopanic
    return ResearchToolRegistry(  # type: ignore[arg-type]
        operations,
        note_sink=notes,
        http_client=http_client,
        owns_client=owns_client,
    )


@dataclass
class DeterministicPlanner:
    """Planner substitute for runs with no LLM configured.

    Returns the same allowlisted default plan the frozen Planner falls back to, so
    the research branch still runs offline instead of being skipped entirely. The
    reason string is carried into the plan notes, keeping the substitution visible.
    """

    tool_registry: object
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    prompt_version: str = "deterministic-default"

    async def run(self, *, request: object, deadline: float) -> tuple[ResearchPlan, list[str]]:
        del deadline
        operations = tuple(self.tool_registry.operations())  # type: ignore[attr-defined]
        assets = [str(getattr(asset, "value", asset)) for asset in getattr(request, "assets", ())]
        plan = ResearchPlan.model_validate(
            default_plan_payload(
                assets=assets,
                allowed_operations=operations,
                lookback_days=self.lookback_days,
                reason="未設定 LLM，使用決定論預設計畫",
            )
        )
        return plan, ["Planner 未使用 LLM，改以決定論預設計畫執行允許清單操作。"]


def build_research_pipeline(
    *,
    clock: Clock,
    llm: object | None = None,
    tool_registry: StaticToolRegistry | None = None,
    market_pipeline: AnalysisPipeline | None = None,
    arbiter: object | None = None,
    data_dir: Path | None = None,
    analysis_date: object | None = None,
    cryptopanic_api_token: str | None = None,
    client: httpx.AsyncClient | None = None,
    source_note_sink: list[str] | None = None,
) -> DeadlineAwarePipeline:
    """Compose the H2-Lite pipeline with the market *and* research branches live.

    This is the composition root the fixed skip order was waiting for: the optional
    and counter-signal operation lists are declared here, so a short acquisition
    window trims optional context first and the counter-signal search last, and
    baseline research is never trimmed.

    With `llm=None` the Planner degrades deterministically and the research branch
    still executes its allowlisted fetches; bounded extraction itself needs a
    model, and that remains the S8 live gate.

    When an `llm` is supplied and no `arbiter` is given, the Arbiter is wired with
    `ArbiterOutput` as its structured-output schema — `AnalysisResult` cannot serve
    that role, because it requires the frozen request context the model must not
    restate. `orchestration/pipeline.py` projects the output back.
    """
    source_notes = source_note_sink if source_note_sink is not None else []
    registry = tool_registry or build_research_tool_registry(
        cryptopanic_api_token=cryptopanic_api_token, client=client, note_sink=source_notes
    )
    # The sink travels with the registry, so a caller-supplied registry keeps its
    # own channel rather than losing every retry disclosure.
    source_notes = getattr(registry, "note_sink", source_notes)
    market = market_pipeline or OrganizerCsvPipeline(
        data_dir=data_dir, analysis_date=analysis_date  # type: ignore[arg-type]
    )
    planner: object = (
        Planner(llm=llm, plan_schema=ResearchPlan, tool_registry=registry)
        if llm is not None
        else DeterministicPlanner(tool_registry=registry)
    )
    research_agent = (
        ResearchAgent(llm=llm, draft_schema=ResearchExtraction, tool_registry=registry)
        if llm is not None
        else None
    )
    if arbiter is None and llm is not None:
        arbiter = Arbiter(llm=llm, result_schema=ArbiterOutput)
    return DeadlineAwarePipeline(
        clock=clock,
        market_pipeline=market,
        planner=planner,
        research_agent=research_agent,
        arbiter=arbiter,
        optional_operations=OPTIONAL_CONTEXT_OPERATIONS,
        counter_signal_operations=COUNTER_SIGNAL_OPERATIONS,
        source_note_sink=source_notes,
    )


_RUN_ID_TIMESTAMP = "%Y%m%d_%H%M%S"
_SUFFIX_RE = re.compile(r"^[a-z0-9]{2,8}$")


def make_run_id(now: datetime, suffix: str) -> str:
    """Build the `run_YYYYMMDD_HHMMSS_<suffix>` identifier from injected time."""
    if not _SUFFIX_RE.match(suffix):
        raise ValueError("run id suffix must be 2-8 lowercase alphanumeric characters")
    return f"run_{now.strftime(_RUN_ID_TIMESTAMP)}_{suffix}"


def build_request(
    *,
    question: str,
    assets: list[Asset],
    run_mode: RunMode,
    now: datetime,
    run_id_suffix: str,
    analysis_as_of: datetime | None = None,
    deadline_seconds: int = 900,
    enable_conditional_debate: bool = False,
) -> AnalysisRequest:
    """Mint the run identity and freeze the cutoff according to run mode.

    `official` freezes the cutoff to the injected clock and refuses a
    caller-supplied value; rehearsal and demo may replay a fixed cutoff.
    """
    if run_mode is RunMode.official and analysis_as_of is not None:
        raise ValueError("official mode freezes analysis_as_of to the run start and cannot accept one")
    return AnalysisRequest(
        question=question,
        assets=assets,
        requested_at=now,
        analysis_as_of=analysis_as_of if analysis_as_of is not None else now,
        deadline_seconds=deadline_seconds,
        run_mode=run_mode,
        enable_conditional_debate=enable_conditional_debate,
        run_id=make_run_id(now, run_id_suffix),
    )


class ApplicationService:
    def __init__(
        self,
        *,
        artifact_root: Path,
        clock: Clock,
        pipeline: AnalysisPipeline,
        prompt_version: str = PROMPT_VERSION,
        policy_version: str = POLICY_VERSION,
        configured_sources: Sequence[str] = (),
        optional_keys_present: Mapping[str, bool] | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._artifact_root = Path(artifact_root)
        self._clock = clock
        self._pipeline = pipeline
        self._prompt_version = prompt_version
        self._policy_version = policy_version
        self._configured_sources = list(configured_sources)
        self._optional_keys_present = dict(optional_keys_present or {})
        self._stdout = stdout

    async def run(
        self,
        request: AnalysisRequest,
        progress: ProgressSink | None = None,
    ) -> RunSummary:
        context = self._build_context(request)
        store = LocalArtifactStore(self._artifact_root / context.run_id, stdout=self._stdout)
        snapshot = self._initial_snapshot(request, context)

        # run_config.json first: it must exist before any analysis work starts.
        store.write_json(RUN_CONFIG, snapshot.model_dump(mode="json"))

        progress_tasks: list[asyncio.Task[None]] = []

        def emit(event: ExecutionEvent) -> None:
            store.append_event(event)
            if progress is not None:
                sync_emit = getattr(progress, "emit", None)
                if sync_emit is not None:
                    sync_emit(event)
                else:
                    published = progress.publish(event)
                    if inspect.isawaitable(published):
                        progress_tasks.append(asyncio.create_task(published))

        emit(self._event(context, "run", "run_start", "ok", message="run started"))
        if request.run_mode is RunMode.official and request.analysis_as_of != context.analysis_as_of:
            emit(
                self._event(
                    context,
                    "run",
                    "cutoff_frozen",
                    "warning",
                    message="official mode froze analysis_as_of to the injected clock",
                )
            )
        for warning in _asset_mismatch_warnings(request):
            emit(self._event(context, "run", "request_asset_mismatch", "warning", message=warning))

        cancelled_error: asyncio.CancelledError | None = None
        try:
            outcome = await self._pipeline.execute(context, emit)
        except asyncio.CancelledError as exc:
            # Cancellation is never suppressed. It is finalized: the four artifacts
            # are written from what already exists, honestly labelled `cancelled`,
            # and then the error is re-raised at the end of this method. Everything
            # between here and that re-raise must stay await-free, because a further
            # await inside a cancelled task raises again immediately.
            cancelled_error = exc
            outcome = _cancelled_outcome(context, self._clock.now_utc())
            emit(
                self._event(
                    context,
                    "run",
                    "run_cancelled",
                    TerminalState.cancelled.value,
                    message="run cancelled; finalizing artifacts before re-raising",
                )
            )

        # evidence.json as soon as the ledger exists, so a reasoning failure
        # cannot remove traceability.
        ledger = outcome.ledger
        if store.write_json(EVIDENCE_LEDGER, ledger.model_dump(mode="json")):
            emit(
                self._event(
                    context,
                    "artifact",
                    "artifact_write",
                    "ok",
                    output_count=len(ledger.items),
                    message=f"wrote {EVIDENCE_LEDGER}",
                )
            )

        result = outcome.result
        if result is None:
            result = build_insufficient_data_result(
                run_id=context.run_id,
                question=context.question,
                assets=list(context.assets),
                analysis_as_of=context.analysis_as_of,
                reason=_fallback_reason(outcome.degradation_notes),
            )
        # evidence_list.json: the competition "Evidence List" deliverable — one row
        # per evidence with exactly the four required columns (source / fetched_at
        # / content_reference / related_claim, the last from this run's links).
        evidence_list = project_evidence_list(
            list(ledger.items), list(result.claim_evidence_links)
        )
        if store.write_json(
            EVIDENCE_LIST, [row.model_dump(mode="json") for row in evidence_list]
        ):
            emit(
                self._event(
                    context,
                    "artifact",
                    "artifact_write",
                    "ok",
                    output_count=len(evidence_list),
                    message=f"wrote {EVIDENCE_LIST}",
                )
            )
        report = render(result, ledger, lint=advice_violations)
        if store.write_text(FINAL_REPORT, report):
            emit(
                self._event(
                    context,
                    "artifact",
                    "artifact_write",
                    "ok",
                    message=f"wrote {FINAL_REPORT}",
                )
            )

        terminal_state = _terminal_state(outcome.terminal_state, store)
        # run_config.json cannot carry a checksum of itself: the digest would be
        # taken before this final rewrite and would never match the file on disk.
        checksums = {
            name: digest for name, digest in store.checksums().items() if name != RUN_CONFIG
        }
        # Validate the merged payload instead of using model_copy(update=...), which
        # deliberately skips Pydantic validation and could let an official run
        # claim fixture/recorded data.
        final_snapshot = RunConfigSnapshot.model_validate(
            {
                **snapshot.model_dump(mode="python"),
                "stage_durations_ms": dict(outcome.stage_durations_ms),
                "used_cached_evidence": any(item.is_cached for item in ledger.items),
                "has_stale_evidence": any(item.is_stale for item in ledger.items),
                "terminal_status": terminal_state.value,
                "effective_data_mode": (
                    outcome.effective_data_mode or snapshot.effective_data_mode
                ),
                "used_recorded_fallback": (
                    outcome.effective_data_mode is DataMode.recorded_fallback
                ),
                "artifact_checksums": checksums,
                "missing_artifacts": store.missing_artifacts(),
                "artifact_write_failures": [f.as_dict() for f in store.failures],
            }
        )
        store.write_json(RUN_CONFIG, final_snapshot.model_dump(mode="json"))
        emit(
            self._event(
                context,
                "run",
                "run_end",
                terminal_state.value,
                message=f"run finished as {terminal_state.value}",
            )
        )
        store.disclose_missing(terminal_state)

        if progress_tasks:
            if cancelled_error is None:
                await asyncio.gather(*progress_tasks)
            else:
                # Best-effort UI publishes; awaiting them inside a cancelled task
                # would raise before the re-raise below.
                for task in progress_tasks:
                    task.cancel()

        if cancelled_error is not None:
            raise cancelled_error

        return RunSummary(
            run_id=context.run_id,
            run_mode=context.run_mode,
            effective_data_mode=final_snapshot.effective_data_mode,
            terminal_state=terminal_state,
            artifact_dir=str(store.run_dir),
            artifact_paths=store.artifact_paths(),
            missing_artifacts=store.missing_artifacts(),
            evidence_item_count=len(ledger.items),
            confidence=result.confidence,
            insufficient_data=result.insufficient_data,
            degradation_notes=list(outcome.degradation_notes) + list(result.degradation_notes),
            report_markdown=report,
        )

    # -- internals ----------------------------------------------------------

    def _build_context(self, request: AnalysisRequest) -> RunContext:
        return build_run_context(request, self._clock)

    def _initial_snapshot(
        self, request: AnalysisRequest, context: RunContext
    ) -> RunConfigSnapshot:
        return RunConfigSnapshot(
            schema_version=SCHEMA_VERSION,
            prompt_version=self._prompt_version,
            policy_version=self._policy_version,
            run_id=context.run_id,
            requested_run_mode=request.run_mode,
            effective_run_mode=context.run_mode,
            # Both start equal. Only the pipeline may lower the effective mode,
            # and `official` is forbidden from ever leaving `live`.
            requested_data_mode=DataMode.requested_for(request.run_mode),
            effective_data_mode=DataMode.requested_for(context.run_mode),
            sanitized_request={
                "question": request.question,
                "assets": [asset.value for asset in request.assets],
                "requested_at": request.requested_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "requested_analysis_as_of": request.analysis_as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "deadline_seconds": request.deadline_seconds,
                # MVP records conditional debate as accepted but disabled.
                "enable_conditional_debate_requested": request.enable_conditional_debate,
                "conditional_debate_effective": False,
            },
            analysis_as_of=context.analysis_as_of,
            deadline_seconds=request.deadline_seconds,
            configured_sources=self._configured_sources,
            optional_keys_present=self._optional_keys_present,
        )

    def _event(
        self,
        context: RunContext,
        stage: str,
        event_type: str,
        status: str,
        *,
        message: str = "",
        output_count: int | None = None,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            schema_version=SCHEMA_VERSION,
            timestamp=self._clock.now_utc(),
            run_id=context.run_id,
            run_mode=context.run_mode,
            stage=stage,
            event_type=event_type,
            status=status,
            output_count=output_count,
            message=message,
        )


def _asset_mismatch_warnings(request: AnalysisRequest) -> list[str]:
    """`assets` always wins over the question text; the disagreement is logged."""
    requested = {asset.value for asset in request.assets}
    mentioned = {asset.value for asset in Asset if asset.value in request.question.upper()}
    extra = sorted(mentioned - requested)
    if not extra:
        return []
    return [
        "question text mentions "
        + ", ".join(extra)
        + " which is not in the requested assets "
        + ", ".join(sorted(requested))
        + "; requested assets take precedence"
    ]


def _fallback_reason(degradation_notes: Sequence[str]) -> str:
    return degradation_notes[0] if degradation_notes else "分析階段未產出可驗證結果"


def _cancelled_outcome(context: RunContext, now: datetime) -> PipelineOutcome:
    """A schema-valid outcome for a run cancelled before the pipeline returned.

    There is no ledger to recover, so the empty one carries the reason. A stable
    filename is not proof of a successful run, and an empty ledger with no stated
    cause would be exactly that.
    """
    message = "Run 在分析完成前被取消，未取得可交付證據。"
    return PipelineOutcome(
        ledger=EvidenceLedger(
            run_id=context.run_id,
            analysis_as_of=context.analysis_as_of,
            run_mode=context.run_mode,
            degradation_events=[
                DegradationEvent(
                    stage="run",
                    event_type="run_cancelled",
                    source="application",
                    message=message,
                    timestamp=now,
                )
            ],
        ),
        result=None,
        terminal_state=TerminalState.cancelled,
        degradation_notes=[message],
    )


def _terminal_state(pipeline_state: TerminalState, store: LocalArtifactStore) -> TerminalState:
    """Artifact delivery is part of run honesty, so missing files degrade the state."""
    missing = store.missing_artifacts()
    if not store.artifact_paths():  # nothing was written at all → total failure
        return TerminalState.failed
    if missing and pipeline_state is TerminalState.completed:
        return TerminalState.degraded
    return pipeline_state


__all__ = [
    "ApplicationService",
    "build_request",
    "make_run_id",
]
