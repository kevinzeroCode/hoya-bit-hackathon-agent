# HOYA Market Agent Spec Diff Plan

> Status: read-only change impact analysis and minimum-patch plan
>
> This document records the approved D1–D8 delivery-scope decisions but does not apply any specification change. It does not replace Requirements, Design, Tasks, Steering, the approved product design, or the approved team workflow.
>
> D1–D8 authorize only the next minimal Requirements patch. Other Proposal recommendations remain proposals until separately approved and applied through a reviewed specification patch.

## Analysis Basis and Source Priority

The analysis uses this precedence:

1. Approved product design and confirmed competition constraints.
2. Current Kiro Requirements.
3. Current Kiro Design.
4. Current Kiro Tasks.
5. Approved four-person workflow.
6. `STAGED_DELIVERY_PROPOSAL.md`.
7. `SYSTEM_DESIGN_REFERENCE.md` as a non-binding reference only.

Where the Proposal conflicts with the current approved product design, this plan records an explicit decision rather than treating the Proposal as already applied. D1–D8 now approve the target delivery-scope changes for the next minimal Requirements patch; the current Requirements, Design, Tasks, Steering, and workflow remain unchanged until their respective reviewed patches are applied.

Change Matrix values are restricted to `Add`, `Amend`, `Remove`, `Clarify`, `Preserve`, and `No change`. Risk values are restricted to `Low`, `Medium`, and `High`.

## 1. Executive Summary

### Specifications that need a patch

- `.kiro/specs/hoya-market-agent/requirements.md` needs a small staged-acceptance preface, an external-content isolation requirement, and targeted clarification of bounded tools and the Silver Bedrock success gate. Requirement 3, Requirement 15, and the Scope Guard may be amended only after the high-priority product-scope decisions in Section 7 are approved.
- `.kiro/specs/hoya-market-agent/design.md` needs stage labels, explicit external-content isolation, static `ToolRegistry` wording, and documentation that the existing typed ports are the compatibility seams. Its topology, sequence, domain model, deadline design, failure model, artifact flow, and deployment topology should not be redrawn.
- `.kiro/specs/hoya-market-agent/tasks.md` has thirteen top-level tasks, including eleven required tasks and two optional tasks. It should be consolidated to no more than eight top-level tasks after Requirements and Design stabilize. The consolidation must preserve test details while making Bronze an explicit blocking gate.
- Selected Steering files need conditional, surgical amendments only if the related product-scope decisions are approved. The evidence contract does not need a patch.

### Files that do not need a patch in this operation

- `docs/ai/STAGED_DELIVERY_PROPOSAL.md` and `docs/ai/SYSTEM_DESIGN_REFERENCE.md` are inputs, not patch targets.
- `.kiro/steering/evidence-contracts.md` already covers immutable `analysis_as_of`, Evidence freshness fields, Claim-Evidence Links, supporting and opposing stances, categorical reliability, deterministic material conflict, limitations, degradation, execution events, and artifact contracts.
- The approved H2-Lite runtime topology, same-process `ApplicationService`, bounded `asyncio`, deterministic Renderer, local artifacts, Docker/ECR/EC2 deployment shape, and disabled H3 interface should be preserved.
- The approved team workflow ownership remains authoritative unless a separate ownership change is approved. P2 owns provider HTTP and Evidence work; P3 owns Planner, Research Agent orchestration, Bedrock, result validation, and Renderer semantics; P1 owns shared contracts, application integration, and artifact-writing contracts; P4 owns Streamlit presentation/download wiring and co-owns deployment with P1.

### Three largest consistency risks

1. **Scope authority mismatch — High.** Proposal deferrals for CoinGecko, the five-asset matrix, three rehearsals, and Platinum timing conflict with approved product-design Sections 10.1, 17, 18.1, and 20 and workflow lines 22 and 98–102. Patching Kiro Specs first would invert the required source priority.
2. **Ownership collision — High.** Describing P4 as owner of deterministic Renderer semantics or the artifact writer conflicts with the approved product design and workflow, which assign Renderer work to P3 and shared artifact contracts to P1. The safe interpretation is that P4 owns presentation and downloads, not core rendering or persistence semantics.
3. **Gate drift — High.** Current Task 9 defines the freeze gate using five assets and three rehearsals. Renumbering Tasks or redefining Gold before Requirements and Design are approved could trigger freeze against an ambiguous acceptance set and break traceability.

### Recommended patch sequence

Patch Requirements first, then Design, then Tasks, then only the Steering lines made stale by approved decisions, and finish with a cross-file consistency review. Do not start any scope-changing patch until Section 7 decisions marked `Yes` have explicit approval.

## 2. Change Matrix

| File | Section | Current state | Proposed change | Change type | Risk | Owner |
| ---- | ------- | ------------- | --------------- | ----------- | ---- | ----- |
| `.kiro/specs/hoya-market-agent/requirements.md` | Before Requirement 1, lines 8–10 | No Bronze/Silver/Gold/Platinum acceptance map | Add a short non-normative stage map; state that proposal-only scope changes remain conditional on approval | Add | Medium | P1 / product owner |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 1 | Has `run_id`, immutable request context, one-to-two asset contract, and H3 flag | Keep contract; do not turn `run_id` into a Job API or persistence requirement | Preserve | Low | P1 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 2 | Defines `official`, `rehearsal`, `demo`, immutable cutoff, cache time, and stale state | Clarify that source/published time is retained when available and missing freshness is disclosed | Clarify | Low | P1 + P2 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 3 | Binance is canonical, CoinGecko is required fallback, and five-asset overlap calibration is required | Amend only if Decision 1 is approved; otherwise preserve current core source policy | Amend | High | Product owner + P2 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 4 | Names several research/context sources and treats three types/groups plus one first-hand source as a quality target with degradation | Clarify one baseline research path as the Silver minimum without making optional sources an exactly-one cap; keep quality gaps disclosed | Clarify | High | Product owner + P2 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirements 5–6 | Defines Evidence fields, Claim-Evidence Links, supporting/opposing stance, categorical reliability, and deterministic conflict/confidence rules | Keep field names and invariants unchanged | Preserve | Low | P2 + P3 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 7 | Defines H2-Lite, bounded Research Agent, structured Arbiter output, `max_tokens`, and deterministic Renderer | Add finite static tool-plan and untrusted external-content rules; clarify at least one schema-valid Bedrock success gate if approved | Amend | Medium | P3 + P1 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 8 | Defines total and per-stage deadlines, per-call timeout, bounded retry, and schema repair | Keep deadline controls as the hard budget; do not add accounting services | Preserve | Low | P1 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirements 9–12 | Defines degradation, deterministic fallback, four artifacts, report honesty, Streamlit, progress, and run-mode labels | Keep behavior; add no PDF/HTML MVP requirement | Preserve | Low | P1 + P3 + P4 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 14 | Requires only a disabled H3 interface in MVP; full H3 clauses are conditional | Preserve the disabled seam; clarify post-freeze timing only if the product decision is approved | Clarify | Medium | Product owner + P3 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Requirement 15 | Requires Docker/ECR/EC2, five-asset acceptance, resilience, and three rehearsals | Conditionally narrow Gold to two separate assets and the approved rehearsal count; retain deployment and resilience | Amend | High | Product owner + P1/P4 |
| `.kiro/specs/hoya-market-agent/requirements.md` | Scope Guard, lines 93–95 | Separates MVP core and H3 exclusions but has no staged ladder | Add approved stage boundaries and explicitly keep production infrastructure outside MVP | Amend | Medium | P1 |
| `.kiro/specs/hoya-market-agent/design.md` | §§1–3, lines 9–95 | One-process H2-Lite runtime and sequence already match the MVP | Add stage annotations and external-content validation points without redrawing topology or sequence | Clarify | Low | P1 |
| `.kiro/specs/hoya-market-agent/design.md` | §§4.1–4.3, lines 112–158 | Has `ApplicationService`, `ProgressSink`, typed market/research adapters, `ArtifactStore`, and `LLMClient` | State that these satisfy the compatibility seams; add static `ToolRegistry` and future persistence port only as local/in-memory protocols | Clarify | Medium | P1 |
| `.kiro/specs/hoya-market-agent/design.md` | §§5–7, lines 160–218 | Domain models, run state/degradation types, deadlines, cancellation, and run modes are complete | Preserve models and behavior; do not introduce persistent job state or remote cancellation | Preserve | Low | P1 |
| `.kiro/specs/hoya-market-agent/design.md` | §8.2–8.7, lines 230–268 | Multiple market/research adapters are drawn as current design; CoinGecko is fallback | Mark baseline versus optional providers and isolate external content; CoinGecko placement remains conditional on approval | Amend | High | Product owner + P2 |
| `.kiro/specs/hoya-market-agent/design.md` | §9, lines 270–285 | Normalizes timestamps, reliability, staleness, conflicts, and validates Bedrock output | Clarify `fetched_at`, available source/published time, cache/stale metadata, immutable cutoff, and rejection of instruction-like content | Clarify | Low | P2 + P3 |
| `.kiro/specs/hoya-market-agent/design.md` | §§10–15, lines 287–403 | Disabled H3, degradation, incremental artifacts, Streamlit progress, config, and EC2 deployment are defined | Preserve; keep H3 and all production evolution outside two-day required work | Preserve | Low | P1 + P3 + P4 |
| `.kiro/specs/hoya-market-agent/design.md` | §§16 and 18, lines 405–438 and 511–523 | Tests and gates require current provider set; gates are not named Bronze/Silver/Gold | Add layer gates and conditionally align asset/rehearsal/provider acceptance after product decisions | Amend | High | P1 + all owners |
| `.kiro/specs/hoya-market-agent/tasks.md` | Execution Rules and Wave Map, lines 7–29 | Thirteen top-level tasks; fixture-first intent exists but Bronze does not block every live branch | Replace top-level map with eight dependency-safe gates while retaining focused subtasks | Amend | High | P1 |
| `.kiro/specs/hoya-market-agent/tasks.md` | Tasks 0–2, lines 33–92 | Preflight, contracts, and fixture slice are separate | Consolidate preflight/contracts as Task 1 and make the offline vertical slice Task 2 Bronze Exit | Amend | Medium | P1 + P4; P2/P3 review |
| `.kiro/specs/hoya-market-agent/tasks.md` | Tasks 3–6, lines 94–203 | Runtime, market, research/evidence, and Bedrock are separate but live tasks can start before explicit Bronze Exit | Reframe as Tasks 3–5 with Bronze dependency and strict P2/P3 ownership split | Amend | High | P1 + P2 + P3 |
| `.kiro/specs/hoya-market-agent/tasks.md` | Tasks 7–8, lines 204–245 | UI/container and integration are separate and touch shared integration boundaries | Fold UI Bronze work into Task 2, keep integration through P1, and avoid concurrent edits to `application.py` or artifact contracts | Amend | Medium | P1 + P4 |
| `.kiro/specs/hoya-market-agent/tasks.md` | Task 9, lines 247–268 | Five assets, calibration, failures, and three rehearsals form one gate | Replace with conditional Gold failure/two-asset gate only after scope decisions; otherwise preserve approved acceptance | Amend | High | Product owner + all |
| `.kiro/specs/hoya-market-agent/tasks.md` | Task 10, lines 270–288 | Freeze, deployment, CI, rehearsal, and submission are combined | Split local Gold acceptance from deployment, then use Tasks 7–8 for deployment and frozen submission work | Amend | Medium | P1 + P4 |
| `.kiro/specs/hoya-market-agent/tasks.md` | Optional Tasks 11–12, lines 290–317 | H3 and S3/CloudWatch can start after required gates | Remove from the two-day task graph; retain as post-hackathon notes only if Platinum timing is approved | Remove | Medium | Product owner + P1 |
| `.kiro/steering/evidence-contracts.md` | §§1–15 | Already provides the required Evidence, Claim, conflict, freshness, run, log, and artifact invariants | Keep unchanged | No change | Low | P1 + P2 + P3 |
| `.kiro/steering/development-workflow.md` | Source of Truth and Hard Gates, lines 7–31 | Correct priority links and a Day 2 freeze exist; trigger is not stated independently of task numbering | Clarify Gold-local-acceptance-or-midday trigger and fallback to last passed layer after approval | Clarify | Medium | P1 |
| `.kiro/steering/competition-rules.md` | Approved Data Policy and MVP Exclusions | Current core source policy includes CoinGecko; honesty, deterministic behavior, budgets, and no accounting subsystem are sufficient | Patch only the approved provider/stage decision; preserve all integrity and exclusion rules | Amend | High | Product owner + P1 |
| `.kiro/steering/product.md` | Success Criteria and Scope Control | Five assets and multi-source targets are current success criteria | Add stage labels and change asset target only after approval | Amend | High | Product owner |
| `.kiro/steering/tech.md` | §§1, 5, 7–12 | Already bans extra orchestration, defines allowlists, `max_tokens`, deterministic fallback, local artifacts, and run-mode honesty | Preserve except for conditional CoinGecko wording | Clarify | Medium | P1 + P2 |
| `.kiro/steering/testing.md` | Test Layers and Freeze Gate | Five-asset matrix and three live rehearsals are mandatory | Amend only after asset and rehearsal decisions; preserve all deterministic and failure tests | Amend | High | P1 + all |
| `.kiro/steering/structure.md` | Canonical Tree and File Ownership | Lists current adapters and clean ownership boundaries | Preserve; mark `coingecko.py` optional/future only if that product decision is approved | Clarify | Medium | P1 + P2 |
| `docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md` | Roles, Day 2 checkpoints, lines 15–22 and 92–102 | Approved ownership; five-coin/three-rehearsal gate; Task 9-or-midday freeze | Preserve ownership. Any gate renumbering or scope change needs separate approval before Kiro patch consistency can pass | Preserve | High | Product owner + P1 |

## 3. Requirements Diff Plan

This section describes change intent, not replacement Requirement text.

### Add

#### A1. Staged acceptance preface

- **Current wording summary:** Requirements are organized by behavior and a Scope Guard; they do not map behavior to Bronze, Silver, Gold, or Platinum.
- **Proposed wording summary:** Add a short preface defining Bronze as the offline executable fallback, Silver as the baseline live path, Gold as the stable/deployed path, and Platinum as non-required work. Mark every decision-dependent boundary as conditional until approved.
- **Reason:** The implementation order needs executable gates without rewriting Requirements 1–15.
- **Acceptance impact:** Enables layer-specific acceptance and rollback. It must not weaken current five-asset, provider, or rehearsal acceptance until their decisions are approved.
- **Traceability impact:** Adds a stable stage label that Design gates and Tasks can reference without duplicating behavior.

#### A2. Bounded tool execution and external-content isolation

- **Current wording summary:** Requirement 7 bounds the Research Agent and structured output; Requirements 3–5 restrict sources and Evidence, but no single Requirement states that retrieved text is untrusted and cannot change policy or allowlists.
- **Proposed wording summary:** Require a finite static tool plan; tool/domain/host allowlists; operation-specific `max_tokens`; and rejection of instruction-like external content until it is normalized, schema-validated, and linked to Evidence. State that external text cannot act as a system instruction or expand an allowlist.
- **Reason:** This is a genuine safety and Evidence-honesty gap that can be implemented in-process.
- **Acceptance impact:** Adds deterministic rejection/normalization cases and a finite-plan test; it does not require a security service, sandbox platform, quota database, or token accounting subsystem.
- **Traceability impact:** Maps to Design §§4.3, 8, and 9 and proposed Tasks 1, 4, and 5.

### Amend

#### M1. Requirement 2 — freshness disclosure

- **Current wording summary:** Freezes `analysis_as_of` and records cache time and stale state by run mode.
- **Proposed wording summary:** Explicitly retain `fetched_at`, source/published time when available, cache/stale metadata, and disclose absent or ambiguous timing.
- **Reason:** Requirement 5 already has most fields; Requirement 2 should make run-level freshness honesty unambiguous.
- **Acceptance impact:** Adds assertions for missing, stale, and ambiguous timestamps without adding persistence.
- **Traceability impact:** Aligns Requirement 2 with Requirement 5, `evidence-contracts.md`, Design §§7–9, and Task 5.

#### M2. Requirement 3 — market baseline and CoinGecko

- **Current wording summary:** Binance is canonical and CoinGecko is the required live fallback; five-asset overlap calibration is required.
- **Proposed wording summary:** If approved, keep Binance as the Silver baseline and move CoinGecko plus the complete five-asset calibration to Platinum/post-hackathon. If not approved, preserve current wording.
- **Reason:** This is the largest two-day scope reduction in the Proposal, but it conflicts with the approved product design.
- **Acceptance impact:** Approval would remove CoinGecko failure handling from Silver/Gold and reduce mandatory calibration. No patch is authorized before approval.
- **Traceability impact:** Requires matching changes to Design §§2, 8, 11, 16, and 18; Tasks 4, 6, and 9; and selected Steering.

#### M3. Requirement 4 — Silver research baseline versus quality target

- **Current wording summary:** Several research/context providers are named; three source types, three independent groups, and one first-hand source are targets whose absence causes disclosure/degradation.
- **Proposed wording summary:** Define one required baseline research path for Silver, treat other sources as optional and non-blocking, and preserve the multi-source quality target as disclosure rather than an exactly-one cap or automatic Silver failure.
- **Reason:** A minimum baseline is feasible in two days; an exactly-one restriction would unnecessarily reject useful optional evidence.
- **Acceptance impact:** Silver passes with one stable research path plus honest gaps; optional-source failure cannot fail Silver.
- **Traceability impact:** Aligns Requirements with Design §8, Task 4, Evidence limitations, and source quality reporting.

#### M4. Requirement 7 — live Bedrock success and finite plan

- **Current wording summary:** Requires bounded LLM components, structured schema output, `max_tokens`, and deterministic rendering/fallback.
- **Proposed wording summary:** Require one schema-valid Bedrock result over the baseline live market and research paths for Silver, while separately requiring deterministic fallback coverage. Fallback-only execution is not a Silver success.
- **Reason:** A fallback test proves resilience but does not prove the intended live Bedrock path works.
- **Acceptance impact:** Adds one opt-in live acceptance record plus deterministic failure coverage; no claim of current Bedrock access is permitted.
- **Traceability impact:** Maps to Design §§4.3, 9, and 16 and proposed Tasks 1, 4, and 6.

#### M5. Requirement 14 — H3 timing

- **Current wording summary:** A disabled interface is MVP; conditional full H3 clauses may be considered after core success.
- **Proposed wording summary:** Preserve the disabled interface. If Platinum timing is approved, move full H3 implementation and rehearsal outside the formal two-day delivery.
- **Reason:** This removes the current exception path that could compete with frozen Gold work.
- **Acceptance impact:** No effect on the disabled stub; removes full H3 from two-day acceptance.
- **Traceability impact:** Requires Design §10, Tasks 11, workflow timing, and presentation wording to agree.

#### M6. Requirement 15 — Gold asset and rehearsal scope

- **Current wording summary:** Requires deployment, five-asset fixture coverage, resilience, and three live-source rehearsals.
- **Proposed wording summary:** If approved, retain Docker/ECR/EC2 and resilience, require two assets as separate Gold runs, and require the approved smaller rehearsal count; move the complete five-asset matrix to Platinum.
- **Reason:** This is the central delivery-feasibility proposal.
- **Acceptance impact:** Substantially narrows Gold and therefore requires product-owner approval, not merely an editorial patch.
- **Traceability impact:** Changes Design §§16 and 18, Task 9, Testing Steering, Product Steering, and the approved workflow checkpoints.

#### M7. Scope Guard — explicit production boundary

- **Current wording summary:** Excludes full H3 and several stretch sources/services.
- **Proposed wording summary:** Add the staged boundary and state that Database, Queue, broker, Job API, independent worker, polling, SSE, WebSocket, DLQ, and authentication service are not MVP Requirements.
- **Reason:** Prevents the non-binding production reference from entering acceptance.
- **Acceptance impact:** None beyond scope control.
- **Traceability impact:** Gives Design and Tasks a normative exclusion reference without adding future components to implementation.

### Preserve

| Requirement | Current contract to preserve | Acceptance impact | Traceability impact |
|---|---|---|---|
| Requirement 1 | `run_id`, request validation, one-to-two asset compatibility, immutable run context | No Job API or database acceptance | Keeps UI, events, and artifacts correlated locally |
| Requirements 2 and 12 | Honest `official`, `rehearsal`, and `demo` labels; no fixture/recorded substitution in official mode | Run-mode tests remain mandatory | Same mode appears in UI, logs, config, and reports |
| Requirement 5 | Evidence source/URL, published/fetched time, content reference, normalized fact, categorical reliability, independence, hash, cache/stale fields | Evidence schema remains stable | Existing IDs and JSON remain canonical |
| Requirement 6 | Supporting/opposing/neutral links, claim DAG, deterministic material conflict, confidence caps | Conflict and insufficient-data cases remain mandatory | Renderer must show both sides and limitations |
| Requirements 7 and 11 | Structured Bedrock validation and deterministic Renderer | Invalid output never enters rendering | Preserves `AnalysisResult` boundary |
| Requirements 8–9 | Per-stage deadlines, partial completion, typed degradation, deterministic fallback | Failure paths still produce honest artifacts | Runtime events and degradation notes remain linked |
| Requirement 10 | Exactly `final_report.md`, `evidence.json`, `execution_log.jsonl`, `run_config.json` | All four names remain required | Artifact contract remains stable across all stages |
| Requirement 13 | Comparable-measure rules and one-to-two asset contract | No direct base-volume comparison | Gold may test two assets separately without requiring dual comparison |
| Requirement 15 | Docker, ECR, EC2, secret handling, rollback, and truthful recorded fallback | Deployment remains Gold | Preserves the approved competition delivery shape |

PDF and HTML remain optional derived outputs and must not become MVP acceptance criteria.

### Remove or defer

No approved Requirement is removed by this plan. The following deferrals are conditional proposals:

| Candidate | Current wording summary | Proposed wording summary | Reason | Acceptance impact | Traceability impact |
|---|---|---|---|---|---|
| CoinGecko core fallback | Required by Requirement 3 and approved product design | Defer to Platinum/post-hackathon if approved | Reduce adapter/failure surface | Silver/Gold no longer fail for missing CoinGecko | Amend Design, Tasks, and four Steering references |
| Complete five-asset matrix | Required by Requirement 15 and approved acceptance | Defer complete matrix; use two separate Gold assets if approved | Fit two-day validation budget | Gold asset coverage narrows | Update acceptance, tests, workflow, and product success criteria |
| Three live-source rehearsals | Required by Requirement 15 and approved acceptance | Replace with approved minimum timed rehearsal count | Protect deployment/submission time | Fewer required rehearsal records | Update Tasks, Testing Steering, and workflow |
| Full H3 implementation | Conditionally allowed after core; disabled stub is MVP | Keep stub, defer implementation until after the event if approved | Eliminate post-freeze feature exception | No H3 implementation gate in two days | Keep interface; remove optional implementation Task |
| PDF/HTML and production infrastructure | Not current MVP Requirements | Keep outside Requirements | Avoid scope expansion | None | No MVP Task mapping is allowed |

## 4. Design Diff Plan

### Minimum design amendments

| Area | Current design | Minimum amendment | Preserve |
|---|---|---|---|
| Capability ladder | §18 has ordered gates but no Bronze/Silver/Gold labels | Add a compact mapping table before §18; conditional decisions remain marked unapproved | Existing H2-Lite topology |
| Same-process service | §§2 and 4.1 already use one `ApplicationService` invocation | State that this is the future async boundary and remains same-process | No FastAPI or Job API |
| Bounded `asyncio` | §§2, 3, and 6 use fork/join, monotonic deadlines, cancellation cleanup | Add stage names and make Bronze Exit a prerequisite for live integration | Existing cancellation rules |
| Run state | `RunSummary`, `WorkerResult`, degradation events, and `run_state.py` are present | Normalize terminal names to a cancellation-compatible enum without persistence semantics | In-memory state |
| Deadline handling | §6 defines absolute milestones and stage-bound retries | Preserve unchanged; cite deadlines as hard control over token/tool plans | No budget service |
| Progress events | `ProgressSink` and JSONL lifecycle events are defined | Version the local event contract if absent; keep Streamlit decoupled from pipeline internals | No polling/SSE/WebSocket |
| Adapter interfaces | §4.3 has market and research protocols | Document them as typed `SourceAdapter` specializations instead of creating duplicate layers | Provider payload isolation |
| Tool Registry | Allowlist behavior exists in adapter/config rules but no named protocol | Add a static local `ToolRegistry` abstraction that exposes only approved adapter operations | No dynamic registration/discovery |
| Bedrock validation | §§4.3 and 9 require schema validation and one repair | Add the Silver live-success gate and finite-plan/external-content boundary if approved | Deterministic fallback after failed repair |
| Evidence freshness | §§7–9 retain fetched, source, cache, stale, and cutoff data | Make missing/ambiguous time disclosure explicit | Existing Evidence model |
| Deterministic fallback | §11 covers Planner, branch, Arbiter, and deadline failures | Keep behavior and add stage acceptance references only | No additional LLM fallback path |
| Artifact generation | §12 defines incremental local atomic writes and four names | Preserve unchanged; describe local `ArtifactStore` as the only MVP implementation | No object-storage requirement |
| Feature Freeze | §18 orders work but does not define the trigger | Add Gold-local-acceptance-or-Day-2-midday trigger after approval | Post-freeze fixes/deploy/rehearsal only |
| Future boundary | Non-goals and deployment notes exclude extra frameworks | Add one visibly separated Production Evolution note by reference only | No production component in current diagram or sequence |

### Existing design elements that should not be redrawn

- **Runtime diagram (§2, lines 38–81):** keep Streamlit, one `ApplicationService`, bounded `asyncio`, deterministic Evidence Processor and Renderer, and local artifacts. Only annotate stage ownership and provider optionality.
- **End-to-end sequence (§3, lines 83–95):** keep frozen `analysis_as_of`, parallel Market/Research branches, early Evidence persistence, schema validation, and deterministic finalization. Add external-content normalization before Evidence admission.
- **Public and worker interfaces (§4.1–4.3):** keep signatures for `ApplicationService`, `ProgressSink`, `MarketWorker`, `ResearchAgent`, source protocols, and `LLMClient`. A generic source label must not invalidate existing specialized protocols.
- **Domain model (§5):** keep current model names and cross-object validators. Add no job metadata entity.
- **Deadline/cancellation design (§6):** keep milestone numbers, monotonic timing, bounded retry, cancellation cleanup, and network-free finalization.
- **Run modes (§7):** keep mode immutability and disclosure rules.
- **Evidence and Arbiter flow (§9):** keep deterministic normalization, exact deduplication, static reliability, material conflict, evidence cap, validation, and one repair.
- **H3 interface (§10):** keep `DisabledConflictExtension`; do not add Bull/Bear/Judge implementation to MVP.
- **Failure table (§11):** keep partial completion and honest disclosure. CoinGecko row changes only if its explicit decision is approved.
- **Artifact/log design (§12):** keep local atomic writes, JSONL, four names, and deterministic insufficient-data artifacts.
- **Streamlit and deployment (§§13 and 15):** keep one screen, same-process call, one Docker image, ECR, one EC2 host, IAM role, and local volume.

### Thin compatibility seams

The Design patch should document, not overbuild, these seams:

- `run_id` remains the synchronous local identity.
- `ProgressSink` remains in-process.
- Existing market and research protocols satisfy typed `SourceAdapter` behavior.
- `ToolRegistry` is a static allowlisted lookup over local adapters.
- `ArtifactStore` has one local-filesystem implementation.
- A future persistence port may expose run-summary and artifact-reference methods, but the MVP uses no persistent implementation.
- Terminal states remain cancellation-compatible.
- `ApplicationService.run(...)` remains the same-process async boundary.

The Design must not add Database, Queue, broker, independent worker, Job API, polling, SSE, WebSocket, DLQ, or authentication service to an MVP diagram, sequence, data model, interface requirement, test gate, or deployment topology.

## 5. Tasks Diff Plan

### Current task-set assessment

| Check | Finding | Impact |
|---|---|---|
| Too many | Yes. There are thirteen top-level Tasks: 0–10 required and 11–12 optional. | Four junior developers must track too many gates and cross-task handoffs in two days. |
| Too detailed | The focused test steps are useful, but provider-specific work is promoted to top-level critical-path Tasks. | Retain detailed subtasks under no more than eight delivery Tasks. |
| Production infrastructure | No Queue, Database, broker, worker fleet, DLQ, or WebSocket is required. Optional S3/CloudWatch is outside the required path but still competes for time. | Remove optional infrastructure work from the two-day task graph. |
| Bronze-first dependency | Partial. Task 2 is a fixture vertical slice, but Tasks 4 and 6 can begin from Task 1 without an explicit Bronze Exit. | Make Bronze Exit a hard dependency for live integration while allowing fixture-based owner work after contracts freeze. |
| Entry/Exit Gates | Each Task has dependencies and acceptance, but the stage gates are implicit. | Add explicit Entry Gate and Exit Gate fields for every top-level Task. |
| Ownership | Mostly clear. P2 owns provider/data/evidence work; P3 owns Bedrock/reasoning. | Preserve the split and prevent P2 from owning Bedrock or P3 from owning low-level HTTP adapters. |
| Cyclic dependency | No formal cycle exists. Task 8 integration and Task 9 acceptance create a wide repair loop across earlier owners. | Keep repair ownership local and let P1 alone merge shared integration files. |
| Concurrent file collisions | Tasks 2, 3, 7, 8, and 10 can touch application, artifacts, or presenter boundaries. | Freeze ports first; serialize `application.py`, shared models, and artifact-writer changes through P1. |

The future `tasks.md` patch should retain focused test cases and verification commands beneath the following eight top-level Tasks. This document does not execute them.

### Task 1: Freeze Scope, Contracts, and Service Preflight

- **Objective:** Resolve approved scope decisions, freeze schemas/ports/enums/artifact names/allowlists, and record redacted access results without blocking Bronze.
- **Owner:** P1 owns contracts; P4 records environment and service preflight; P2 and P3 review their contracts.
- **Dependencies:** Approved answers for every Section 7 decision that changes current product scope; otherwise preserve current approved scope.
- **Entry Gate:** Source priority acknowledged; no unresolved owner conflict; target region/model/provider names identified without secrets.
- **Exit Gate:** Shared models and local protocols are accepted by all owners; fakes satisfy every external port; blocked services have typed fixture/fallback paths.
- **Required outputs:** Redacted service-access record, `AnalysisRequest`/Evidence/Claim/result contracts, run-state enum, `ProgressSink`, source protocols, static `ToolRegistry`, `ArtifactStore`, fixed clock/fakes, and frozen four filenames.
- **Failure fallback:** Record the blocked service and continue to Bronze using only fakes and fixtures; do not redesign topology.
- **Affected files:** `.env.example`, `pyproject.toml`, `docs/rehearsals/service-access-check.md`, `src/hoya_agent/models.py`, `config.py`, `clock.py`, `ports.py`, `tests/fakes.py`, `tests/unit/test_models.py`, `tests/unit/test_config.py`.
- **Can run in parallel:** P4 preflight can run while P1 prepares contracts; contract acceptance is the join gate.

### Task 2: Deliver Bronze End-to-End

- **Objective:** Produce a fully offline Streamlit run from fixture request, Evidence, and `AnalysisResult` through deterministic rendering and the four artifacts.
- **Owner:** P1 owns `ApplicationService` and artifact-writing contract; P3 owns Renderer semantics/fallback; P4 owns Streamlit presentation/downloads; P2 supplies Evidence fixtures.
- **Dependencies:** Task 1.
- **Entry Gate:** Frozen ports and fixture schemas are consumable without network, Bedrock, or AWS.
- **Exit Gate:** A single-asset rehearsal fixture produces parseable `run_config.json`, streaming `execution_log.jsonl`, `evidence.json`, and `final_report.md`; insufficient data also renders honestly.
- **Required outputs:** Fixture request/evidence/result, smallest application flow, deterministic Renderer/lint/fallback, Streamlit fixture view, four download controls, and Bronze integration evidence.
- **Failure fallback:** Bronze is the fallback; preserve the known-good fixture bundle and revert partial UI/integration work to the last passing Bronze tag.
- **Affected files:** `src/hoya_agent/application.py`, `src/hoya_agent/reporting/{renderer.py,lint.py,artifacts.py}`, `src/hoya_agent/ui/`, `streamlit_app.py`, `tests/fixtures/vertical_slice/`, `tests/unit/reporting/`, `tests/integration/test_vertical_slice.py`.
- **Can run in parallel:** P2 fixture preparation, P3 Renderer work, and P4 presenter work can proceed against frozen fakes; P1 alone integrates shared files.

### Task 3: Add In-Process Runtime Controls

- **Objective:** Add explicit state, stage deadlines, bounded `asyncio` fork/join, progress events, cancellation cleanup, partial completion, and append-only execution events.
- **Owner:** P1.
- **Dependencies:** Tasks 1 and 2.
- **Entry Gate:** Bronze artifacts and application boundary are stable.
- **Exit Gate:** Fake-clock and branch-failure cases terminate deterministically, preserve successful branch output, cancel pending work, and finalize honest artifacts.
- **Required outputs:** `DeadlineManager`, run-state/progress contract, fork/join pipeline, deadline-bound retry/repair controls, and failure-event logging.
- **Failure fallback:** Keep the sequential Bronze application path runnable while runtime controls are repaired.
- **Affected files:** `src/hoya_agent/orchestration/{run_state.py,deadline.py,pipeline.py}`, `src/hoya_agent/application.py`, `tests/unit/orchestration/`, `tests/integration/test_fork_join.py`.
- **Can run in parallel:** Can run alongside fixture-based P2/P3 work for Tasks 4–5, but P1 serializes changes to `application.py`.

### Task 4: Add Silver Baseline Data and Bedrock Paths

- **Objective:** Connect Organizer CSV, one approved baseline live market source, one approved baseline research source, and a bounded schema-valid Bedrock path while retaining Bronze.
- **Owner:** P2 owns market/research HTTP adapters, normalization, timeouts, and source degradation. P3 owns Planner, Research Agent orchestration, Bedrock reasoning, structured-output validation, and reasoning fallback. P1 owns integration.
- **Dependencies:** Tasks 1 and 2; live integration also depends on Task 3 deadline contracts.
- **Entry Gate:** Baseline provider decisions are approved; domain/host/tool allowlists are frozen; redacted access results or explicit blocked-service records exist.
- **Exit Gate:** If approved, at least one live single-asset run returns schema-valid Bedrock output from the baseline paths; deterministic Bedrock failure also yields honest degraded artifacts; fallback-only does not satisfy Silver success.
- **Required outputs:** Organizer CSV adapter, baseline market/research adapters, typed `SourceResult`, static tool registry, Bedrock wrapper with operation-specific `max_tokens`, finite research plan, and structured validators.
- **Failure fallback:** Preserve Bronze. A source failure may produce official partial output only when official Evidence remains; a Bedrock failure uses deterministic result/report fallback and cannot masquerade as live AI success.
- **Affected files:** `src/hoya_agent/data/`, `src/hoya_agent/adapters/{organizer_csv.py,binance.py,<approved-research>.py,bedrock.py}`, `src/hoya_agent/reasoning/`, `prompts/`, `tests/contract/`, `tests/fixtures/http/`, `tests/fixtures/llm/`.
- **Can run in parallel:** P2 adapter work and P3 reasoning work are parallel behind frozen protocols; P2 does not edit Bedrock/reasoning files and P3 does not edit low-level research HTTP adapters.

### Task 5: Enforce Evidence and Report Integrity

- **Objective:** Enforce freshness, external-content isolation, exact deduplication, static reliability, independence, Claim-Evidence Links, supporting/counter evidence, material conflict, confidence caps, limitations, and deterministic output lint.
- **Owner:** P2 owns Evidence normalization and policies; P3 owns claim/result validation and Renderer semantics; P1 owns final cross-contract validation.
- **Dependencies:** Tasks 1 and 2; uses Task 4 adapters through fixtures and typed results.
- **Entry Gate:** Evidence and result schemas are frozen; representative success, stale, missing-time, conflict, malicious-instruction, and failure fixtures exist.
- **Exit Gate:** Every rendered fact/conclusion resolves to validated Evidence or explicit insufficient data; external instructions cannot alter policy/tools/URLs; freshness and degradation are disclosed.
- **Required outputs:** Evidence Processor, ledger/policies, deterministic conflict indicators, graph validators, freshness disclosures, prompt-injection resistance tests, report lint, and traceability checks.
- **Failure fallback:** Reject invalid external records or claims, record the gap, cap confidence deterministically, and render partial/insufficient output.
- **Affected files:** `src/hoya_agent/evidence/`, `src/hoya_agent/reasoning/arbiter.py`, `src/hoya_agent/reporting/{renderer.py,lint.py}`, `.kiro/steering/evidence-contracts.md` as read-only contract, `tests/unit/evidence/`, `tests/unit/reasoning/`, `tests/unit/reporting/`.
- **Can run in parallel:** P2 policy tests and P3 claim/Renderer tests can run in parallel; shared model changes route through P1.

### Task 6: Pass Gold Failure and Asset Gates

- **Objective:** Prove independent Market, Research, Bedrock/schema, Renderer/artifact, and deadline degradation plus the approved asset coverage.
- **Owner:** All owners repair their domains; P1 owns the gate.
- **Dependencies:** Tasks 3–5.
- **Entry Gate:** Silver success and fallback gates pass locally; all failure fixtures exist; the asset-scope decision is approved.
- **Exit Gate:** Required failure scenarios end in truthful terminal states with inspectable fixed artifacts; the approved assets complete separate runs; no production infrastructure is introduced.
- **Required outputs:** Acceptance fixtures, failure matrix, artifact contract checks, run-mode honesty checks, approved asset-run records, and rollback tag.
- **Failure fallback:** Revert to the last passing Silver or Bronze tag and record the unresolved Gold blocker; do not weaken evidence honesty or artifact requirements.
- **Affected files:** `tests/acceptance/`, `tests/integration/`, `tests/fixtures/failures/`, `docs/rehearsals/run-log.md`, owner modules only for reproduced defects.
- **Can run in parallel:** Failure cases can be partitioned by owner after the common gate harness is frozen; P1 integrates results.

### Task 7: Containerize and Deploy Gold

- **Objective:** Build one Streamlit image, push an immutable ECR tag, run that exact tag on one EC2 host, and document health and rollback.
- **Owner:** P1 and P4 co-own; P4 never carries deployment risk alone.
- **Dependencies:** Task 6 local Gold Exit; deployment preflight from Task 1.
- **Entry Gate:** Feature Freeze has started; local Gold tag and artifact fallback are preserved; IAM/region/tag/security-group/rollback decisions contain no secrets.
- **Exit Gate:** The built and deployed immutable tags match and the Streamlit/artifact path is smoke-checked, or the documented local-image fallback is selected honestly.
- **Required outputs:** `Dockerfile`, `.dockerignore`, `compose.yaml`, deployment/runbook records, immutable tag mapping, health check, and rollback command.
- **Failure fallback:** Run the same Gold image locally or use the last reachable immutable image; do not add an API gateway, queue, database, worker, or new deployment framework.
- **Affected files:** `Dockerfile`, `.dockerignore`, `compose.yaml`, `scripts/smoke_test.py`, `docs/runbooks/`, `docs/rehearsals/`, README deployment instructions.
- **Can run in parallel:** P4 can prepare runbooks/smoke presentation while P1 handles image/IAM integration; both review the final path.

### Task 8: Freeze, Rehearse, and Verify Submission

- **Objective:** Enforce freeze, run the approved timed rehearsal set, inspect artifacts/secrets/mode labels, and prepare truthful submission evidence.
- **Owner:** All; P4 operates the UI and rehearsal record, P1 signs off.
- **Dependencies:** Task 6 starts the freeze; Task 7 is required for deployed-demo exit.
- **Entry Gate:** Gold local acceptance passes or Day 2 midday arrives, whichever is earlier; no Platinum feature is in progress.
- **Exit Gate:** Approved rehearsal records, four-artifact inspection, secret review, recorded-demo disclosure, deployment/local fallback, and submission backup are complete. Platinum remains outside the two-day task graph.
- **Required outputs:** Timed rehearsal records, artifact checklist, secret-scan record, demo/runbook labels, submission backup, and final task-to-commit traceability.
- **Failure fallback:** Use the last passed layer/image and clearly labelled recorded `demo` bundle; never relabel rehearsal/demo as official.
- **Affected files:** `docs/rehearsals/`, `docs/runbooks/`, `docs/evidence/kiro/README.md`, README submission instructions, artifact inspection records; implementation files only for reproduced defects.
- **Can run in parallel:** Rehearsal/document/secret checks can proceed while Task 7 deployment is completed, but final sign-off waits for both paths.

## 6. Steering Diff Plan

Existing Steering already covers most required policy: `development-workflow.md` defines source-of-truth order and hard gates; `testing.md` is fixture-first and protects deterministic/failure behavior; `tech.md` bans extra orchestration and defines allowlists, operation-specific `max_tokens`, deterministic rendering/fallback, local artifacts, and run-mode honesty; `evidence-contracts.md` is complete; the approved workflow supplies ownership.

Only decision-dependent or task-number-independent clarification should be patched:

| Steering file | Patch need | Minimum plan |
|---|---|---|
| `development-workflow.md` | Required after stage approval | Replace generic Day 2 freeze wording with Gold local acceptance or Day 2 midday, whichever is earlier; add rollback to last passed layer. Keep source priority and ownership links. |
| `competition-rules.md` | Conditional | If CoinGecko or five-asset scope changes are approved, amend only Approved Data Policy/acceptance references. Preserve deadlines, run modes, Evidence, reliability, conflict, artifact, secret, and MVP-exclusion rules. |
| `product.md` | Conditional | If the stage scope is approved, express success as Bronze/Silver/Gold with Platinum separate. Do not weaken Evidence honesty or four artifacts. |
| `tech.md` | Conditional | Change CoinGecko wording only if approved. Existing no-infrastructure, `max_tokens`, allowlist, Bedrock validation, fallback, artifact, and mode rules need no patch. |
| `testing.md` | Conditional | Align asset matrix and rehearsal count only after those decisions. Preserve unit/contract/integration layering, live opt-in, failure injection, and artifact checks. |
| `structure.md` | Conditional | Keep the lean tree. Mark the CoinGecko adapter optional/future only if approved; do not create new packages for compatibility seams. |
| `evidence-contracts.md` | None | No Steering patch required. Preserve all names and invariants. |

If all current approved product-scope decisions remain unchanged, no scope-related Steering patch is required; only the task-number-independent freeze clarification in `development-workflow.md` is recommended after the Kiro Tasks patch.

## 7. Explicit Decision Register

D1–D8 are approved delivery-scope decisions. Approval authorizes only the next minimal Requirements patch and does not mean that any specification or implementation change has been applied.

| Decision | Current Spec | Proposal | Recommended decision | Reason | Approval required | Approval status |
| -------- | ------------ | -------- | -------------------- | ------ | ----------------- | --------------- |
| D1 — CoinGecko | Approved product design §10.1/§20, Requirement 3, Design §8.3/§11, and Task 4 require it as live fallback | Move CoinGecko to Platinum | Defer the CoinGecko live adapter to post-hackathon Future Work; retain only the generic `SourceAdapter` compatibility seam, and do not require CoinGecko for Silver or Gold | Reduces the required provider and failure-path surface while preserving future compatibility | Yes | `Approved` |
| D2 — Five-coin matrix | Approved product design §18.1, Requirement 15, Task 9, Testing Steering, and workflow require BTC/ETH/SOL/BNB/XRP | Move complete matrix to Platinum | Retain the five-asset allowlist, but move the complete five-coin validation matrix and calibration to post-hackathon Future Work | Separates supported assets from the smaller two-day validation commitment | Yes | `Approved` |
| D3 — Two-coin Gold validation | Current formal acceptance is five assets; one-to-two assets is a request compatibility contract, not the Gold coverage gate | Validate at least two assets as separate single-asset Gold runs | Gold requires two different assets validated as separate single-asset runs; additional assets are optional and non-blocking, and dual-asset comparison is not required | Provides cross-asset evidence without a full matrix or comparison feature | Yes | `Approved`, **partially superseded 2026-08-01** |

> **D3 superseding note (2026-08-01).** The Gold asset gate is unchanged: two different
> assets, validated as two separate single-asset runs. What changed is the clause
> "dual-asset comparison is not required" — the product owner has ruled dual-asset
> comparison a **committed capability**, now Requirement 17 and Task 12, scheduled
> after Silver and before Feature Freeze. It is still excluded from the Gold asset
> gate and still must not delay Gold local Exit, deployment, the timed rehearsal, or
> submission, and the two Gold single-asset runs may not be substituted for it (nor
> it for them). Requirements, Design, Tasks, and Steering have been patched
> accordingly; this register row is kept for traceability rather than rewritten.
| D4 — Three rehearsals | Approved product design §18.1, Requirement 15, Task 9, Testing Steering, and workflow require three live-source rehearsals | Reduce to at least one timed rehearsal | Require one complete timed judged-flow rehearsal for Gold; additional rehearsals are optional and must not delay deployment or submission | Preserves one complete timing proof while protecting delivery time | Yes | `Approved` |
| D5 — Platinum timing | Approved design allows H3 evaluation after core by Day 2 morning; optional Tasks may start after required gates | Make Platinum wholly post-freeze and post-hackathon/out-of-band | Platinum is post-hackathon Future Work only and must not be implemented during the formal two-day delivery period | Removes optional feature work from the frozen competition path | Yes | `Approved` |
| D6 — Silver baseline source wording | Current specs name several providers and a three-type/group quality target; they do not impose an exactly-one cap | Require one baseline live market and one baseline research source; optional sources are non-blocking | Silver requires one designated baseline live market source and one designated baseline research source; additional sources are optional, non-blocking, and not subject to an exactly-one maximum | Defines a stable minimum without rejecting useful optional Evidence | Yes | `Approved` |
| D7 — Bedrock success gate | Structured validation and fake/contract tests exist; no explicit Silver live schema-valid success gate is named | Require at least one schema-valid Bedrock result; fallback-only is insufficient | Silver requires at least one successful schema-valid Bedrock result using the baseline live market and research paths; deterministic fallback must also be tested, and fallback-only execution does not satisfy Silver | Proves both the intended live reasoning path and its degradation path | Yes | `Approved` |
| D8 — Feature Freeze trigger | Approved workflow uses Task 9 pass or Day 2 midday; Tasks use generic Day 2 afternoon wording | Use Gold local Exit or Day 2 midday, whichever is earlier | Feature Freeze begins at Gold local Exit or Day 2 midday, whichever occurs first; after freeze only fixes, deployment, rehearsal, documentation, rollback, and submission verification are allowed | Replaces task-number coupling with a stable delivery gate | Yes | `Approved` |
| Renderer and artifact ownership | Approved product/workflow assign Renderer semantics to P3, shared artifact contracts/writer to P1, and UI/download/deployment support to P4 | Proposal preserves that split; requested shorthand could be read as assigning Renderer/artifacts to P4 | Preserve approved ownership: P4 owns presentation and downloads, not Renderer semantics or artifact persistence contracts | Prevents P1/P3/P4 file collisions and follows higher-priority sources | No | `Not required` |

There are **8 approved approval-required decisions** and **0 unresolved decisions**. The ownership row requires no approval because it is resolved by source priority.

## 8. Traceability Map

Future Production Architecture is intentionally absent from the Task impact column.

| Proposal capability | Requirement impact | Design impact | Task impact | Owner |
| ------------------- | ------------------ | ------------- | ----------- | ----- |
| Bronze offline fixtures | Add staged preface; preserve Requirements 9–12 | Annotate §§2–3 and §18; no topology change | Task 2 | P1/P3/P4, P2 fixtures |
| Bronze deterministic Renderer | Preserve Requirements 7, 9, 11 | Preserve §§9, 11–12 | Tasks 2 and 5 | P3 semantics; P1 integration |
| Bronze four artifacts | Preserve Requirement 10 | Preserve §12 | Tasks 1–2 | P1 writer; P4 downloads |
| Silver baseline live market source | Clarify Requirement 3 after decision | Amend §8 provider priority | Task 4 | P2 |
| Silver baseline research source | Clarify Requirement 4 after decision | Amend §§8.4–8.7 | Task 4 | P2 adapter; P3 orchestration |
| Silver schema-valid Bedrock success | Amend Requirement 7 after decision | Clarify §§4.3, 9, and 16 | Tasks 1 and 4 | P3; P1 gate |
| Gold two separate assets | Amend Requirement 15 after decision | Amend §§16 and 18 | Task 6 | All; P1 gate |
| Gold failure degradation | Preserve Requirements 9 and 15 | Preserve §§6 and 11 | Tasks 3, 5, and 6 | All by domain |
| Gold Docker/ECR/EC2 | Preserve Requirement 15 | Preserve §15 | Task 7 | P1 + P4 |
| Gold timed rehearsal | Amend Requirement 15 after decision | Amend §§16.4 and 18 | Task 8 | P4 operator; P1 sign-off |
| Platinum post-freeze | Clarify Requirements 14–15 after decision | Clarify §§10 and 18 | No two-day Task | Product owner |
| Gold-or-midday Feature Freeze | Add staged preface/Scope Guard after decision | Add to §18 | Tasks 7–8 entry gates | P1 |
| Internal run state | Preserve Requirements 1, 8, 9 | Preserve §§5–6 | Tasks 1 and 3 | P1 |
| Per-stage deadlines | Preserve Requirement 8 | Preserve §6 | Task 3 | P1 |
| Operation-specific `max_tokens` | Preserve/amend Requirement 7 | Preserve §§4.3 and 14 | Tasks 1 and 4 | P3 |
| Finite allowlisted tool plan | Add bounded-tool Requirement | Clarify §§4.3, 8, and 14 | Tasks 1 and 4 | P1/P2/P3 |
| Tool/domain/host allowlist | Add/clarify Requirements 3, 4, and 7 | Clarify §§8 and 14 | Tasks 1 and 4 | P1 config; P2 adapters |
| External content isolation | Add safety Requirement | Add normalization boundary to §§3, 8, and 9 | Tasks 4 and 5 | P2/P3 |
| Prompt-injection resistance | Add safety acceptance | Add malicious-instruction test design in §16 | Task 5 | P2/P3 |
| Partial completion | Preserve Requirement 9 | Preserve §§6 and 11 | Tasks 3 and 6 | P1 + domain owner |
| Deterministic fallback | Preserve Requirements 7, 9, and 11 | Preserve §§9, 11, and 12 | Tasks 2, 4, 5, and 6 | P3 semantics; P1 flow |
| Run-mode honesty | Preserve Requirements 2 and 12 | Preserve §7 and UI badges | Tasks 2, 6, and 8 | P1/P4 |
| Claim-Evidence Links | Preserve Requirements 5–6 | Preserve §§5 and 9 | Task 5 | P2/P3 |
| Supporting and counter evidence | Preserve Requirement 6 | Preserve §9 and conflict presentation | Task 5 | P2/P3 |
| `fetched_at` and published/source time | Clarify Requirements 2 and 5 | Clarify §§7–9 | Tasks 4 and 5 | P2 |
| Cache/stale metadata | Preserve Requirements 2 and 5 | Preserve §§7–9 | Tasks 4 and 5 | P2 |
| Immutable `analysis_as_of` | Preserve Requirements 1–2 | Preserve §§3 and 7 | Tasks 1, 4, and 5 | P1/P2 |
| Categorical `high / medium / low` reliability | Preserve Requirements 5–6 and 11 | Preserve §§5 and 9 | Task 5 | P2 policy |
| Deterministic material conflict | Preserve Requirement 6 | Preserve §§9–10 | Task 5 | P2 indicator; P3 presentation |
| Limitations/degradation disclosure | Preserve Requirements 6, 9, and 11 | Preserve §§9 and 11 | Tasks 5–6 | P2/P3 |
| `run_id` compatibility seam | Preserve Requirement 1 | Clarify §§4–5 | Tasks 1–3 | P1 |
| Progress contract | Preserve Requirement 12 | Clarify §§4.1 and 13 | Tasks 1–3 | P1; P4 consumes |
| Typed `SourceAdapter` | Clarify Requirements 3–4 | Document existing specialized protocols in §4.3 | Tasks 1 and 4 | P1 contract; P2 implementation |
| Static `ToolRegistry` | Add bounded-tool Requirement | Add local static abstraction to §§4.3/14 | Tasks 1 and 4 | P1/P2/P3 |
| Local `ArtifactStore` | Preserve Requirement 10 | Clarify §12 local implementation | Tasks 1–2 | P1 |
| Future persistence port | No behavior Requirement; Scope Guard says no persistence now | Model a local/no-op seam only in §4 | Task 1 contract only | P1 |
| Cancellation-compatible terminal state | Preserve Requirements 8–9 | Preserve §6 | Tasks 1 and 3 | P1 |
| Same-process async boundary | Preserve Requirement 12 | Preserve §§2, 4.1, 13, and 15 | Tasks 2–3 | P1; P4 UI |
| P2/P3 Research boundary | Clarify ownership notes only | Preserve module boundaries §§4 and 8–9 | Tasks 4–5 | P2 HTTP; P3 reasoning |

## 9. Recommended Patch Order

### 1. Requirements

- **Why first:** Requirements determine which Proposal adjustments are authorized acceptance changes and which remain proposals. Design and Tasks cannot safely narrow current product scope first.
- **After-patch checks:** Verify all approved decisions are reflected once; unchanged Evidence enums/fields, run modes, four filenames, deterministic policies, and deployment requirements remain intact; every conditional decision has an approval reference.
- **Must not change:** Do not add production infrastructure, numeric reliability, PDF/HTML MVP output, unbounded tools, or claims that live services have passed.

### 2. Design

- **Why second:** Design must implement the approved Requirement meaning through the existing H2-Lite topology before Tasks are renumbered.
- **After-patch checks:** Verify stage mapping, external-content isolation, freshness, Bedrock success/fallback distinction, local compatibility seams, and provider optionality match Requirements; compare all diagrams and interfaces for accidental topology change.
- **Must not change:** Do not redraw the system as services, add a Job API, or add Database, Queue, broker, independent worker, polling, SSE, WebSocket, DLQ, or authentication service.

### 3. Tasks

- **Why third:** Only stable Requirement and Design gates can produce a dependency-safe eight-Task execution graph.
- **After-patch checks:** Count no more than eight top-level Tasks; Bronze blocks live integration; each Task has owner/dependencies/entry/exit/outputs/fallback/files/parallelism; P2/P3 boundaries and P1-only shared integration are explicit; no cycles exist.
- **Must not change:** Do not delete focused deterministic/failure tests, introduce shared-file multi-owner edits, start Platinum, or claim any command/service has passed.

### 4. Steering only if necessary

- **Why fourth:** Steering should change only where an approved Requirement/Design/Task decision makes an always-included rule stale.
- **After-patch checks:** Verify source priority, fixture-first execution, deterministic Renderer, no-production-infrastructure rule, run-mode honesty, freeze trigger, and ownership agree. Confirm `evidence-contracts.md` remains unchanged unless an independently approved contract issue appears.
- **Must not change:** Do not duplicate full Requirements/Design text or change canonical Evidence names/enums for convenience.

### 5. Final consistency review

- **Why last:** Cross-file review detects gate drift and proposal language accidentally presented as approved behavior.
- **After-patch checks:** Trace every approved Must capability from Requirement to Design to Task/owner; search for old Task numbers, five-asset/three-rehearsal/CoinGecko wording, exactly-one wording, H3 timing, four filenames, reliability enum, and forbidden production components. Verify Git diff scope before any implementation starts.
- **Must not change:** Review is read-only; it cannot resolve missing approvals or silently edit higher-priority product/workflow documents.

## 10. Readiness Checklist

| Check | Result | Basis |
|---|---|---|
| Requirements patch scope is clear | Yes | D1–D8 approve the target scope for the next minimal Requirements patch; Requirements have not yet been modified. |
| Design patch scope is clear | Yes | Existing architecture is retained; only labels, isolation, freshness, seams, and approved provider/gate wording change. |
| Tasks patch scope is clear | Yes | D1–D8 define the future Gold/Silver acceptance contents, but Tasks have not yet been modified. |
| Unresolved Product decisions remain | No | D1–D8 are recorded as `Approved`; the ownership row is `Not required`. |
| Proposal conflicts with Kiro/approved Specs | Resolved for patch planning | D1–D8 resolve the intended direction; current Specs remain unchanged until reviewed patches are applied. |
| Production infrastructure could be added accidentally | Controlled risk | Explicit exclusions exist in Requirements/Design plan and no implementation Task maps future architecture. |
| Ownership is clear | Yes | Higher-priority approved split is preserved; P2 HTTP and P3 Bedrock/reasoning do not overlap. |
| Feature Freeze is consistent | Yes for patch planning | D8 approves the trigger and D1–D7 define the intended Gold Exit scope; current workflow has not yet been modified. |
| Traceability is complete | Yes for planned scope | Every Must-level Proposal capability has a Requirement, Design, Task, and owner mapping or an explicit no-two-day-Task disposition. |

### Approval record

- D1–D8: `Approved`.
- Unresolved Product decisions: `0`.
- Requirements, Design, Tasks, Steering, implementation, tests, Docker, and AWS configuration remain unmodified by this approval record.

**Final Decision: `READY_TO_PATCH_REQUIREMENTS`**

Approval of D1–D8 authorizes only the next minimal Requirements patch. It does not imply that any specification, implementation, test, Bedrock path, deployment, or rehearsal has been completed.
