# HOYA Market Agent Four-Person Team Workflow

> Status: approved on 2026-07-17
>
> Operator guide: [Kiro Team Playbook](../../kiro-team-playbook.md)

## 1. Decision

Use component ownership with mandatory review and pairing at integration boundaries. Three engineers own the core pipeline domains. P4 owns UI and demo support, while P1 co-owns deployment so no less-experienced member becomes a critical-path single point of failure.

Do not divide work into four independent end-to-end implementations. Shared contracts are frozen first, and all parallel work integrates through `models.py`, `ports.py`, and `ApplicationService`.

## 2. Roles

| Role | Primary responsibility | Kiro tasks | Critical ownership |
|---|---|---|---|
| P1 Integration / Release | Contracts, orchestration, deadline, artifacts, integration, releases | 1, 2, 3, 8; gate owner for 9 | Shared schemas, ports, application service, pipeline |
| P2 Data / Evidence | OHLCV, indicators, live market adapters, research adapters, Evidence Processor | 4, 5 | Deterministic market and evidence modules |
| P3 Reasoning / Report | Bedrock, Planner, Research Agent, Arbiter, prompts, report semantics | 2, 6 | Bounded LLM behavior and validated `AnalysisResult` |
| P4 UI / Demo Support | Streamlit, presenter, fixtures, runbooks, rehearsal records, demo materials | 0, 7; co-lead 10 | UI and repeatable demo operation |
| P1 + P4 | Docker, ECR, EC2, health checks, rollback runbook | 10 | Deployment and recovery |
| All | Five-coin acceptance, failure drills, three rehearsals | 9, 10 | Final competition readiness |

P1 should be the strongest integrator and final technical decision maker. P4 is suitable for a member who benefits from more structured tasks because the role works behind stable interfaces and never owns AWS or core contracts alone.

## 3. File Ownership

### P1

- `src/hoya_agent/models.py`
- `src/hoya_agent/config.py`
- `src/hoya_agent/clock.py`
- `src/hoya_agent/ports.py`
- `src/hoya_agent/application.py`
- `src/hoya_agent/orchestration/`
- `src/hoya_agent/reporting/artifacts.py`
- integration tests spanning multiple owners

### P2

- `src/hoya_agent/data/`
- market and research HTTP adapters except `bedrock.py`
- `src/hoya_agent/evidence/`
- matching unit, contract, and HTTP fixtures

### P3

- `src/hoya_agent/adapters/bedrock.py`
- `src/hoya_agent/reasoning/`
- `prompts/`
- `src/hoya_agent/reporting/renderer.py`
- `src/hoya_agent/reporting/lint.py`
- matching reasoning and Bedrock tests

### P4

- `src/hoya_agent/ui/`
- `streamlit_app.py`
- `Dockerfile`, `.dockerignore`, and `compose.yaml`, reviewed by P1
- UI tests and presentation fixtures
- `docs/rehearsals/`, demo runbook, screenshots, and presentation evidence

Only P1 merges changes to shared contracts. P2, P3, and P4 propose contract changes in their task branch and wait for P1 plus every affected owner to approve them.

## 4. Git Workflow

1. Start every numbered Kiro task from current `main` using `task/<number>-<short-name>`.
2. Keep one numbered task per branch and one primary owner per branch.
3. Stage explicit paths; never use `git add .` from the parent `AWS` directory.
4. Run the focused test suite before requesting review.
5. Update the matching checkbox in `.kiro/specs/hoya-market-agent/tasks.md` in the implementation commit.
6. P1 reviews interface compatibility and merges after required checks pass.
7. Rebase or merge current `main` before integration; do not resolve contract conflicts by silently choosing one side.

Recommended initial branches:

```text
task/0-service-preflight
task/1-shared-contracts
task/2-fixture-vertical-slice
task/3-deadline-pipeline
task/4-market-data
task/5-research-evidence
task/6-bedrock-reasoning
task/7-streamlit-shell
```

Do not run Kiro `Run all Tasks`. Each owner opens the existing `hoya-market-agent` spec and runs only the assigned dependency-safe task.

## 5. Two-Day Execution

| Checkpoint | P1 | P2 | P3 | P4 | Exit gate |
|---|---|---|---|---|---|
| T+0 to T+45 min | Freeze schemas and ports | Review data contracts | Review LLM contracts | Service preflight | Shared contracts accepted |
| T+45 to T+135 min | Fixture application path | Prepare representative fixtures | Fixture `AnalysisResult` and report | Verify UI-facing result shape | Four artifact files produced |
| Day 1 parallel block | Deadline pipeline | Tasks 4 then 5 | Task 6 | Task 7 | Owner tests green |
| End of Day 1 | Integrate Task 8 | Repair owned module | Repair owned module | Exercise UI | First complete H2-Lite fixture run |
| Day 2 morning | Own acceptance gate | Five-coin/data failures | Arbiter/schema failures | UI and download failures | Task 9 passes |
| Day 2 feature freeze | Co-own deployment | Fix only | Fix only | Co-own deployment/runbook | Reachable EC2 demo |
| Final block | Lead judged-flow rehearsal | Observe data gaps | Observe reasoning gaps | Operate UI and record steps | Three timed rehearsals |

Feature freeze begins after Task 9 passes or at Day 2 midday, whichever comes first. After freeze, only fixes, deployment, rehearsal, documentation, and submission verification are allowed.

## 6. Handoff Contracts

- P1 publishes Pydantic models, protocols, fake clock, fake adapters, and fake progress sink before parallel work starts.
- P2 returns validated domain models and never writes reports or invokes Bedrock.
- P3 receives evidence IDs and normalized facts, and never fetches provider data or writes artifacts directly.
- P4 calls only `ApplicationService` and presenter interfaces. UI code never imports concrete adapters or pipeline stages.
- P4 begins against fakes. Live integration happens only after Task 8 is green.
- AWS credentials stay with the deployment operator and EC2 role; P4 does not need access keys in source files.

## 7. Coordination Rules

- Hold a five-minute sync at every checkpoint, not continuous group debugging.
- A member blocked for 20 minutes asks the relevant owner for pairing.
- A contract change requires P1 and every affected owner; otherwise the frozen contract wins.
- P1 may stop optional or UI-polish work whenever the artifact deadline, integration, or deployment is at risk.
- Drop work in this order: H3, optional AWS sinks, optional adapters, UI polish. Never drop deterministic fallback or the four artifacts.

## 8. Definition of Done

A task is complete only when its focused tests pass, its files stay within the declared ownership boundary, no secret is committed, the Kiro checkbox is updated, and another member can consume the output through the frozen interface.

The team is demo-ready only when the fixture run, degraded run, live-source rehearsal, EC2 deployment, four downloads, and recorded fallback disclosure have all been exercised by someone other than the feature author.
