# HOYA Market Agent Staged Delivery Proposal

> Status: delivery proposal only; not an implementation-status report
>
> Scope: four junior developers, two full working days, limited Kiro quota
>
> MVP stack: Python, Streamlit, `asyncio`, Amazon Bedrock, Docker, ECR, EC2

## 1. Decision Summary

Adopt a strict capability ladder: Bronze first, then Silver, then Gold. Platinum is post-freeze, post-hackathon or explicitly out-of-band future work only. Each required layer may start only after the previous layer has an executable demo, explicit verification evidence, and a known rollback path. At every checkpoint, the fallback is the last passed layer rather than an unfinished mixture of newer features.

The two-day target is Gold. Bronze is the non-negotiable offline baseline, Silver proves the live evidence and Bedrock path, and Gold proves degradation, deployment, and rehearsal. Platinum is excluded from MVP Acceptance and cannot delay feature freeze.

This proposal preserves the approved H2-Lite direction while reducing delivery risk:

```text
Streamlit -> ApplicationService -> bounded asyncio pipeline
          -> deterministic evidence/conflict policies
          -> bounded Bedrock structured output
          -> deterministic renderer -> four fixed artifacts
```

It does not introduce FastAPI, a queue, database, message broker, durable workflow engine, or a separate worker service.

### 1.1 Review Basis and Input Gap

The proposal applies this source order:

1. Approved product design and stated competition constraints.
2. Current Kiro Requirements, Design, and Tasks.
3. Approved four-person workflow and ownership.
4. Production system design concepts only as non-binding architecture reference.

`SYSTEM_DESIGN_REFERENCE.md` did not exist when this proposal was originally created. A subsequent read-only architecture review has now been completed, and the proposal remains subordinate to the approved product design and Kiro specifications. This later review must not be described as an input to the proposal's original creation, nor converted into claims that production architecture is approved or implemented.

The repository currently contains specifications and data but no `src/`, `tests/`, or runtime implementation tree. This proposal does not claim that any test, external service, image, deployment, or rehearsal has passed.

## 2. Non-negotiable Delivery Rules

- Reliability remains the enum `high|medium|low`; no numeric reliability score is added.
- The required artifacts remain exactly:
  - `final_report.md`
  - `evidence.json`
  - `execution_log.jsonl`
  - `run_config.json`
- Markdown and Streamlit are the MVP presentation formats. PDF and HTML are Platinum exports only and never replace the four required artifacts.
- Market numbers, reliability, conflict detection, report rendering, and failure fallback remain deterministic.
- LLM output must be structured, schema-validated, evidence-bound, and unable to invent market values.
- Each LLM operation uses an operation-specific `max_tokens`, and each stage uses a finite, allowlisted tool plan. The MVP does not introduce a separate token or tool-call accounting subsystem; stage deadlines remain the hard execution control.
- Retrieved external content is treated as untrusted data. It cannot override system policy, select unallowlisted tools or URLs, or enter a claim until it has been normalized, schema-validated, and linked to Evidence.
- Instructions embedded in web pages or research content are never treated as system instructions. External content cannot expand the tool or domain allowlist, and this control does not require an additional security service or sandbox infrastructure.
- Every Evidence item records `fetched_at`, source or published time when available, cache or stale metadata, and the immutable `analysis_as_of`. Missing, stale, or ambiguous time metadata must be disclosed in limitations or degradation notes.
- `official`, `rehearsal`, and `demo` remain visibly distinct. An official run never silently loads fixtures or a recorded run.
- Unconfirmed competition interpretations remain documented working assumptions, not confirmed facts.
- A failed stage preserves completed evidence, logs, and artifacts whenever possible; a partial run is labelled partial.
- No Future Architecture component is part of the MVP Acceptance criteria.

## 3. Capability Ladder

### 3.1 Bronze — Offline Safety Baseline

**Capabilities**

- One fixture `AnalysisRequest` for a single asset.
- Fixture Evidence Ledger and fixture `AnalysisResult`.
- Streamlit input and result view.
- Deterministic Markdown renderer.
- Incremental creation of the four fixed artifacts.
- Run-state enum, in-process progress events, Execution Log, deterministic reliability/conflict policies, and deterministic insufficient-data fallback.
- No network, Bedrock, AWS account, API key, or deployment dependency.

**Entry Gate**

- Approved field names, enums, fixed artifact names, report sections, and run-mode semantics are frozen.
- P1 publishes the minimal request/evidence/result/progress contracts and fixture boundaries.
- A representative fixture contains no secrets and can be redistributed within the repository.

**Exit Gate**

- A local command starts Streamlit and accepts a single-asset fixture request.
- The request deterministically produces all four fixed artifacts with one consistent `run_id`.
- `final_report.md` is Traditional Chinese, uses the approved report sections, and renders only fixture-backed facts.
- `evidence.json` and `execution_log.jsonl` are parseable and trace the rendered claims.
- Repeating the same fixture yields semantically identical Evidence, report, reliability, conflict, and fallback results, apart from explicitly variable run metadata.
- An empty or invalid analysis fixture produces a clearly labelled insufficient-data report rather than an invented answer.

**Fallback**

- Bronze is itself the offline fallback. Preserve a known-good fixture bundle and launcher.
- If a later layer fails, return to Bronze as `run_mode=rehearsal`, or show a recorded bundle as `run_mode=demo`; never label either as official.

### 3.2 Silver — Live Core

**Capabilities**

- One asset per run.
- Organizer CSV as the historical baseline.
- One required baseline live market source.
- One required baseline research source.
- Bedrock structured output through a thin, bounded client.
- Evidence IDs, source metadata, Claim-Evidence Links, and deterministic traceability checks.
- Bronze remains intact and runnable without the network.

The recommended Silver source set is Binance for live market data and one research path selected during Day 1 service preflight. CoinGecko is not required for Silver; it remains Platinum unless the team deliberately swaps it in as the single live market source.

Additional sources are optional, non-blocking, and may only be attempted after the required baseline path is stable. Failure of an optional source must not fail Silver.

**Entry Gate**

- Bronze Exit Gate passes.
- The selected market source, research source, and Bedrock model are preflighted with redacted pass/fail evidence, or the team explicitly records which service is blocked.
- Domain and host allowlists are frozen; neither the user nor the LLM can provide arbitrary URLs.
- Provider adapters return typed success, empty, timeout, and error results.

**Exit Gate**

- A single-asset live run combines Organizer CSV, one live market source, and one research source.
- Silver requires at least one successful schema-valid Bedrock result using the baseline live market and research paths. Deterministic fallback must also be tested, but fallback-only execution does not satisfy the Silver success gate.
- When Bedrock fails, the deterministic Renderer produces honestly labelled partial or degraded artifacts; fallback must not be presented as a successful live AI run.
- Every report market number resolves to deterministic tool evidence; every conclusion resolves to Evidence IDs or is marked insufficient.
- Source name/URL, time, parameters/range, content reference, reliability, and independence group are retained.
- Live Evidence includes `fetched_at`; source or published time is retained when available; stale or unavailable freshness metadata is explicitly disclosed; and `analysis_as_of` remains immutable throughout the run.
- Four fixed artifacts are produced and Bronze still runs with network and Bedrock disabled.

**Fallback**

- A Silver live failure remains an official partial result if useful official evidence exists.
- Switching to Bronze requires an explicit mode change to `rehearsal`; using a saved run requires `demo` plus recorded timestamp disclosure.
- Bedrock failure uses deterministic `AnalysisResult`/report fallback; it does not call another unapproved orchestration path.

### 3.3 Gold — Stable Competition Build

**Capabilities**

- Explicit Market source failure behavior.
- Explicit Research source failure behavior.
- Explicit Bedrock/schema failure behavior.
- Partial completion with deterministic fallback and all four artifact filenames.
- At least two supported assets verified as separate single-asset runs; this does not require dual-asset comparison.
- One Docker image, immutable ECR tag, one EC2 host, one Streamlit service.
- At least one full timed judged-flow rehearsal with a documented rollback.

**Entry Gate**

- Silver Exit Gate passes locally.
- Market, research, Bedrock, renderer, and artifact failure fixtures are available.
- Deployment owner, EC2 region, IAM approach, image tag convention, health check, and rollback command are recorded without secrets.
- No unresolved contract change is in progress.

**Exit Gate**

- Failure injection demonstrates that each of Market, Research, and Bedrock may fail independently while the run reaches a truthful terminal state.
- Completed branches are retained, degradation is visible, and fixed artifacts remain schema-valid even when content is partial or insufficient.
- At least two assets complete the Gold path as individual runs.
- The tested Docker image is pushed with an immutable tag and the same tag is started on EC2.
- A timed rehearsal covers question entry, progress, report/evidence/log inspection, four artifact downloads, live failure recovery, and rollback.
- The team records actual results; it does not infer that a test or service passed from configuration alone.

**Fallback**

- On EC2 failure, run the same image locally or use the last reachable immutable image.
- On live-source failure, retain an official partial result; for presentation continuity, use a clearly labelled recorded `demo` run.
- On a regression discovered after freeze, revert to the last passed Silver or Bronze tag rather than adding emergency features.

### 3.4 Platinum — Bonus Work

Platinum is post-freeze and outside the two-day required delivery scope. It is post-hackathon or explicitly out-of-band future work only, after the Gold Demo, deployment path, and submission backup are complete.

**Capabilities, in priority order**

1. One additional research source.
2. CoinGecko live market fallback.
3. Complete five-asset verification.
4. ~~Dual-asset comparison using comparable measures only.~~ **Removed from Platinum 2026-08-01** — promoted to a committed capability (Requirement 17 / Task 12), scheduled after Silver and before Feature Freeze.
5. Evidence visualization.
6. PDF and/or HTML export derived from deterministic Markdown.
7. UI polish.
8. H3 Conditional Debate, last and only after all other desired Platinum work is stable.

**Entry Gate**

- Gold Exit Gate and the two-day submission work are complete, the submission backup is preserved, and a rollback to the Gold image is proven.
- Platinum is not an exception to Feature Freeze and may not be started during the formal two-day delivery period.
- Each selected Platinum item has a time box, owner, deterministic acceptance check, and kill switch or isolated revert.

**Exit Gate**

- The selected bonus feature passes its isolated check and does not change Gold behavior when disabled.
- The four canonical artifacts remain present. PDF/HTML are optional derived exports and are not counted as required artifacts.
- Five-asset or dual-asset claims are accepted only after their actual matrix/comparison checks are recorded.
- H3 may be described as implemented only after a timed rehearsal is retained; otherwise it stays an unimplemented extension.

**Fallback**

- Disable or revert the Platinum feature and redeploy the last Gold tag.
- Any Platinum failure ends bonus work; it does not reopen Gold architecture or postpone submission work.

## 4. Architecture Classification

### A. Implement Now

These concepts directly improve a two-day in-process MVP and belong in Bronze through Gold Acceptance.

| Concept | MVP interpretation |
|---|---|
| Run-state enum | Small explicit lifecycle such as `idle/running/partial/completed/failed/cancelled`; no job database or queue semantics |
| Stage deadlines | Monotonic in-process deadlines; per-call timeouts and retries are clamped to the current stage |
| Progress events | Typed in-memory events sent to Streamlit and appended to JSONL; no network event transport |
| Partial completion | Preserve successful branch output and truthfully label unavailable branches |
| Tool/domain allowlist | Fixed assets, providers, official domains, operations, and URL hosts; no dynamic tool discovery |
| Evidence traceability | Evidence IDs, Claim-Evidence Links, source metadata, `based_on_claim_ids`, and deterministic validation |
| Execution Log | Append-only `execution_log.jsonl` with stage/tool lifecycle, sanitized parameters, status, and public-safe errors |
| Four artifacts | Incremental local creation with the four approved fixed filenames |
| Deterministic policies | Static `high|medium|low` reliability, exact dedup, independence groups, material conflict, confidence caps |
| Deterministic output | Template rendering, recommendation lint, insufficient-data and Bedrock-failure fallback |
| In-process concurrency | Plain `asyncio` fork/join with cancellation cleanup; no durable workflow framework |
| Local recovery | Known-good fixtures, recorded demo disclosure, immutable image tags, and documented rollback |

### B. Model Now, Implement Later

Keep only the smallest seam needed to avoid coupling the MVP to local details. Do not build supporting infrastructure.

| Concept | Model now | Explicitly defer |
|---|---|---|
| Job identity | Keep the current `run_id` as the synchronous operation identifier and reserve a future mapping to `job_id` | Separate job lifecycle, job API, persistence, and distributed ownership |
| Cancellation status | Include terminal cancellation/deadline outcomes in the run/result schema | User-facing remote cancel endpoint and cross-process cancellation |
| Artifact storage interface | Retain a narrow artifact writer/store port with one local-filesystem implementation | S3, signed URLs, retention service, replication, and artifact database |
| Source adapter protocol | Retain a typed `SourceAdapter` protocol returning validated success, partial, empty, or failure results | Provider registry service, remote discovery, or independent adapter services |
| Tool registry abstraction | Back a `ToolRegistry` abstraction with a static allowlist and local adapter references | Dynamic registration, plugin marketplace, or health-routing control plane |
| Future persistence boundary | Retain a port for run summaries and artifact references with no persistent MVP implementation | Job database, checkpoint store, retention service, or distributed ownership |
| Future async boundary | Keep `ApplicationService.run(...)` asynchronous and return a typed `RunSummary` | API service, enqueue/claim protocol, background job polling, and worker fleet |
| Progress contract | Version progress events so Streamlit does not inspect pipeline internals | SSE, WebSocket, remote subscriptions, or persisted event streams |

Retain a typed `SourceAdapter` protocol, a static-allowlisted `ToolRegistry` abstraction, and a future persistence port for run summaries and artifact references. Their MVP implementations remain local or in-memory and require no Database, Queue, broker, or independent service.

These are compatibility seams, not infrastructure requirements. No new abstraction should be added solely to imitate production infrastructure. If the current `ApplicationService`, typed ports, and local artifact writer already provide the seam, document that seam instead of creating another layer.

### C. Future Architecture Only

These belong only in a clearly labelled Production Evolution section or presentation. They are not MVP Requirements, MVP Tasks, acceptance gates, or claims of current implementation:

- API Gateway.
- Authentication or authorization service.
- Job metadata database.
- Queue, message broker, and durable workflow engine.
- Independent worker service or horizontally scaled worker fleet.
- DLQ and production circuit-breaker infrastructure.
- Polling API, SSE, or WebSocket delivery.
- Horizontal scaling, autoscaling, and multi-instance scheduling.
- Scheduler and notification services.
- Production retention, tenancy, HA, and operational control-plane components.

Future diagrams must visually separate this list from the current single-process Streamlit/EC2 MVP and use labels such as “future”, “not implemented”, or “production evolution”.

## 5. Four-Person Ownership

The approved ownership model remains valid. The staged ladder changes sequencing, not domain boundaries.

| Person | Stable ownership | Bronze | Silver | Gold / freeze |
|---|---|---|---|---|
| P1 Integration / Release | Contracts, run state, deadlines, application service, artifacts, merge gates | Freeze minimum contracts; integrate fixture flow and four artifacts | Integrate typed adapters/Bedrock boundary; protect Bronze | Failure matrix, release tag, rollback decision, final acceptance owner |
| P2 Data / Evidence | CSV, live market/research adapters, deterministic metrics, Evidence Processor | Supply fixture Evidence and deterministic policy cases | Organizer CSV + one market source + one research source | Source-failure fixtures, second asset verification, repair data/evidence defects only |
| P3 Reasoning / Report | Bedrock structured output, claims, deterministic renderer/fallback | Fixture `AnalysisResult`, renderer, traceability checks | Bounded Bedrock result and evidence-bound claims | Bedrock/schema failure path; after freeze, no H3 unless Gold is fully accepted |
| P4 UI / Demo Support | Streamlit, progress presenter, container, runbook, rehearsal records | Streamlit against fakes and four downloads | Live/partial/fallback badges and operator flow | Co-own Docker/ECR/EC2 with P1; operate timed rehearsal and recorded demo disclosure |

Cross-owner rules:

- P2 owns research HTTP adapters, research source integration, normalization, timeout, and degradation behavior.
- P3 owns Planner, Research Agent orchestration, Bedrock reasoning, structured-output validation, and reasoning fallback.
- P2 does not own Bedrock reasoning.
- P3 does not own low-level research HTTP adapter implementation.
- Only P1 merges shared contracts; every affected owner acknowledges a contract change.
- P4 never owns deployment risk alone; P1 co-owns image, EC2, health check, and rollback.
- P2 never writes reports or calls Bedrock. P3 never fetches provider data or writes artifacts directly. P4 calls only the application/presenter boundary.
- Every owner provides fixtures/fakes first so another service never becomes a coding blocker.

## 6. Two-Day Checkpoints

| Checkpoint | Required outcome | Gate decision |
|---|---|---|
| Day 1, T+0 to T+45 | Service preflight recorded; contracts, artifact names, enums, source allowlists, and ownership frozen | If external services are blocked, continue Bronze; do not redesign architecture |
| Day 1, T+45 to T+150 | Bronze request -> fixture evidence/result -> deterministic report -> four artifacts through Streamlit | Bronze must pass before parallel live work begins |
| Day 1, afternoon parallel block | P1 runtime controls, P2 selected sources, P3 Bedrock/traceability, P4 UI presenter/container | Each branch integrates through frozen ports and preserves offline fakes |
| End of Day 1 | Silver single-asset path integrated locally; Bronze rerun remains available | If Silver is unstable, demo Bronze and repair Silver first on Day 2 |
| Day 2, morning | Gold failure drills, at least two single-asset runs, Docker configuration, local judged-flow rehearsal | Gold core must pass before deployment; Platinum remains post-hackathon or explicitly out-of-band |
| Day 2, midday | Feature Freeze begins, or starts earlier when Gold acceptance is reached | After freeze: fixes, deployment, rehearsal, docs, submission verification only |
| Day 2, afternoon | Exact image tag on ECR/EC2, health/smoke check, timed rehearsal, rollback and recorded demo disclosure | If deployment fails, use local Gold image or last passed layer; do not add infrastructure |
| Final block | Secret review, artifact inspection, truthful capability labels, submission package | Platinum is not started during the formal two-day delivery block |

## 7. Feature Freeze Policy

Feature Freeze starts when the Gold local acceptance gate passes or at Day 2 midday, whichever occurs first.

Within the two-day delivery, post-freeze means no new product work. Platinum remains post-hackathon or explicitly out-of-band future work after the Gold Demo, deployment path, and submission backup are complete; it is never an exception to Feature Freeze and cannot block Gold, Demo, deployment, or submission.

Allowed after freeze:

- Fix a reproduced defect.
- Complete Docker/ECR/EC2 deployment and rollback documentation.
- Run failure drills and timed rehearsals.
- Correct documentation, presentation labels, or secret exposure.
- Revert to the last passed layer or immutable image.

Not allowed after freeze:

- Add a new provider, framework, output format, Agent role, or infrastructure service.
- Change shared schemas for convenience rather than a blocking correctness defect.
- Start H3, PDF/HTML, evidence visualization, or visual polish. (Dual-asset comparison is no longer in this list — as of 2026-08-01 it is committed Requirement 17 work that must land *before* freeze, not after it.)
- Replace deterministic policy with model judgment.

P1 is the freeze owner and may stop optional work whenever artifacts, integration, deployment, or rehearsal is at risk.

## 8. Adopt-Now System Design Concepts

The useful production-design ideas are behavioral contracts, not production infrastructure:

1. **Explicit state:** a typed run lifecycle and terminal partial/failure/cancelled outcomes.
2. **Deadline ownership:** a single in-process deadline manager using monotonic time and stage budgets.
3. **Observable progress:** versioned progress events mirrored to Streamlit and Execution Log.
4. **Failure isolation:** `asyncio` branch failures become typed results; successful output is retained.
5. **Idempotent local artifacts:** stable names, atomic replacement where practical, checksums, and incremental persistence.
6. **Port boundaries:** Bedrock, sources, artifact writing, clock, and progress are narrow interfaces with local/fake implementations.
7. **Allowlisted execution:** providers, hosts, assets, and operations are fixed by configuration rather than chosen by an LLM.
8. **Traceable reasoning:** validated evidence and claim graphs are the only path into the deterministic renderer.
9. **Truthful recovery:** official partial, rehearsal fixture, and recorded demo are distinct outcomes.

These concepts fit one process and one EC2 instance. None requires a queue, database, API gateway, or separate worker.

## 9. Minimal Changes Recommended for Existing Kiro Documents

This proposal does not apply these edits. The next approved spec-maintenance pass should make surgical changes rather than rewrite the documents.

These delivery-scope adjustments remain proposals until explicitly applied through the Spec Diff Plan and approved specification patch.

### 9.1 Requirements

- Add a short “Staged Acceptance” preface mapping Bronze, Silver, Gold, and Platinum.
- Keep Requirements 1–13 behavior, but attach acceptance levels:
  - Bronze: fixture request/evidence/result, Streamlit, deterministic renderer, four artifacts.
  - Silver: single asset, Organizer CSV, one live market source, one research source, Bedrock structured output, traceability.
  - Gold: failure drills, partial completion, two assets as separate runs, Docker/ECR/EC2, timed rehearsal.
  - Platinum: CoinGecko fallback, extra research source, five-asset matrix, dual comparison, visualization, PDF/HTML, polish, H3.
- In Requirement 3, keep Binance as the recommended Silver live source but move mandatory CoinGecko fallback acceptance to Platinum.
- In Requirement 4, keep “three source types/three groups/one first-hand source” as a disclosed target unless confirmed by organizers; do not make Silver failure depend on it.
- In Requirement 15, change five-asset and three-live-rehearsal requirements from the two-day Gold gate to Platinum targets. Gold requires at least two assets and at least one timed rehearsal.
- Keep Requirement 14 H3 clauses future-conditional and visibly outside MVP.
- Preserve every existing fixed enum, artifact name, deterministic rule, and run-mode honesty requirement.

### 9.2 Design

- Add one staged runtime table before the current full H2-Lite diagram.
- Show Bronze as the first executable composition using fixture ports; Silver swaps in only the selected live adapters and Bedrock; Gold adds failure acceptance and deployment, not new topology.
- Keep Streamlit and `ApplicationService` in one process. Progress uses callbacks/events, not a polling API.
- Retain local artifact and source interfaces as future seams without S3, a registry service, or a separate executor.
- Remove CoinGecko from the required Silver path; describe it under Platinum fallback.
- Keep PDF/HTML as derived Platinum exports and Markdown as canonical.
- Add a clearly separated “Production Evolution — not implemented” section containing only Category C concepts.

### 9.3 Tasks

- Replace the current 10 required + 2 optional top-level Tasks with the eight-task sequence in Section 10.
- Move service preflight into Task 1 rather than keeping it as a separate implementation wave.
- Make the first executable result Bronze, not a partial scaffold waiting for later components.
- Treat two-asset verification as two separate single-asset Gold cases. ~~keep dual comparison in Platinum~~ — **superseded 2026-08-01:** dual-asset comparison is now committed Requirement 17 / Task 12 work, executed after Silver and before Feature Freeze. The two separate Gold cases remain, and neither substitutes for the other.
- Move CoinGecko, five-asset full matrix, extra research source, PDF/HTML, visualization, polish, and H3 out of required tasks.
- Keep per-owner subtasks, exact verification commands, and Kiro task-to-commit evidence, but do not use Kiro “Run all Tasks”.

### 9.4 Steering

- `competition-rules.md`: add staged gates and keep the three organizer interpretations explicitly unconfirmed.
- `product.md`: replace the all-at-once success list with Bronze/Silver/Gold outcomes; list Platinum separately.
- `tech.md`: retain the locked stack and add explicit bans on queues, databases, message brokers, FastAPI, remote progress transports, and separate workers for this MVP.
- `structure.md`: keep the lean tree; document local `ArtifactStore`, static source lookup, async service, and progress event as interfaces rather than new packages/services.
- `evidence-contracts.md`: no enum or conflict-policy rewrite; only add cancellation/partial terminal-state fields if absent.
- `testing.md`: create a gate command per layer; live tests remain opt-in and no pass claim is allowed without current evidence.
- `development-workflow.md`: add the Gold-or-midday Feature Freeze rule and “fallback to last passed layer” requirement.

## 10. Proposed Top-Level Tasks — Maximum Eight

### Task 1: Freeze Scope, Contracts, and Service Preflight

- Owners: P1 and P4; all review.
- Freeze request/evidence/result schemas, enums, artifact names, progress events, run states, allowlists, local ports, and stage budgets.
- Record redacted Bedrock/research/AWS preflight outcomes without blocking Bronze.
- Exit: contracts accepted; fixtures and fakes can satisfy every external port.

### Task 2: Deliver Bronze End-to-End

- Owners: P1 + P3, with P4 UI and P2 fixture support.
- Build fixture request/evidence/result, deterministic renderer/fallback, Execution Log, Streamlit, and four fixed artifacts.
- Exit: fully offline, executable, traceable Bronze demo.

### Task 3: Add In-Process Runtime Controls

- Owner: P1.
- Add stage deadlines, `asyncio` fork/join, cancellation cleanup, progress events, partial state, atomic/incremental artifact writes, and failure recording.
- Exit: fake-clock and branch-failure scenarios preserve completed output and finish deterministically.

### Task 4: Add Silver Data and Bedrock Paths

- Owners: P2 market/research adapters; P3 Bedrock structured output; P1 integration.
- Add Organizer CSV, one live market source, one research source, static source metadata, bounded Bedrock output, and Bronze fallback preservation.
- Exit: single-asset Silver path and offline Bronze both remain runnable.

### Task 5: Enforce Evidence and Report Integrity

- Owners: P2 evidence policies; P3 claims/renderer; P1 final validation.
- Enforce static reliability, exact dedup, independence, material conflict, confidence caps, claim/evidence graph validation, deterministic lint, and fallback.
- Exit: all rendered claims trace to evidence or explicitly state insufficient data.

### Task 6: Pass Gold Failure and Two-Asset Gates

- Owners: all; P1 owns gate.
- Exercise market failure, research failure, Bedrock/schema failure, partial completion, artifact failure handling, and two assets as separate runs.
- Exit: every required degradation path ends truthfully with inspectable fixed artifacts.

### Task 7: Containerize and Deploy Gold

- Owners: P1 + P4.
- Build one image, push immutable ECR tag, deploy one Streamlit service on one EC2 instance, health/smoke check, and document rollback.
- Exit: tested tag and deployed tag match, or documented local-image fallback is selected.

### Task 8: Freeze, Rehearse, and Verify Submission

- Owners: all; P4 operates, P1 signs off.
- Freeze features, conduct at least one timed judged-flow rehearsal, inspect artifacts, verify recorded-demo disclosure, review secrets, and prepare truthful presentation labels.
- Exit: Gold evidence package is complete; Platinum remains outside the two-day delivery and requires separate post-hackathon or out-of-band planning.

## 11. Five Largest Risks

| Risk | Why it is large | Mitigation and rollback |
|---|---|---|
| Scope exceeds two junior-days per person | Current documents require many providers, five assets, multiple rehearsals, deployment, and optional systems | Enforce layer gates, eight tasks, Gold-or-midday freeze; revert to last passed layer |
| Bedrock or research service access is unavailable or unstable | Region/model access, tokens, throttling, and API drift can block the live path | Day 1 preflight, typed errors, bounded retries, deterministic fallback, Bronze offline demo |
| Evidence traceability or policy becomes inconsistent across modules | LLM, adapters, claims, and renderer may drift on IDs, reliability, conflicts, or time ranges | Freeze shared contracts, deterministic validators, one owner per boundary, evidence-only rendering |
| Integration and ownership collisions consume the schedule | Four developers can change shared models, application flow, and UI contracts simultaneously | P1-only shared merges, fixture-first ports, checkpoint syncs, no silent contract conflict resolution |
| Deadline/deployment failure appears only during the final demo | Local success does not prove 13-minute behavior, container health, EC2 reachability, or rollback | Fake-clock tests, early local judged-flow run, immutable image tags, health check, timed rehearsal, recorded demo disclosure |

## 12. Recommended Kiro, Codex, and Claude Code Division

### Kiro — specification evidence and bounded task execution

- Spend limited quota on the minimal staged edits to Requirements, Design, Tasks, and always-included Steering.
- Use Kiro to open one dependency-safe task at a time, preserve task history, and record task-to-commit evidence.
- Use Kiro for contract-sensitive acceptance criteria, not broad “Run all Tasks” generation or routine formatting.
- Stop Kiro-driven scope expansion when a suggestion adds Platinum or Future Architecture to Gold.

### Codex — repository-wide consistency and integration

- Own cross-file audits, staged-scope consistency, implementation-plan reconciliation, and shared-contract review.
- Assist P1 with application/orchestration/artifact integration, deterministic verification commands, failure-path review, and minimal diffs.
- Before any completion claim, inspect current outputs and repository state; do not infer pass status from specs or prior logs.
- Prefer read-only review when asked to audit, and keep unrelated user changes untouched.

### Claude Code — focused owner-scoped component work

- Give it bounded tasks with frozen input/output contracts, exact owned paths, fixtures, and focused verification commands.
- Suitable work includes one adapter, one deterministic policy module, one renderer/presenter slice, or one reproducible defect.
- Do not assign it simultaneous shared-contract edits or open-ended architecture redesign.
- Require its handoff to include changed paths, current verification evidence, assumptions, and any unresolved service dependency.

### Coordination Rule

One human owner and one active coding tool own a file set at a time. Kiro defines/records the task, Codex performs cross-boundary review and integration support, and Claude Code performs isolated owner-scoped implementation where useful. Tools must not make competing edits to the same branch or treat another tool's unverified statement as evidence.

## 13. Final Recommendation

Immediately adopt Bronze-first gates, the eight-task plan, explicit state/deadline/progress/partial contracts, evidence traceability, Execution Log, deterministic policies/fallback, the four fixed artifacts, and the Gold-or-midday Feature Freeze.

Model only the interfaces for future job identity, cancellation status, artifact storage, static source lookup, progress events, and asynchronous execution. Keep their only MVP implementations local and in-process.

Keep API Gateway, authentication, job database, queues, durable workflows, worker fleets, DLQ/circuit-breaker infrastructure, polling/SSE/WebSocket, horizontal scaling, schedulers, and notifications exclusively in a labelled Future Architecture section. They must not enter the two-day MVP Requirements, Tasks, acceptance gates, or implementation claims.
