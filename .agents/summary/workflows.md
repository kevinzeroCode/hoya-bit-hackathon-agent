# Workflows

## Primary Workflow: Complete Analysis Run

```mermaid
sequenceDiagram
    participant User as User/UI
    participant App as ApplicationService
    participant Store as ArtifactStore
    participant Plan as Planner
    participant MW as Market Worker
    participant RA as Research Agent
    participant EP as Evidence Processor
    participant H3 as Conflict Extension
    participant Arb as Arbiter
    participant Ren as Renderer

    User->>App: run(request, progress)
    
    Note over App: Phase 1: Initialize
    App->>App: Validate request, freeze cutoff (official mode)
    App->>App: Mint run_id, build RunContext
    App->>Store: Create artifact directory
    App->>Store: write_json("run_config.json", initial_snapshot)
    App->>Store: append_event(run_start)

    Note over App: Phase 2: Plan
    App->>Plan: run(request, tool_registry, deadline)
    Plan->>Plan: Single LLM call → execution plan
    Plan-->>App: (plan, notes) or default plan on failure

    Note over App: Phase 3: Parallel Evidence Gathering
    par Market Worker (deterministic)
        App->>MW: build_market_evidence(asset, bars, as_of)
        MW->>MW: Compute indicators (return, vol, drawdown, z-score)
        MW-->>App: WorkerResult with EvidenceDrafts
    and Research Agent (LLM-bounded)
        App->>RA: run(plan, request, deadline)
        RA->>RA: Execute adapter calls per plan steps
        RA->>RA: Single LLM extraction call
        RA-->>App: ResearchOutcome with EvidenceDrafts
    end

    Note over App: Phase 4: Evidence Processing
    App->>EP: build_ledger(all_drafts)
    EP->>EP: Rank, dedup (SHA-256), assign IDs (ev_001, ev_002...)
    EP-->>App: EvidenceLedger
    App->>Store: write_json("evidence.json", ledger)
    App->>Store: append_event(evidence_persisted)

    Note over App: Phase 5: Reasoning
    App->>H3: evaluate(ledger, conflict_indicators, context)
    H3-->>App: route="arbiter" (always, H3 disabled)
    App->>Arb: run(ledger, request, conflicts, deadline)
    Arb->>Arb: Select ≤30 evidence items
    Arb->>Arb: Single LLM call → AnalysisResult
    Arb->>Arb: Structural validation (DAG, links, coverage)
    Arb->>Arb: Apply deterministic confidence caps
    Arb-->>App: (result, notes) or fallback

    Note over App: Phase 6: Render & Finalize
    App->>Ren: render(result, ledger, lint=hook)
    Ren->>Ren: Build 11 sections (Traditional Chinese)
    Ren->>Ren: Run prohibited-language lint
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
    
    DeterministicFallback --> PlanFB["Planner: default plan (all ops)"]
    DeterministicFallback --> ResFB["Research: preserve records, no drafts"]
    DeterministicFallback --> ArbFB["Arbiter: insufficient-data result from top-5 facts"]
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

Analysis calls stop at 720 seconds, leaving artifact finalization budget. Market and Research execute as an independent fork-join; failures degrade honestly. Dual assets share one run/cutoff/ledger, aligned UTC bars, and a balanced Arbiter projection. See `s8-s9-s9b.md`.
