# Workflows

## Gold local Exit workflow

Run `PYTHONPATH=src python scripts/run_acceptance.py` for two independent BTC/ETH
offline rehearsal runs. The acceptance suite checks asset allowlisting, market-data
degradation, fixed artifact parsing/checksums, Evidence provenance, deterministic
rendering, and the minute-12 deadline/finalize reserve. See
`docs/rehearsals/run-log.md` for the recorded verification.

## Primary Workflow: Complete Analysis Run

```mermaid
sequenceDiagram
    participant User as User/UI
    participant App as ApplicationService
    participant Pipe as DeadlineAwarePipeline
    participant Store as ArtifactStore
    participant Plan as Planner
    participant MW as Market Worker
    participant RA as Research Agent
    participant EP as Evidence Processor
    participant Arb as Arbiter
    participant Fin as finalize_analysis
    participant Ren as Renderer

    User->>App: run(request, progress)
    
    Note over App: Phase 1: Initialize
    App->>App: Validate request, freeze cutoff (official mode)
    App->>App: Mint run_id, build RunContext
    App->>Store: Create artifact directory
    App->>Store: write_json("run_config.json", initial_snapshot)
    App->>Store: append_event(run_start)

    Note over App,Pipe: Phase 2-5 delegated to DeadlineAwarePipeline
    App->>Pipe: execute(context, emit)

    Note over Pipe: Phase 2: Plan
    Pipe->>Plan: run(request, tool_registry, deadline)
    Plan->>Plan: Single LLM call → execution plan
    Plan-->>Pipe: (plan, notes) or default plan on failure
    Pipe->>Pipe: _apply_skip_order(plan) — trim optional work in SKIP_ORDER

    Note over Pipe: Phase 3: Parallel Evidence Gathering (fork-join)
    par Market Worker (deterministic)
        Pipe->>MW: build_market_evidence(asset, bars, as_of)
        MW->>MW: Compute indicators (return, vol, drawdown, z-score)
        MW-->>Pipe: WorkerResult with EvidenceDrafts
    and Research Agent (LLM-bounded)
        Pipe->>RA: run(plan, request, deadline)
        RA->>RA: Execute adapter calls per plan steps
        RA->>RA: Single LLM extraction call
        RA-->>Pipe: ResearchOutcome with drafts + records
    end
    Note over Pipe: On timeout: cancel unfinished branch, then await it

    Note over Pipe: Phase 4: Evidence Processing
    Pipe->>EP: complete_extracted_drafts → build_ledger(all_drafts)
    EP->>EP: Rank, dedup (SHA-256), assign IDs (ev_001, ev_002...)
    EP-->>Pipe: EvidenceLedger
    Pipe-->>App: (outcome carries ledger)
    App->>Store: write_json("evidence.json", ledger)
    App->>Store: append_event(evidence_persisted)

    Note over Pipe: Phase 5: Reasoning
    Pipe->>Arb: select_balanced_evidence ≤30 + ledger_view
    Arb->>Arb: Single LLM call → ArbiterOutput
    Arb->>Arb: project_to_analysis_result (stamp frozen context, clamp time ranges)
    Arb-->>Pipe: (result, notes) or deterministic fallback
    Pipe->>Fin: build_conflict_indicators → apply_confidence_caps → build_trust_scorecards
    Fin-->>Pipe: AnalysisResult (+ conflict_indicators on ledger)
    Pipe-->>App: PipelineOutcome

    Note over App: Phase 6: Render & Finalize
    App->>Ren: render(result, ledger, lint=advice_violations)
    Ren->>Ren: Build 11 sections (+ dual section 12) (Traditional Chinese)
    Ren->>Ren: Run prohibited-language lint (runs last)
    Ren-->>App: report_markdown
    App->>Store: write_text("final_report.md", report)
    App->>Store: write_json("run_config.json", final_snapshot + checksums)
    App->>Store: append_event(run_complete)
    App-->>User: RunSummary
```

---

## Degradation Workflow: LLM Failure

```mermaid
flowchart TD
    Start["LLM Call Attempted"]
    Start --> Response{"Response received?"}
    
    Response -->|Timeout/Unavailable| Retryable{"Retryable error?"}
    Retryable -->|Yes + fallback model configured| Switch["Switch to fallback model"]
    Switch --> Response2{"Fallback response?"}
    Response2 -->|Success| Validate
    Response2 -->|Failure| DeterministicFallback["Deterministic Fallback"]
    Retryable -->|No / No fallback configured| DeterministicFallback
    
    Response -->|Success| Validate{"Schema valid?"}
    Validate -->|Yes| Accept["Accept output"]
    Validate -->|No| Repair["Build repair messages"]
    Repair --> RepairCall["Second LLM call (same deadline)"]
    RepairCall --> Validate2{"Schema valid now?"}
    Validate2 -->|Yes| Accept
    Validate2 -->|No| DeterministicFallback
    
    DeterministicFallback --> PlanFB["Planner: default allowlisted plan"]
    DeterministicFallback --> ResFB["Research: preserve records, no drafts"]
    DeterministicFallback --> ArbFB["Arbiter: _fallback() → ArbiterOutput(insufficient_data);<br/>live cut: MappingArbiter returns None → deterministic report"]
```

---

## Degradation Workflow: Adapter Failure

```mermaid
flowchart TD
    Call["Adapter call (e.g. fetch_binance_daily)"]
    Call --> HTTP{"HTTP Success?"}
    
    HTTP -->|Yes| Parse{"Parse OK?"}
    Parse -->|Yes| Filter["Filter by analysis_as_of"]
    Filter --> Return["Return (data, [])"]
    
    Parse -->|No| Degrade["Return ([], [degradation_note])"]
    HTTP -->|No, status 5xx| Retry{"Within stage deadline?"}
    Retry -->|Yes| RetryCall["One retry with backoff"]
    RetryCall --> HTTP
    Retry -->|No| Degrade
    HTTP -->|No, 4xx/auth| Degrade
    
    Degrade --> Pipeline["Pipeline continues with partial evidence"]
    Pipeline --> EP["Evidence Processor handles whatever arrived"]
```

---

## Deadline and Fork-Join Workflow

```mermaid
flowchart TD
    Ctx["RunContext (frozen started_monotonic + deadline_monotonic)"]
    Ctx --> DM["DeadlineManager.for_run()"]
    DM --> Res["reserve = max(20%, min(60 s, half the run))"]
    Res --> Win["analysis window = min(total - reserve, 720 s)"]
    Win --> Mile["Stage milestones scaled from the 720 s reference<br/>planner 30 / gather 270 / evidence 360 / reason 510 / artifact 630"]

    Mile --> Plan["Planner: budget = min(remaining(planner), 45 s)"]
    Plan --> Fork["_fork_join(market, research, timeout=remaining(gather))"]

    Fork --> Wait{"asyncio.wait: both done<br/>before the gather milestone?"}
    Wait -->|Yes| Settle["Settle each stage from its result"]
    Wait -->|No| Cancel["task.cancel() on the unfinished branch"]
    Cancel --> Await["then gather(..., return_exceptions=True)"]
    Await --> Keep["Cancelled branch returns a CancelledError *value*;<br/>the sibling's evidence still enters the ledger"]
    Keep --> Settle

    Settle --> Term{"RunStateMachine.terminal_state()"}
    Term -->|"one branch cancelled/failed,<br/>sibling completed"| Deg["degraded"]
    Term -->|"empty ledger + market branch cancelled<br/>→ cancel_run()"| Can["cancelled"]
    Term -->|"all failed"| Fail["failed"]
    Term -->|"all clean and analysis present"| Done["completed"]
```

**Caller-initiated cancellation** takes a different route, in `application.py`:

```mermaid
flowchart TD
    Run["ApplicationService.run()"] --> Exec["await pipeline.execute()"]
    Exec -->|"CancelledError"| Cap["catch it, build a cancelled PipelineOutcome<br/>(empty ledger carrying the reason)"]
    Cap --> Fin["write evidence.json → render deterministic<br/>insufficient-data report → final_report.md →<br/>rewrite run_config.json with terminal_status=cancelled"]
    Fin --> Prog["cancel best-effort progress tasks<br/>(🚫 do not await them)"]
    Prog --> Re["re-raise the CancelledError"]
```

**Why the finalize path must be await-free:** inside an already-cancelled task, the
next `await` raises `CancelledError` again immediately, so the remaining artifact
writes would never happen. Every step between the catch and the re-raise is
synchronous, and `progress_tasks` are cancelled rather than awaited.
Finalizing is not suppressing — the error is always re-raised.

**Invariants:**
- `time.monotonic()` drives every budget; UTC timestamps are only persisted
- The acquisition window has exactly one owner (the fork-join). Branches clamp only
  their own per-call timeout, because two clamps on the same milestone make
  "which one cancelled this branch" a race
- Cancel first, then await. No pending task reaches the Evidence stage
- `asyncio.CancelledError` is never suppressed — outer cancellation tears the
  children down and re-raises
- Below `MIN_ARBITER_SECONDS` (5 s) the Arbiter is skipped so the deterministic
  finalize keeps its reserve; the run falls back deterministically and discloses it

**Now triggered in a real run:** `application.build_research_pipeline()` declares the
source lists — baseline (`fetch_rss_news`), optional context (`fetch_fear_greed`,
`fetch_official_announcements`) and counter-signal (`fetch_cryptopanic_news`) — which
is what makes the fixed skip order fire in a real run instead of only in its unit
tests. A non-allowlisted research host is rejected at registry construction, before
any request. The live cut (`composition.build_live_pipeline`) runs without a
Planner/Research branch, so the skip order does not apply there.

---

## Optional-Work Skip Order

```mermaid
flowchart TD
    Plan["ResearchPlan.planned_steps"]
    Plan --> Cls["classify each step by tool_operation"]
    Cls -->|"in counter_signal_operations"| CS["counter_signal_second_search"]
    Cls -->|"in optional_operations"| OC["optional_context"]
    Cls -->|"neither"| BL["baseline — never surrendered"]

    CS --> Pol["plan_optional_work(pending,<br/>remaining=remaining(gather),<br/>cost=per-call timeout x step count)"]
    OC --> Pol
    Pol --> Drop{"kept costs fit the window?"}
    Drop -->|No| Pop["drop the earliest still-kept item in SKIP_ORDER:<br/>H3 → optional_context → counter_signal"]
    Pop --> Drop
    Drop -->|Yes| Trim["trim skipped steps out of the plan"]

    Trim --> Any{"any step left?"}
    Any -->|Yes| Hand["hand the narrower plan to the frozen Research Agent"]
    Any -->|No| SkipBranch["do not start the research branch at all"]
    Hand --> Disc["each skip: degradation note + settled-degraded stage in the log"]
    SkipBranch --> Disc
```

**Invariants:**
- The order is owned in one place (`deadline.SKIP_ORDER`); no caller may reorder it
- Costs come from the caller (configured per-call timeout × planned calls) — the policy
  invents no estimates
- Baseline research is never surrendered. If every planned step was optional and none
  fits, the branch is not started rather than run as bookkeeping
- H3 is in the order's vocabulary but is never classified or scheduled, so it is never
  reported as skipped — that would imply the run had a debate stage to give up
- Enforcement uses the existing interface (a narrower `ResearchPlan`), so the frozen
  `reasoning/research_agent.py` is untouched

---

## Evidence Processing Workflow

```mermaid
flowchart TD
    Input["All EvidenceDrafts from Market Worker + Research Agent"]
    
    Input --> Rank["1. Rank: reliability (high→low) then freshness"]
    Rank --> Dedup["2. Dedup: SHA-256(canonicalized normalized_fact)"]
    Dedup --> Assign["3. Assign stable IDs: ev_001, ev_002, ..."]
    Assign --> Ledger["4. Build EvidenceLedger"]
    
    Ledger --> Persist["Persist evidence.json immediately"]
    Ledger --> Select["Select top ≤30 for Arbiter"]
    
    Select --> Priority["Priority: high-reliability first"]
    Priority --> Conflict["Preserve conflict-involved items"]
    Conflict --> RoundRobin["Round-robin across independence groups"]
    RoundRobin --> ArbiterPayload["Deliver to Arbiter"]
```

---

## Confidence Cap Workflow

```mermaid
flowchart TD
    Raw["Arbiter LLM assigns initial confidence"]
    
    Raw --> Check1{"insufficient_data = true?"}
    Check1 -->|Yes| Low1["Cap overall → low"]
    Check1 -->|No| Check2
    
    Check2{"Material conflict on conclusion?"}
    Check2 -->|Yes| Low2["Cap affected claim → low<br/>Cap overall → cannot be high"]
    Check2 -->|No| Check3
    
    Check3{"< 2 supporting independence groups?"}
    Check3 -->|Yes| Med["Cap claim → medium"]
    Check3 -->|No| Check4
    
    Check4{"Only low-reliability support?"}
    Check4 -->|Yes| Low3["Cap claim → low"]
    Check4 -->|No| Check5
    
    Check5{"Only stale cache as current evidence?"}
    Check5 -->|Yes| Low4["Cap current-state claim → low"]
    Check5 -->|No| Keep["Keep LLM-assigned confidence"]
    
    Low1 --> Record["Record cap rationale in degradation_notes"]
    Low2 --> Record
    Med --> Record
    Low3 --> Record
    Low4 --> Record
    Keep --> Final["Final AnalysisResult"]
    Record --> Final
```

---

## Artifact Write Workflow

```mermaid
sequenceDiagram
    participant App as ApplicationService
    participant Store as LocalArtifactStore
    participant FS as Filesystem

    Note over App,FS: Run Start
    App->>Store: write_json("run_config.json", initial)
    Store->>FS: Write .tmp-run_config.json
    Store->>FS: fsync
    Store->>FS: os.replace → run_config.json
    
    Note over App,FS: Throughout Run (streaming)
    loop Every stage event
        App->>Store: append_event(event)
        Store->>FS: Append JSONL line + flush
    end

    Note over App,FS: After Evidence Processor
    App->>Store: write_json("evidence.json", ledger)
    Store->>FS: Write .tmp-evidence.json
    Store->>FS: fsync + os.replace

    Note over App,FS: After Renderer
    App->>Store: write_text("final_report.md", report)
    Store->>FS: Write .tmp-final_report.md
    Store->>FS: fsync + os.replace

    Note over App,FS: Finalization
    App->>Store: checksums() → SHA-256 of each artifact
    App->>Store: write_json("run_config.json", final + checksums)
    Store->>FS: Atomic overwrite
```

---

## Development Workflow: Red-Green-Refactor

```mermaid
flowchart LR
    A["1. Write failing test<br/>(describes single behavior)"] --> B["2. Run test<br/>(confirm RED)"]
    B --> C["3. Implement minimal code<br/>(pass the test)"]
    C --> D["4. Run focused test<br/>(confirm GREEN)"]
    D --> E["5. Run regression suite<br/>(no breakage)"]
    E --> F["6. ruff check .<br/>(lint clean)"]
    F --> G["7. Commit<br/>(conventional subject)"]
    G --> H{"More behavior<br/>needed?"}
    H -->|Yes| A
    H -->|No| Done["Done"]
```

### Test Infrastructure

- **`tests/conftest.py`** — Handles `sys.path` bootstrap, inserting the `src/` directory so that `hoya_agent` is importable from any test without requiring an editable install. This is the root-level conftest loaded by pytest before any test module.

- **`tests/fakes.py`** — Provides shared deterministic fakes used across all test layers (unit, contract, integration, acceptance):

  | Fake | Satisfies Protocol | Purpose |
  |---|---|---|
  | `FixedClock` | `Clock` | Returns a fixed UTC `now_utc()` and monotonic value; supports `advance(seconds)` for deadline tests |
  | `FakeLLM` | `LLMClient` | Pops pre-configured `BaseModel` responses (or raises exceptions) from a queue; records all calls |
  | `FakeSourceAdapter` | `SourceAdapter` | Returns a canned result and records call parameters |
  | `FakeMarketDataAdapter` | `MarketDataAdapter` | Returns canned bars/snapshot; records `(method, params)` tuples |
  | `InMemoryProgressSink` | `ProgressSink` | Collects `ExecutionEvent` instances in a list |
  | `InMemoryArtifactStore` | `ArtifactStore` | Stores artifacts in a `dict` keyed by `(run_id, filename)` |

  Additional helpers: `InMemoryRunPersistence` (satisfies `PersistencePort`), `FakeResearchSourceAdapter` (typed variant of `FakeSourceAdapter`), `fake_tool_registry(**ops)` (builds a `StaticToolRegistry`), and `UTC_EPOCH` constant.

---

## Deployment Workflow

```mermaid
flowchart TD
    Dev["Developer machine"]
    Dev -->|"docker build"| Image["Docker Image<br/>(non-root, pinned deps)"]
    Image -->|"docker tag + push"| ECR["Amazon ECR<br/>(immutable tag)"]
    ECR -->|"docker compose pull"| EC2["EC2 Instance"]
    EC2 -->|"docker compose up"| Container["Running Container<br/>Streamlit :8501"]
    Container --> Vol["Local Volume /artifacts"]
    Container <-->|"Instance Role"| Bedrock["Amazon Bedrock"]
```

---

## Cross-Asset Comparison Workflow (Requirement 17)

```mermaid
flowchart TD
    Req["Request with assets=[A, B]"]
    Req --> ParA["Gather evidence for asset A"]
    Req --> ParB["Gather evidence for asset B"]
    
    ParA --> Metrics["Compute: returns, volatility, correlation, beta, relative strength %ile"]
    ParB --> Metrics
    
    Metrics --> Rules["Cross-asset rules enforcement"]
    Rules --> NoVolume["❌ Never compare base-asset volume"]
    Rules --> Comparable["✓ Only: returns, ratios, percentiles, quote volume"]
    Rules --> TimeMatch["✓ Same provider, same period"]
    
    Comparable --> CompDrafts["build_comparison_evidence(A, B, bars_a, bars_b)"]
    CompDrafts --> Ledger["Single EvidenceLedger for both assets"]
    Ledger --> Arbiter["Arbiter receives both assets' evidence<br/>(balanced, neither dominates 30-item cap)"]
    Arbiter --> Result["Single AnalysisResult with cross-asset claims"]
```

---

## Timeout and Skip Workflow

```mermaid
flowchart TD
    Timer["Monotonic clock running"]
    Timer --> Check{"Time remaining?"}
    
    Check -->|"> 4 min"| Normal["All stages proceed normally"]
    Check -->|"< 4 min (entering 8th minute)"| Skip1["Skip H3 (already disabled)"]
    Skip1 --> Skip2["Skip optional context adapters"]
    Skip2 --> Skip3["Skip counter-signal secondary search"]
    
    Check -->|"720s reached"| HardStop["Cancel all external/LLM calls"]
    HardStop --> Finalize["Finalize with available evidence"]
    
    Check -->|"780s reached"| ArtifactDeadline["All 4 artifacts MUST be on disk"]
    ArtifactDeadline --> Buffer["Remaining 120s = competition buffer"]
```

## 2026-08-01 workflow update

`_provisional_seams.py` is retired; `application.py`, `reporting/artifacts.py`, and
orchestration consume the canonical seams in `models.py` / `ports.py` / `clock.py`.
Analysis calls stop at 720 seconds, leaving artifact finalization budget. Market and
Research execute as an independent fork-join (cancel-then-await); failures degrade
honestly. Dual assets share one run/cutoff/ledger, aligned UTC bars, and a balanced
Arbiter projection. The Reason stage crosses an explicit `ArbiterOutput` boundary
(`project_to_analysis_result` stamps frozen context; `mapping.py` does the same for
the live `ArbiterGeneration` cut). See `s8-s9-s9b.md`.

## 2026-08-01 workflow update (S6 second pass)

Two stages of the primary workflow gained deterministic steps.

**Evidence stage — extraction completion before merge.** Research drafts now pass through
`research_extractor.complete_extracted_drafts()` first. The bounded LLM call supplies wording
only; reliability comes from the static table (a feed item whose original page was not fetched
stays `low`), `independence_group` from `policies.independence_group()`, and every timestamp
from the fetched record. One record may yield several facts, so one article becomes several
Evidence items. A fact citing a `record_id` that was never fetched is dropped with a
disclosure — previously such drafts were rejected wholesale at merge time, which is why
extracted research never reached the ledger.

**Post-Arbiter — material conflict, then caps, then scorecards.** `finalize_analysis()` runs
after the Arbiter and before the outcome is returned:

```mermaid
flowchart TD
    Result["Arbiter AnalysisResult (claims + stanced links)"]
    Result --> Detect["build_conflict_indicators(links, ledger)<br/>§9 rule, deterministic"]
    Detect -->|no conflict| Trust
    Detect -->|conflict| Attach["Attach indicators to ledger<br/>+ material_conflict_detected event"]
    Attach --> Caps["apply_confidence_caps(...)<br/>conclusion → low, overall ≠ high"]
    Caps --> Trust["build_trust_scorecards(...)<br/>consistency reads the indicators"]
    Trust --> Out["PipelineOutcome (ledger + result + notes)"]
```

Conflict detection has to run here rather than inside the Evidence Processor because stance
lives on `ClaimEvidenceLink`, so the rule is undecidable until claims exist. H3 stays disabled
and is never consulted; the conflict is preserved regardless. Both `DeadlineAwarePipeline` and
`OrganizerCsvPipeline` apply the pass, so the offline path surfaces conflicts too.

**Composition — the skip order now has its source lists.** `application.build_research_pipeline()`
declares baseline (`fetch_rss_news`), optional context (`fetch_fear_greed`,
`fetch_official_announcements`) and counter-signal (`fetch_cryptopanic_news`) operations, which
is what makes the fixed skip order fire in a real run instead of only in its unit tests.
A non-allowlisted research host is rejected at registry construction, before any request.

## 2026-08-01 workflow update (S8 third pass — Arbiter boundary)

The Reason stage gained an explicit boundary crossing:

```mermaid
flowchart TD
    Ledger["EvidenceLedger (canonical, enum-valued)"]
    Ledger --> Balanced["select_balanced_evidence(...) ≤30"]
    Balanced --> View["ledger_view(...) → string-valued EvidenceView[]"]
    View --> Arb["Arbiter.run(result_schema=ArbiterOutput)<br/>1 call + ≤1 repair"]
    Arb -->|LLMError / structural violation| FB["_fallback() → ArbiterOutput<br/>insufficient_data=true"]
    Arb --> Out["ArbiterOutput"]
    FB --> Out
    Out --> Proj["project_to_analysis_result(...)<br/>stamp frozen context, map enums,<br/>fill/clamp time ranges"]
    Proj -->|ValidationError| Degrade["stage degraded → deterministic report"]
    Proj --> Final["finalize_analysis(...) → conflicts → caps → scorecards"]
```

Why the view exists: the frozen reasoning layer reads attributes through `str(...)`, so
enum-valued items make `_reliability_rank()` return unknown. Left unfixed, `select_evidence()`
loses its high-first priority and the deterministic fallback emits a report with no claims and
no evidence links — a silent loss of exactly the traceability the fallback exists to provide.
The same reasoning applies to the output schema's `Literal` strings and
`apply_confidence_caps()`'s string comparisons.

## Run/Data-Mode Finalization

The pipeline reports its actual `effective_data_mode` at completion. Finalization
validates the complete `RunConfigSnapshot` again before rewriting
`run_config.json`. Rehearsal may remain `fixture`; demo may degrade from requested
`live` to `recorded_fallback`; official plus any non-live effective data mode is
rejected by the canonical model validator instead of being silently copied into an
artifact. Integration coverage lives in `tests/integration/test_run_modes.py`.

## Research Extraction Provenance Bridge

The baseline research adapter records the *provenance* an extracted fact needs —
`original_publisher` and `original_page_fetched` — in `RawSourceRecord.metadata`
before the LLM boundary. It does not record reliability or independence group:
those are the Evidence Processor's to assign (see the S6 fifth-pass note above), so
a producer can never state its own trustworthiness. The Research Agent returns only
extracted fact fields plus `record_id`, as the frozen prompt requires.
`research_extractor.complete_extracted_drafts()` then joins the fetched record back
by `record_id`, derives the source class (and therefore reliability) and the
independence group deterministically, and drops — with a disclosure — any fact that
cannot be joined or validated. This keeps source policy deterministic while allowing
the canonical extraction schema to enter the ledger.

## Bronze UI Workflow (Streamlit)

```mermaid
flowchart TD
    Start["Judge opens streamlit_app.py"]
    Start --> Form["Form: pick 1-2 assets, question, mode"]
    Form --> Mode{"Mode?"}
    Mode -->|即時 official| Live["_run_live: build_request(official)<br/>_live_pipeline(now)"]
    Mode -->|離線 rehearsal/demo| Off["_run_offline: build_request +<br/>OrganizerCsvPipeline(BRONZE_CUTOFF)"]

    Live --> Bedrock{"AWS_REGION +<br/>BEDROCK_PRIMARY_MODEL_ID set?"}
    Bedrock -->|Yes| BL["build_bedrock_llm + build_live_pipeline<br/>(MappingArbiter, live Binance + F&G)"]
    Bedrock -->|No / build fails| Det["Deterministic live data:<br/>Binance bars + F&G, no Arbiter"]
    BL --> Run
    Det --> Run
    Off --> Run["ApplicationService.run(progress=_StreamlitProgress)"]

    Run --> Stream["ExecutionEvents stream into st.status panel<br/>(Planner → Market → Evidence → Renderer)"]
    Stream --> Summary["RunSummary"]
    Summary --> View["presenter.summary_view() + trust_funnel(evidence.json)"]
    View --> Render["Metrics: run mode / terminal / evidence / confidence<br/>Trust funnel (G3): evidence → source types → independence groups → conflicts<br/>Tabs: Report / Evidence Ledger / Execution Log<br/>4 downloadable artifacts + degradation expander"]
```

**Invariants:**
- Business logic lives in `application.py` / `presenter.py`; `streamlit_app.py` is glue only
- `presenter.py` is framework-free (no Streamlit import) so it is unit-testable
- One submit == one `ApplicationService` call (form disabled while a run is in flight)
- H3 multi-agent debate is explicitly out of Bronze scope (caption in the UI)
- The renderer runs `advice_lint`, so rendered text is safe by construction

## Skills / CLI Analysis Workflow (src/skills + scripts/analyze.py)

A deterministic, parallel analysis surface that does NOT participate in the
`DeadlineAwarePipeline`. It is a dev/inspection entry point over the organizer
dataset and deliberately does **not** implement the run-artifact contract.

```mermaid
flowchart TD
    CLI["scripts/analyze.py BTC [--as-of ...] [--skills A1,A3] [--format md,html]"]
    CLI --> Load["skills.dataset.load_bundle(data_dir, asset, as_of, benchmark)<br/>→ MarketBundle + LoadReport"]
    Load --> Run["skills.report.run_skills(bundle, skill_ids)<br/>A1 regime · A2 position · A3 risk ·<br/>A4 participation · A5 attribution ·<br/>A7 analogs · A9 verification"]
    Run --> Assemble["build_report → AnalysisReport<br/>(each SkillResult carries findings + EvidenceRef + limitations + section_markdown)"]
    Assemble --> Lint["skills.lint.assert_no_advice<br/>(prohibited prescriptive language)"]
    Lint --> Out{"--stdout?"}
    Out -->|Yes| Print["print markdown / html"]
    Out -->|No| Write["write <stem>.md / <stem>.html<br/>(refuse overwrite unless --force)"]
```

**Invariants:**
- A skill never raises — missing data is an outcome (`UNAVAILABLE`), not an exception
- A skill never invents a number — absent fields + a limitation say so
- No skill calls a model; every number originates in `src/calc/`
- `src/skills/` and `src/calc/` do not import `hoya_agent`; the two analysis surfaces are independent
- This flow produces plain named files, not the 4 fixed run artifacts
