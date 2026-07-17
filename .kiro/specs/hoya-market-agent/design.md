# HOYA Market Agent Technical Design

> Status: approved implementation design
>
> Source of truth: `docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md`
>
> MVP architecture: H2-Lite only. H3 is a disabled extension interface and is not an implementation commitment.

## 1. Design Goals

The system accepts one analysis question and one or two assets, gathers bounded market and research evidence, and produces four traceable artifacts within the competition deadline:

- `final_report.md`
- `evidence.json`
- `execution_log.jsonl`
- `run_config.json`

The implementation optimizes for a stable two-day build by four junior developers. It therefore uses one Python process, plain `asyncio`, deterministic market calculations and rendering, a small number of bounded Amazon Bedrock calls, and explicit failure degradation.

### 1.1 Locked Decisions

- Python 3.12, Pydantic v2, `httpx`, `pandas`, `pytest`.
- Plain `asyncio`; no LangGraph, Strands, Celery, message broker, or autonomous agent loop.
- Amazon Bedrock Converse API through one thin `BedrockClient` boundary.
- Streamlit calls the application service in the same process; no FastAPI service in MVP.
- One Docker image deployed from ECR to one EC2 instance with Docker Compose.
- Local artifact directory and JSONL/stdout logging; S3 and CloudWatch are stretch only.
- H2-Lite bounded specialists are the multi-agent feature shown in every run.
- H3 debate is represented only by a disabled interface whose MVP implementation always returns `no_material_conflict`.

### 1.2 Non-goals

- Price prediction, trade execution, or buy/sell recommendations.
- Free-form agent loops, dynamic tool discovery, arbitrary web browsing, or recursive planning.
- Semantic near-duplicate clustering, dynamic source reputation scoring, or unsupported probability percentages.
- On-chain, macro, S3, CloudWatch, ECS, and H3 debate implementation in the MVP.

## 2. Runtime Architecture

```text
Streamlit UI
    |
    v
ApplicationService.run(request)
    |
    v
DeadlineAwarePipeline
    |
    +--> Planner (one bounded Bedrock structured-output call)
    |
    +--> asyncio.gather(return_exceptions=True)
    |      |
    |      +--> Market Worker
    |      |      CSV + Binance -> CoinGecko fallback
    |      |      deterministic indicators -> EvidenceDraft[]
    |      |
    |      +--> Research Agent
    |             CryptoPanic + official feeds + Alternative.me
    |             one bounded Bedrock extraction call -> EvidenceDraft[]
    |
    v
Evidence Processor (schema, exact dedup, independence, reliability, conflicts)
    |
    +--> evidence.json is written immediately
    |
    v
ConflictExtension (MVP disabled stub: no debate)
    |
    v
Arbiter (one bounded Bedrock structured-output call, at most one repair)
    |
    +--> on failure: deterministic AnalysisResult fallback
    |
    v
Renderer + Artifact Builder (deterministic)
    |
    v
final_report.md + execution_log.jsonl + run_config.json
```

Only Planner, Research Agent extraction, and Arbiter use an LLM. Market Worker, Evidence Processor, conflict detection, rendering, linting, artifact writing, and deadline handling are deterministic Python.

## 3. End-to-end Sequence

1. `ApplicationService` validates `AnalysisRequest`, freezes `analysis_as_of`, creates `run_id`, snapshots sanitized configuration, and writes `run_config.json` before any network call.
2. `DeadlineManager` derives all stage deadlines from `time.monotonic()` and the request deadline. UTC wall-clock timestamps are used only in evidence and logs.
3. Planner emits a validated `ResearchPlan`. If Planner fails, the pipeline uses a deterministic plan based on `assets` and the default lookback windows.
4. Market Worker and Research Agent start concurrently. Each branch owns its adapter calls and returns `WorkerResult`; branch exceptions are data, not pipeline-fatal errors.
5. Evidence Processor normalizes all successful drafts, performs exact-hash deduplication, applies static reliability and independence policies, and emits `EvidenceLedger` plus conflict indicators.
6. Artifact Builder atomically writes `evidence.json` as soon as the ledger is valid. This step does not wait for Arbiter.
7. The disabled H3 extension receives conflict indicators and returns `no_material_conflict`; it cannot invoke Bull, Bear, or Judge in MVP.
8. Arbiter receives at most 30 ranked evidence items and emits `AnalysisResult`. One schema repair may run only inside the same stage deadline.
9. If Arbiter or its repair fails, a deterministic fallback builds a low-confidence result from validated ledger facts and lists every missing capability.
10. Renderer creates the report from `AnalysisResult` and the ledger, applies the investment-advice lint, and writes the remaining artifacts atomically.
11. The application returns `RunSummary` with artifact paths, effective data mode, stage statuses, and degradation notes for the UI.

## 4. Module Boundaries

| Module | Owns | May depend on | Must not do |
|---|---|---|---|
| `models.py` | Pydantic request, evidence, claim, result, log, and plan schemas | Pydantic and standard library | Network, filesystem, LLM, UI |
| `config.py` | Environment parsing, defaults, model IDs, time budgets, sanitized snapshots | `models.py` | Emit secrets or start work |
| `application.py` | Use-case entry point, run directory creation, pipeline invocation, `RunSummary` | orchestration, reporting, models, config | Contain adapter or UI logic |
| `orchestration/` | Pipeline order, stage state, deadlines, cancellation, degradation registration | public worker/reasoner interfaces | Parse provider payloads or calculate indicators |
| `data/` | Deterministic OHLCV loading/merging rules, indicators, Market Worker | models and adapter protocols | Call Bedrock or render reports |
| `adapters/` | All external I/O: CSV, HTTP APIs, Bedrock | models, config, `httpx`, `boto3` | Make business confidence or claim decisions |
| `evidence/` | Normalization, exact dedup, reliability, independence, ledger, conflict rules | models | Fetch sources or use an LLM |
| `reasoning/` | Planner, bounded research extraction, Arbiter, H3 interface, prompts | models, Bedrock protocol, adapter protocols | Write artifacts or bypass evidence IDs |
| `reporting/` | Deterministic Markdown rendering, output lint, atomic artifact writes | models | Call external services or invent facts |
| `streamlit_app.py` | Input form, progress display, results and downloads | `ApplicationService` only | Import adapters or pipeline internals directly |

### 4.1 Public Service Contract

```python
class ApplicationService(Protocol):
    async def run(
        self,
        request: AnalysisRequest,
        progress: ProgressSink | None = None,
    ) -> RunSummary: ...
```

Streamlit may run this coroutine in a controlled background thread/event loop, but there must be exactly one application-service invocation per submitted run. UI rerenders must not start duplicate runs.

### 4.2 Worker Contracts

```python
class MarketWorker(Protocol):
    async def execute(
        self, plan: ResearchPlan, context: RunContext
    ) -> WorkerResult: ...

class ResearchAgent(Protocol):
    async def execute(
        self, plan: ResearchPlan, context: RunContext
    ) -> WorkerResult: ...
```

`WorkerResult` always returns a status (`completed`, `partial`, `failed`), zero or more `EvidenceDraft` objects, and degradation events. An expected source failure must not escape as an uncaught exception.

### 4.3 Adapter Contracts

```python
class MarketDataAdapter(Protocol):
    async def fetch_daily_bars(...) -> SourceResult[list[MarketBar]]: ...
    async def fetch_snapshot(...) -> SourceResult[MarketSnapshot]: ...

class ResearchSourceAdapter(Protocol):
    async def fetch(...) -> SourceResult[list[RawSourceRecord]]: ...

class LLMClient(Protocol):
    async def converse_structured(
        self, *, operation: str, messages: list[dict], schema: type[BaseModel],
        max_tokens: int, deadline: float
    ) -> BaseModel: ...
```

All provider-specific field names and error payloads stop at the adapter boundary. Core modules receive only validated domain models.

## 5. Domain Contracts

The canonical field-level rules are in `.kiro/steering/evidence-contracts.md`. `models.py` contains the corresponding Pydantic v2 models.

Required core models:

- `AnalysisRequest`
- `ResearchPlan`
- `RunContext`
- `MarketBar` and `MarketSnapshot`
- `RawSourceRecord` and `EvidenceDraft`
- `EvidenceItem`, `EvidenceLedger`, and `ConflictIndicator`
- `Claim`, `ClaimEvidenceLink`, and `AnalysisResult`
- `DegradationEvent`, `ExecutionEvent`, `RunConfigSnapshot`, and `RunSummary`

Validation rules that cross objects, such as missing evidence IDs, cyclic claim dependencies, confidence caps, and material conflicts, belong in `evidence/` or the final result validator rather than in UI code.

## 6. Deadline and Cancellation Design

### 6.1 Absolute Milestones

For the normal 900-second request, deadlines are measured from a monotonic `run_started` value:

| Milestone | Absolute offset | Behavior at deadline |
|---|---:|---|
| Planner complete | 30 s | Use deterministic default plan |
| Parallel acquisition complete | 270 s | Cancel unfinished adapter/extraction tasks; keep partial results |
| Evidence Processor complete | 360 s | Validate and persist all available evidence |
| Arbiter and render complete | 510 s | Use deterministic fallback result/report if needed |
| Artifact validation target | 630 s | Enter reserve; do not add optional work |
| Analysis hard stop | 720 s | Cancel every remaining external/LLM call |
| Artifact hard stop | 780 s | Ensure all four artifact filenames exist |
| Competition deadline | 900 s | Reserved for UI/reviewer handling |

For a shorter allowed deadline, `DeadlineManager` proportionally clamps stage deadlines while reserving the last 20% (at least 60 seconds when possible) for deterministic finalization. The pipeline never extends a request deadline because of retries or schema repair.

### 6.2 Cancellation Rules

- Use `time.monotonic()` for budgets and UTC `datetime` only for persisted timestamps.
- Run parallel branches with `asyncio.gather(..., return_exceptions=True)` inside the acquisition stage deadline.
- On timeout, cancel every unfinished child task and await them with `return_exceptions=True` before continuing.
- Never swallow `asyncio.CancelledError`; adapters must release HTTP responses and re-raise cancellation.
- Per-call timeout is at most 45 seconds and is always clamped to remaining stage time.
- One retry is allowed for retryable network, throttling, and 5xx errors only when backoff plus the next timeout fit inside the same stage deadline.
- Schema repair is not extra budget. It uses the Arbiter stage's remaining time.
- Optional adapter work is skipped before required work. H3 is always skipped in MVP.
- Filesystem finalization is deterministic and must not depend on a live network or LLM call.

## 7. Run Modes

`run_mode` is immutable after validation and appears in the UI, every log event, and `run_config.json`.

| Mode | Source policy | Fallback policy | Required disclosure |
|---|---|---|---|
| `official` | Live configured APIs plus organizer CSV | Partial live results or explicitly metadata-bearing cache only; never fixtures or recorded responses | Cache source time, cache time, stale flag, failed sources |
| `rehearsal` | Deterministic fixtures and organizer CSV; network is optional and off by default | Fixture failures become test failures | Visible rehearsal badge and fixture IDs |
| `demo` | Attempt live sources first | May use a recorded response bundle when live access fails | Visible recorded-fallback banner, original capture time, degradation note |

`analysis_as_of` is frozen once at run creation. In `official` it defaults to current UTC; in `rehearsal` and `demo` it may be supplied to reproduce a fixture. A retry creates a new `run_id` but reuses the same explicit `analysis_as_of` when the caller requests reproducibility.

## 8. Data and API Adapter Design

### 8.1 Organizer CSV

- Loads `HOYA_BIT_crypto_market_dataset/data/{ASSET}_daily_ohlcv.csv`.
- Validates `date,open,high,low,close,volume`, UTC daily dates, positive prices, and high/low consistency.
- Treats volume as base-asset volume and never compares it directly across assets.
- Uses the source name `public_market_data` and independence group `organizer-public-market-data`.
- Does not infer a particular exchange as the upstream source.

### 8.2 Binance Primary Live Adapter

- Uses Spot public REST `GET /api/v3/klines` for UTC daily bars and `GET /api/v3/ticker/24hr` for the latest snapshot/quote volume.
- Maps assets to `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, and `XRPUSDT` through a fixed allowlist.
- Fetches only data at or before `analysis_as_of`.
- Keeps organizer CSV and Binance observations as distinct evidence sources; a merge records the cutover date and source difference.
- Uses quote volume for within-run comparable liquidity context. Base volume is never used for cross-asset ranking.

### 8.3 CoinGecko Fallback Adapter

- Has a fixed asset-to-coin-id allowlist.
- Supplies current USD price, change, and USD total volume when Binance snapshot retrieval fails.
- Is not treated as OHLC-equivalent. Indicators requiring open/high/low bars remain based on validated CSV/Binance bars or are marked unavailable.
- Emits a `source_fallback` degradation event and uses independence group `coingecko.com`.

### 8.4 CryptoPanic News Adapter

- Requires `CRYPTOPANIC_API_TOKEN`; missing configuration disables the adapter without failing the run.
- Filters by requested currencies and `analysis_as_of`/lookback.
- Preserves original article URL, publisher, title, published time, and fetched time.
- Sets `independence_group` from the original publisher domain, not `cryptopanic.com`, when the upstream publisher is available.
- Keeps the aggregator record at low reliability unless the original publisher page is actually fetched and cited.
- The Research Agent may extract facts only from the returned record fields/content reference; it cannot fabricate article text.

### 8.5 Official Source Adapter

- Uses a checked-in configuration allowlist of official project blog/RSS endpoints by asset.
- Runs best-effort and reports `source_unavailable` when an asset has no working official endpoint.
- Official source evidence is high reliability only when the URL belongs to the configured official domain and the publication timestamp is present.

### 8.6 Alternative.me Context Adapter

- Uses the `/fng/` endpoint without a key.
- Produces market-wide context with `asset=null`; reports must state that it is not a coin-specific signal.
- Uses source type `social`, reliability `low`, and independence group `alternative.me`. Stale data is marked but is not demoted below `low`.

### 8.7 Adapter Result Envelope

Every adapter returns a `SourceResult` containing provider name, request parameters with secrets removed, fetched time, status, data, cache metadata, latency, and a normalized error category. Raw secrets and authorization headers must never enter logs, evidence, or artifacts.

## 9. Evidence Processing and Arbiter Input

Evidence Processor performs this deterministic sequence:

1. Validate drafts and reject any fact without a resolvable source reference.
2. Normalize URLs, timestamps, whitespace, asset names, and source type.
3. Calculate `content_hash`; exact duplicates collapse to one item while retaining provenance aliases.
4. Derive `independence_group` using the policy in `evidence-contracts.md`.
5. Assign static reliability and record cache/staleness; apply the confidence caps in `evidence-contracts.md` without dynamically rewriting source reliability.
6. Allocate stable run-local IDs (`ev_001`, `ev_002`, ...).
7. Detect material conflicts at claim-link validation time.
8. Rank evidence by reliability, directness, freshness, and source diversity.

Arbiter receives no more than 30 evidence items. The selection first preserves all high-reliability evidence, then material-conflict pairs, then fills remaining slots while maximizing distinct independence groups. The prompt receives IDs and normalized facts, not unbounded raw pages.

Arbiter output is accepted only if it validates as `AnalysisResult`, all evidence and claim references resolve, claim dependencies are acyclic, and confidence obeys the caps. One structured repair call may receive validation errors and the previous JSON. If it still fails, deterministic fallback runs.

## 10. H3 Extension Interface

```python
class ConflictExtension(Protocol):
    async def evaluate(
        self,
        ledger: EvidenceLedger,
        indicators: list[ConflictIndicator],
        context: RunContext,
    ) -> ConflictExtensionResult: ...
```

The only MVP implementation is `DisabledConflictExtension`:

- It performs no network or LLM call.
- It returns `status="disabled"`, `route="arbiter"`, and the deterministic indicators unchanged.
- In every MVP run mode, `enable_conditional_debate=true` is logged as disabled/ignored and routes directly to Arbiter.
- No Bull/Bear/Judge prompts, tasks, or tests are required for MVP acceptance.

## 11. Failure Degradation

| Failure | Pipeline response | User-visible result |
|---|---|---|
| Planner timeout/schema error | Deterministic asset/lookback plan | Warning in log and report |
| One evidence branch fails | Continue with other branch | Missing source and confidence impact disclosed |
| Adapter timeout/429/5xx | At most one bounded retry; then partial result | Adapter name, error category, and fallback recorded |
| Binance fails | Use CoinGecko snapshot if available; retain CSV history | Source-switch note; unsupported OHLC metrics omitted |
| CryptoPanic token absent | Disable news adapter | News gap in limitations |
| Fewer than three independent groups | Continue, cap confidence | `insufficient_data` when central conclusion cannot be supported |
| Conflicting medium/high evidence | Preserve both links and conflict indicator | Low confidence for affected claim and explicit conflict section |
| Research extraction fails | Keep deterministic market evidence and raw-source gap | No LLM-created research facts |
| Arbiter fails after one repair | Build deterministic fallback result from ledger facts | Low confidence, fallback banner, all four artifacts |
| Renderer lint fails | Replace prohibited recommendation phrasing with neutral template or fallback report | Lint event in execution log |
| Artifact write fails | Retry local atomic replace once; continue writing other filenames | Run marked failed/partial with exact missing path |
| Analysis hard stop | Cancel external tasks and finalize synchronously | Partial report and degradation notes |

No failure path may silently substitute fixture data in `official` mode.

## 12. Artifact and Logging Design

Each run writes to `artifacts/{run_id}/`. Writes use a temporary file in the same directory, flush, then `os.replace` to avoid exposing half-written JSON or Markdown.

### 12.1 Incremental Persistence

- At run start: create directory, open append-only `execution_log.jsonl`, write sanitized `run_config.json`.
- After each stage/tool call: append and flush an `ExecutionEvent`.
- After Evidence Processor: write complete `evidence.json` immediately.
- After Arbiter or fallback: render and write `final_report.md`.
- At finalization: update sanitized `run_config.json` with effective mode, terminal state, stage durations, prompt/schema versions, and artifact checksums.

If no evidence is available, `evidence.json` is a valid empty ledger with degradation events. If no analysis is available, `final_report.md` is a deterministic insufficient-data report. This guarantees stable artifact filenames without pretending success.

### 12.2 Execution Log Granularity

Log run/stage/tool lifecycle events, not chain-of-thought or full prompts. Record:

- event timestamp, run ID, mode, stage, event type, status, duration;
- adapter/model identifier, sanitized parameters, retry count, item counts;
- timeout/cancellation/error category and public-safe message;
- input/output schema version and prompt version;
- artifact write/checksum events.

Never log API tokens, AWS credentials, authorization headers, full prompt text, or hidden model reasoning.

## 13. Streamlit Experience

The first screen is the working analysis interface, not a landing page. It contains:

- question input;
- one- or two-asset selector restricted to the five supported assets;
- visible run-mode selector;
- run button disabled while a run is active;
- stable progress rows for Planner, Market Worker, Research Agent, Evidence Processor, Arbiter, and Renderer;
- result tabs for Report, Evidence, and Execution Log;
- download buttons for all four artifacts;
- persistent badges for partial, fallback, cached, stale, rehearsal, and recorded-demo states.

The UI displays status emitted through `ProgressSink`; it must not infer success from elapsed time or inspect internal task objects.

## 14. Configuration

Environment-backed settings are loaded once through `Settings` in `config.py`. Required production keys:

- `AWS_REGION`
- `BEDROCK_PRIMARY_MODEL_ID`
- `ARTIFACT_ROOT`

Optional keys:

- `BEDROCK_FALLBACK_MODEL_ID`
- `CRYPTOPANIC_API_TOKEN`
- `HTTP_CONNECT_TIMEOUT_SECONDS`
- `HTTP_READ_TIMEOUT_SECONDS`
- `MAX_EVIDENCE_FOR_ARBITER` (hard maximum 30)
- `ALLOW_RECORDED_DEMO_FALLBACK`
- `LOG_LEVEL`

`.env` is local-only. `run_config.json` contains key presence booleans and non-secret values, never secret contents. Model fallback is used only for retryable availability/throttling failures and remains within the same stage deadline.

## 15. Deployment

```text
Browser -> EC2 security group port -> Docker Compose
                                      |
                                      +-- hoya-agent container
                                          Streamlit + Python application
                                          IAM instance role -> Bedrock
                                          local volume -> /app/artifacts
```

- Build one image with a pinned Python dependency lock.
- Push the immutable image tag to ECR.
- EC2 pulls that tag and runs a single Compose service with a persistent artifact volume.
- Use an EC2 IAM role for Bedrock; do not bake AWS keys into the image or Compose file.
- Bind Streamlit to `0.0.0.0`; restrict the security group to the demo access requirement.
- Container health check verifies the Streamlit health endpoint.
- Logs go to stdout and the per-run JSONL file. S3 and CloudWatch remain optional.

## 16. Test Strategy

### 16.1 Unit Tests

- Pydantic schema validation and serialization.
- UTC date parsing, CSV validation, source cutover, and asset allowlists.
- Indicator golden fixtures: returns, moving averages, volatility, drawdown, range, volume z-score.
- Exact hash deduplication, independence groups, static reliability, and stale confidence caps/disclosures.
- Claim DAG, evidence-link integrity, material conflict, confidence caps.
- Deadline clamping, retry eligibility, cancellation propagation.
- Deterministic report rendering and prohibited-language lint.

### 16.2 Contract Tests

- Mock `httpx` responses for Binance, CoinGecko, CryptoPanic, official feeds, and Alternative.me.
- Verify timeout, 429, malformed JSON, missing fields, stale data, and provider error mapping.
- Stub Bedrock Converse responses for valid structured output, invalid schema, throttling, repair success, and repair failure.
- Assert sanitized adapter/log snapshots contain no configured secrets.

### 16.3 Integration Tests

- Rehearsal fixture end-to-end run produces all four filenames with one shared run ID.
- Market branch failure still yields research evidence and a report.
- Research branch failure still yields deterministic market evidence and a report.
- Arbiter failure produces a deterministic fallback report and valid artifacts.
- Artificially short deadline cancels pending tasks and finalizes artifacts.
- `official` mode refuses fixture/recorded fallback; `demo` visibly records it.
- H3 flag does not create Bull/Bear/Judge calls and always routes to Arbiter.

### 16.4 Smoke Tests

- Docker image starts and passes its health check.
- Streamlit can submit a rehearsal run and download each artifact.
- A manual live-source rehearsal validates source cutover and current API shapes before competition day; it is not part of deterministic CI.

## 17. Repository Structure

```text
.
|-- .kiro/
|   |-- specs/hoya-market-agent/
|   |   |-- requirements.md
|   |   |-- design.md
|   |   `-- tasks.md
|   `-- steering/
|       |-- tech.md
|       |-- structure.md
|       `-- evidence-contracts.md
|-- src/hoya_agent/
|   |-- __init__.py
|   |-- models.py
|   |-- config.py
|   |-- clock.py
|   |-- ports.py
|   |-- application.py
|   |-- orchestration/
|   |   |-- deadline.py
|   |   |-- run_state.py
|   |   `-- pipeline.py
|   |-- data/
|   |   |-- market_series.py
|   |   |-- indicators.py
|   |   `-- market_worker.py
|   |-- adapters/
|   |   |-- organizer_csv.py
|   |   |-- binance.py
|   |   |-- coingecko.py
|   |   |-- cryptopanic.py
|   |   |-- rss.py
|   |   |-- official.py
|   |   |-- alternative_me.py
|   |   `-- bedrock.py
|   |-- evidence/
|   |   |-- processor.py
|   |   |-- ledger.py
|   |   `-- policies.py
|   |-- reasoning/
|   |   |-- planner.py
|   |   |-- research_agent.py
|   |   |-- arbiter.py
|   |   `-- conflict_extension.py
|   |-- reporting/
|   |   |-- renderer.py
|   |   |-- artifacts.py
|   |   `-- lint.py
|   `-- ui/
|       `-- presenter.py
|-- prompts/
|   |-- planner-v1.md
|   |-- research-extraction-v1.md
|   `-- arbiter-v1.md
|-- tests/
|   |-- unit/
|   |-- contract/
|   |-- integration/
|   |-- acceptance/
|   |-- live/
|   `-- fixtures/
|-- streamlit_app.py
|-- Dockerfile
|-- compose.yaml
|-- pyproject.toml
`-- .env.example
```

Import and ownership rules for this tree are defined in `.kiro/steering/structure.md`.
## 18. Implementation Gates

Work proceeds in this order:

1. Schemas, fixture adapters, execution log, and artifact filenames.
2. One rehearsal vertical slice from request to all four artifacts.
3. Deterministic market indicators and Evidence Processor policies.
4. Bounded Bedrock Planner/Arbiter with fallback.
5. Live adapters and Research Agent extraction.
6. Streamlit UI and Docker deployment.
7. Failure drills, live-source rehearsal, and presentation polish.

H3, S3, CloudWatch, ECS, on-chain, and macro adapters remain out of scope unless every H2-Lite acceptance test passes by Day 2 morning.
