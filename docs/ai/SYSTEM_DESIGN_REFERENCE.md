# HOYA Market Agent System Design Reference

> **Document status:** Non-binding architecture reference and Production evolution reference.
>
> This document is not an implementation contract and is **not part of Hackathon MVP acceptance**.
>
> Approved Kiro Requirements, Design, Tasks, and always-included Steering take precedence over this reference.
>
> No statement in this document asserts that runtime features, tests, Bedrock access, AWS resources, or deployment have been implemented or verified.

## 1. Purpose and Scope

HOYA Market Agent is conceptually a long-running AI research agent that performs bounded multi-source retrieval, evidence-oriented reasoning, and traceable report generation.

Its purpose is to:

- accept an analysis question and supported market identifiers;
- retrieve market and research material from controlled sources;
- normalize evidence into a common, auditable representation;
- separate facts, inferences, and conclusions;
- show supporting, counter, and conflicting evidence;
- state uncertainty and missing information;
- produce a report whose claims can be traced to source evidence;
- preserve an execution record suitable for review and reproduction.

This architecture is for research-oriented analysis. It explicitly excludes:

- trading or trade execution;
- wallets, custody, or key management;
- order matching or exchange operations;
- portfolio management or personalized allocation;
- guaranteed prices, returns, forecasts, or outcomes.

The two-day Hackathon implementation is a bounded, same-process subset of this broader system. Production concepts describe possible evolution only.

## 2. Implement in Hackathon MVP

The following concepts fit the approved two-day H2-Lite boundary and may be implemented without production-scale infrastructure:

- **Internal run state:** explicit in-memory lifecycle and truthful terminal status.
- **Stage deadlines:** monotonic, stage-owned budgets within the competition ceiling.
- **Tool-call budget:** a bounded plan and per-stage call limit, not a distributed quota service.
- **Progress events:** typed in-process events for Streamlit and the Execution Log.
- **Partial completion:** retain successful branch output when another branch fails.
- **Evidence traceability:** every material fact retains source, time, parameters, and evidence ID.
- **Claim-Evidence links:** `supports|opposes|neutral` belongs on links, not Evidence Items.
- **Execution Log:** append-only, sanitized lifecycle and degradation events.
- **Tool allowlist:** only approved operations and adapters may execute.
- **Domain allowlist:** assets, providers, official domains, and URL hosts are constrained.
- **External content isolation:** retrieved text is untrusted data, never executable instruction.
- **Structured Bedrock output:** bounded, schema-validated results through a thin client boundary.
- **Deterministic reliability:** source policy assigns only `high`, `medium`, or `low`.
- **Deterministic conflict detection:** transparent rules preserve material support and opposition.
- **Deterministic fallback:** validated evidence renders an insufficient-data or degraded report without another LLM call.
- **Four fixed artifacts:** local, incremental, reviewable outputs for every run when the artifact volume is writable.

The four required artifact filenames remain exactly:

- `final_report.md`
- `evidence.json`
- `execution_log.jsonl`
- `run_config.json`

Reliability remains a categorical enum:

- `high`
- `medium`
- `low`

Reliability must not be replaced by a numeric score. Corroboration affects claim confidence under deterministic rules; it does not dynamically rewrite source reliability.

The Hackathon runtime remains:

```text
Streamlit
  -> same-process ApplicationService
  -> bounded asyncio stages
  -> Evidence Processor and Claim verification
  -> structured Bedrock analysis or deterministic fallback
  -> deterministic Markdown renderer
  -> local four-artifact directory
```

No Queue, Database, DLQ, WebSocket transport, or independent Worker Fleet is required by this MVP runtime.

## 3. Model Now, Implement Later

The MVP may keep thin interfaces that prevent core logic from depending directly on local implementation details:

- `run_id` as the shared identity for one request, its events, and its artifacts;
- `ProgressSink` for typed progress and degradation events;
- source adapter protocols returning validated success, partial, empty, or failure results;
- an artifact store protocol with one local-filesystem implementation;
- a cancellation-compatible state enum for deadline and future cancellation outcomes;
- a future persistence boundary around run summaries and artifacts;
- a tool registry abstraction backed only by a static allowlist in the MVP.

These seams provide future compatibility without requiring current infrastructure. They must not require:

- a Database;
- a Queue;
- an independent API or worker service;
- a Message broker.

If an existing application-service, adapter, progress, or artifact interface already provides the seam, document and reuse it rather than adding another abstraction.

## 4. Future Production Architecture

**Future Architecture — not required or implemented in the two-day MVP.**

A production evolution may introduce the following only after requirements, operating scale, security, and reliability targets justify them:

- API Gateway;
- authentication and authorization;
- Analysis Job Service;
- Job metadata database;
- Queue or durable workflow;
- independent worker fleet;
- persistent raw snapshot storage;
- persistent evidence store;
- persistent artifact storage;
- policy-driven retry with backoff;
- circuit breaker;
- Dead Letter Queue;
- polling APIs;
- Server-Sent Events;
- WebSocket delivery;
- horizontal scaling and autoscaling;
- per-user quota;
- scheduler;
- notifications;
- production observability dashboards.

These components must appear in diagrams and presentations under a visibly separate Future Architecture or Production Evolution boundary. They are not current Requirements, Tasks, acceptance criteria, or implementation claims.

A possible production flow is conceptual only:

```text
Client -> API Gateway/Auth -> Analysis Job Service -> durable work boundary
       -> worker fleet -> persistent snapshots/evidence/artifacts
       -> polling/SSE/WebSocket -> client
```

The conceptual flow does not authorize adding FastAPI, a broker, a database, a worker service, or another orchestration framework to the Hackathon build.

## 5. Functional Design Reference

The broader functional design includes these bounded capabilities:

1. **Create analysis request:** validate question, supported identifiers, run mode, and immutable analysis cutoff.
2. **Plan bounded data collection:** choose only allowlisted tools, sources, time ranges, and call budgets.
3. **Collect market evidence:** use reproducible calculations and preserve source parameters and timestamps.
4. **Collect research evidence:** retrieve bounded records from approved research and official domains.
5. **Normalize evidence:** convert identifiers, timestamps, assets, URLs, and facts into validated models.
6. **Deduplicate evidence:** collapse exact content hashes while preserving safe provenance aliases.
7. **Detect conflicts:** identify material support and opposition through deterministic rules.
8. **Link claims:** connect facts, inferences, and conclusions to supporting and counter evidence.
9. **Generate confidence and uncertainty:** apply categorical confidence rules, limitations, and invalidation conditions.
10. **Produce partial results:** retain available evidence and disclose failed or missing capabilities.
11. **Generate traceable outputs:** render a deterministic report and append a sanitized execution log.

The Hackathon MVP does not require:

- a cancellation UI;
- re-run history or re-run management;
- notifications;
- PDF export;
- HTML export;
- multi-user job management;
- WebSocket progress;
- a full asynchronous job API.

Those functions remain future product decisions and must not be inferred from the existence of thin interfaces.

## 6. Non-functional Design Reference

The Hackathon-relevant qualities are:

- **Competition deadline:** total execution remains under the confirmed competition ceiling.
- **Per-stage deadlines:** planning, collection, evidence, reasoning, and rendering cannot consume unbounded time.
- **Graceful degradation:** one source, branch, or Bedrock failure does not erase completed work.
- **Freshness metadata:** source time, fetch time, cache time, and stale state remain visible.
- **Snapshot consistency:** evidence is evaluated against one immutable `analysis_as_of` cutoff.
- **Traceability:** claims and report statements resolve to validated evidence or state insufficient data.
- **Secret handling:** credentials, tokens, authorization headers, full prompts, and hidden reasoning are excluded from artifacts and logs.
- **Prompt-injection resistance:** retrieved content cannot select tools, override policy, or become system instruction.
- **Cost and tool budgets:** Bedrock output, evidence count, tool calls, retries, and optional work remain bounded.
- **Maintainability:** adapters expose typed protocols so provider changes do not alter core reasoning contracts.

The following are Production-only qualities and mechanisms:

- horizontal scalability;
- Queue backlog management;
- multi-worker concurrency;
- per-user quota enforcement;
- persistent checkpoint recovery;
- a full metrics, tracing, alerting, and dashboard platform.

Production targets require separate capacity, availability, recovery, privacy, and security requirements. They cannot be treated as implicitly satisfied by the single-instance Hackathon design.

## 7. Hackathon vs Production Mapping

| Concern | Hackathon implementation | Production evolution |
|---|---|---|
| Runtime | Streamlit and same-process `ApplicationService` | API-facing job service plus independently deployable workers |
| Job state | In-memory run state and `run_id` in artifacts | Persistent job metadata and state-transition records |
| Parallelism | Bounded `asyncio` fork/join inside one process | Durable work distribution across a controlled worker fleet |
| Persistence | Local run directory and immutable input/config snapshots | Persistent raw snapshots, evidence, metadata, and artifact stores |
| Retry | At most one stage-bound retry where approved; otherwise deterministic fallback | Policy-driven backoff, circuit breaker, and Dead Letter Queue |
| Progress | In-process `ProgressSink`, Streamlit state, and JSONL events | Polling, Server-Sent Events, or WebSocket subscriptions |
| Artifact storage | Local artifact directory with four fixed filenames | Durable object storage, retention policy, and controlled download access |
| Scaling | One active run per instance; no horizontal scaling requirement | Horizontal scaling, autoscaling, scheduling, and capacity controls |
| Failure handling | Partial completion, typed gaps, local rollback, deterministic fallback | Durable checkpoints, replay policy, DLQ handling, and operator workflows |
| Observability | `execution_log.jsonl`, `run_config.json`, and container stdout | Central logs, metrics, traces, dashboards, alerts, and SLO reporting |
| Security | Domain/tool allowlists, input isolation, secret redaction, EC2 role | Authentication, authorization, per-user quotas, audit controls, and policy enforcement |

The Hackathon column is the only implementation-oriented portion of this reference, and it remains subordinate to approved Kiro documents. The Production column is non-binding evolution guidance only.

Source condensed for this reference: `docs/system-design.md`. The source remains in place and is not replaced by this document.
