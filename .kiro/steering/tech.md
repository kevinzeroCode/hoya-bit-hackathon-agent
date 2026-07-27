---
inclusion: always
---

# Technology Steering

These rules apply to every implementation task in the HOYA Market Agent repository. The approved product spec and `.kiro/specs/hoya-market-agent/design.md` take precedence over convenience-driven framework changes.

## 1. Locked Stack

| Area | Required choice | Notes |
|---|---|---|
| Language | Python 3.12 | Use type hints on all public functions |
| Validation | Pydantic v2 | All cross-module payloads are validated models |
| Async I/O | standard-library `asyncio` | Explicit fork/join and deadlines only |
| HTTP | `httpx.AsyncClient` | One shared client per run/application lifecycle |
| Tabular calculations | `pandas` | Deterministic market indicators only |
| AWS SDK | `boto3` | Bedrock Runtime Converse API |
| LLM | Amazon Bedrock | Primary and optional fallback model IDs from config |
| UI | Streamlit | Same process as application service |
| Tests | `pytest`, `pytest-asyncio` | Mock provider contracts; rehearsal fixtures for E2E |
| Packaging | `pyproject.toml`, `src/` layout | Pin a reproducible dependency lock before deployment |
| Runtime | Docker, ECR, EC2, Docker Compose | One image and one service in MVP |
| Logs/artifacts | stdout, JSONL, local volume | S3/CloudWatch are stretch only |

Do not introduce LangGraph, AWS Strands Agents, FastAPI, Celery, Redis, a message broker, a vector database, or another orchestration framework without changing the approved design first.

## 2. Python Conventions

- Use UTF-8 source files, four-space indentation, and explicit imports.
- Use `snake_case` for functions/modules/fields, `PascalCase` for classes and Pydantic models, and uppercase names for constants.
- Prefer small pure functions for normalization, policy, indicator, ranking, and rendering logic.
- Public functions and methods require parameter and return annotations.
- Use `pathlib.Path`, timezone-aware UTC `datetime`, `Decimal` only where exchange precision requires it, and floats for analytical indicators with documented rounding at presentation time.
- Never use naive datetimes. Parse external timestamps at adapter boundaries and normalize to UTC.
- Do not represent structured domain data as untyped dictionaries after leaving an adapter.
- Do not catch `Exception` without immediately converting it to a typed degradation/error result or re-raising it at the orchestration boundary.
- Never catch and suppress `asyncio.CancelledError`.
- Keep comments focused on non-obvious policy or deadline reasoning. Do not narrate straightforward assignments.

## 3. Pydantic and Schema Rules

- `src/hoya_agent/models.py` is the canonical Python representation of all shared contracts.
- Use `ConfigDict(extra="forbid")` for persisted and LLM-output models so silent provider/model fields cannot leak through.
- Use enums or `Literal` values for assets, run modes, source types, reliability, stance, claim type, and statuses.
- Validate asset allowlists, UTC timestamps, non-empty IDs/text, time-range order, and numeric finiteness.
- Keep schema field names identical across Python, JSON artifacts, prompts, fixtures, and tests.
- Version persisted schemas and prompt templates in `run_config.json`.
- LLM structured output must validate as the target model before entering core logic. At most one repair call is allowed and it shares the original stage deadline.
- Object-graph validation (claim references, evidence links, DAG, confidence caps) belongs in deterministic validators, not in prompt instructions alone.

See `evidence-contracts.md` for the canonical evidence, claim, result, and artifact invariants.

## 4. Async and Deadline Rules

- Use `time.monotonic()` for deadlines and durations; use UTC wall-clock time only for persisted timestamps.
- The orchestrator owns absolute stage deadlines. Adapters receive a deadline or remaining timeout and may not extend it.
- Run Market Worker and Research Agent with `asyncio.gather(..., return_exceptions=True)` under the acquisition deadline.
- On timeout, cancel and await unfinished tasks before advancing to the Evidence Processor.
- Clamp every HTTP/Bedrock timeout to the remaining stage time. Default provider-call timeout must not exceed 45 seconds.
- Allow at most one retry for throttling, transient connection errors, or 5xx responses. Retry only if backoff and the next call fit within the current stage.
- Use bounded exponential backoff with jitter. Never retry schema validation, authentication, unsupported assets, or deterministic input errors as network faults.
- Treat branch failure as a `WorkerResult(status="partial"|"failed")`, not a pipeline crash.
- After the 12-minute analysis hard stop, no external or LLM call may start or continue.
- Artifact finalization must remain deterministic and network-free.

## 5. HTTP Adapter Rules

- All HTTP calls live under `src/hoya_agent/adapters/`; no direct `httpx` call is allowed in data, evidence, reasoning, reporting, UI, or orchestration modules.
- Reuse an `httpx.AsyncClient` with explicit connect/read/write/pool timeouts and a stable user agent.
- Restrict hosts and asset/provider mappings to configured allowlists. Do not let an LLM create arbitrary URLs.
- Parse provider payloads into provider-local DTOs, then map them to domain models.
- Return a typed `SourceResult` with status, safe parameters, latency, cache metadata, data, and normalized error category.
- Remove query tokens, authorization headers, AWS credentials, and secret-bearing fields before logging or persisting parameters.
- Honor `analysis_as_of`; discard future records and disclose records without a trustworthy publication time.
- Preserve the original source URL/publisher when an aggregator provides it.
- Contract-test success, timeout, 429, 5xx, malformed JSON, missing fields, and stale responses for each adapter.

## 6. Market Data Rules

- The organizer CSV is a common benchmark source named `public_market_data`; never claim it came from Binance or another specific exchange.
- CSV dates and Binance daily klines use UTC boundaries.
- Record the explicit cutover when extending CSV history with Binance live data. Do not silently overwrite overlapping observations.
- Binance is the primary live market source. CoinGecko is post-hackathon Future Work, not an MVP fallback; a baseline market-source failure yields honest partial/degraded output and never claims a second live provider was used.
- Base-asset `volume` from organizer CSV is not comparable across BTC, ETH, SOL, BNB, and XRP.
- For cross-asset liquidity comparison, use quote/USD volume from the same provider and comparable period, or declare the comparison unavailable.
- Indicator calculations are deterministic, parameterized, and covered by golden fixtures.
- Do not forward-fill unavailable price/volume values across source gaps merely to make an indicator computable.
- Round only for report presentation. Persist enough precision to reproduce calculations.

## 7. Bedrock Rules

- All Bedrock Runtime calls pass through `src/hoya_agent/adapters/bedrock.py` and its `LLMClient` protocol.
- Obtain region and model IDs from `Settings`; never hard-code a model ARN or credentials.
- Use the Converse API with a constrained structured-output/tool schema that maps to a Pydantic model.
- Planner receives only the request and supported capabilities.
- Research extraction receives bounded source records and must cite their record IDs; it cannot browse or invent URLs.
- Arbiter receives the validated, ranked ledger capped at 30 evidence items and must cite evidence IDs.
- Set operation-specific `max_tokens`; do not build a token accounting subsystem.
- Log model ID, operation, latency, attempt, token usage when returned, prompt version, and schema version. Never log full prompt text, secrets, chain-of-thought, or hidden reasoning.
- The optional fallback model is used only for retryable model availability/throttling failures and within the same stage deadline.
- Any unvalidated output is discarded. After one failed repair, use deterministic fallback behavior.

## 8. Evidence-only Generation

- LLM output is never an evidence source.
- Every generated factual statement must map to a validated `EvidenceItem` or be omitted.
- An Evidence Item contains a source reference, fetch time, content reference, normalized fact, reliability, independence group, and content hash.
- Exact SHA-256 deduplication is allowed; semantic similarity clustering is out of scope.
- Reliability is assigned by deterministic static policy, not by an LLM.
- Material conflict detection is deterministic, claim-level, and follows `evidence-contracts.md`.
- Confidence is `high`, `medium`, or `low`; never emit unsupported numeric probabilities.
- Missing or conflicting evidence lowers confidence and appears in limitations/degradation notes.

## 9. Rendering and Artifact Rules

- `final_report.md` is rendered deterministically from `AnalysisResult` plus the Evidence Ledger.
- Never ask an LLM to rewrite the final report after validation.
- The renderer includes the direct answer, market context/time range, facts, inferences, conclusions, opposing signals/conflicts, confidence rationale, limitations, invalidation conditions, watch items, and source references.
- Run a deterministic lint for prohibited prescriptive investment language such as direct instructions to buy, sell, add, reduce, or leverage a position.
- Artifact names are fixed: `final_report.md`, `evidence.json`, `execution_log.jsonl`, `run_config.json`.
- Write artifacts atomically using a temporary file in the same directory followed by `os.replace`.
- Open the execution log at run start and append/flush events during execution.
- Persist evidence as soon as the Evidence Processor completes so Arbiter failure cannot remove traceability.
- Empty/partial artifacts must be schema-valid and explicitly state the degradation; stable filenames are not proof of a successful run.

## 10. Run-mode Honesty

- `official`: live sources and organizer CSV only. Cached evidence requires source time, cache time, and stale state. Never load fixtures or recorded responses.
- `rehearsal`: deterministic fixtures are expected and are visibly labeled.
- `demo`: may attempt live calls and use a recorded bundle only after failure; the UI/report/config must label the fallback and capture time.
- Run mode is immutable after the run starts and appears in all logs/artifacts.
- A demo/rehearsal result must never be relabeled as official.

## 11. Configuration and Secrets

- Parse environment values once in `config.py`; pass a typed `Settings` object into factories.
- `.env` is local-only and excluded from Git. Provide `.env.example` with placeholder names only.
- Use an EC2 instance role for Bedrock permissions. Do not store long-lived AWS access keys in source, image layers, Compose, artifacts, or screenshots.
- `run_config.json` stores whether optional credentials were configured, not their values.
- Sanitize errors because provider SDK exceptions can echo request details.
- Before any commit or submission, scan tracked files for secrets and generated artifact data.

## 12. Deployment Rules

- Build a single non-root Docker image with Python dependencies installed from the pinned lock.
- Keep Streamlit, application service, and pipeline in the same container/process for MVP.
- Expose only the Streamlit port required for the demo.
- Mount a persistent local artifact directory; do not write run output into the image filesystem layer.
- Push immutable image tags to ECR and deploy the exact tested tag through Docker Compose on EC2.
- Use a container health check and restart policy. Do not add orchestration infrastructure during the two-day build.

## 13. Test Quality Bar

- New deterministic behavior requires unit tests.
- Every external adapter requires mocked contract tests.
- Every failure/degradation rule requires at least one integration test using fixtures or fakes.
- The rehearsal end-to-end test must produce and validate all four artifacts.
- Market formulas require golden expected values, including boundary/NaN behavior.
- Tests must not call live APIs or Bedrock by default.
- A separate manual live-source rehearsal is run before the competition to detect provider schema changes.
- Verification before merge includes tests, artifact schema validation, and a secret scan; a passing UI screenshot alone is insufficient.

## 14. Forbidden Shortcuts

- Do not pass raw provider dictionaries deep into the application.
- Do not put business logic in Streamlit callbacks.
- Do not let prompts decide timeouts, source reliability, independence, conflict materiality, or artifact filenames.
- Do not hide adapter failures, cached data, fixture data, or recorded demo fallback.
- Do not compare base volumes across assets.
- Do not add H3 Bull/Bear/Judge implementation before all H2-Lite acceptance tests pass.
- Do not commit competition PDF/ZIP files, `.env`, credentials, logs, or generated run artifacts.
