# Repository Structure Steering

## Canonical Tree

```text
src/hoya_agent/
  models.py                 # shared Pydantic contracts only
  config.py                 # typed settings and sanitized snapshots
  clock.py                  # injectable UTC/monotonic clock
  ports.py                  # shared Protocol interfaces
  application.py            # single use-case entry point and composition
  orchestration/            # deadline, run state, pipeline
  data/                     # market series, indicators, Market Worker
  adapters/                 # flat external I/O modules
  evidence/                 # ledger, policies, processor
  reasoning/                # planner, research extraction, arbiter, H3 stub
  reporting/                # deterministic renderer, artifacts, lint
  ui/presenter.py           # domain-to-Streamlit view models only
prompts/                    # versioned Planner/Research/Arbiter Markdown
streamlit_app.py            # UI entry; imports ApplicationService/presenter
tests/
  unit/
  contract/
  integration/
  acceptance/
  live/
  fixtures/
```

The exact files are those listed in the Kiro design. Keep `adapters/` flat for the two-day MVP. Do not add `llm/` or `observability/` packages.

## Dependency Direction

```text
streamlit_app -> ui.presenter + application -> orchestration
orchestration -> data + evidence + reasoning + reporting
core modules -> ports -> adapter implementations
all project modules -> models
```

- `models.py` imports no project module.
- `clock.py` owns UTC/monotonic access so deadline tests need no real sleeps.
- `ports.py` holds `Protocol` boundaries for adapters, LLM, workers, progress, and clock; it has no concrete I/O.
- `config.py` may import models, never adapters or UI.
- `application.py` composes concrete dependencies and invokes the pipeline; provider parsing stays in adapters.
- `orchestration/` coordinates stages/failures but does not calculate indicators, assign reliability, or render Markdown.
- `data/`, `evidence/`, and `reporting/` are deterministic and never call Bedrock.
- Only flat `adapters/*.py` modules import `httpx` or `boto3`.
- `reasoning/` consumes `LLMClient` and evidence IDs; it never writes artifacts.
- `ui/presenter.py` creates display models. `streamlit_app.py` must not import concrete adapters or pipeline stages.

## File Ownership

- Shared schemas: `models.py`.
- Settings and locked env names: `config.py` (`BEDROCK_PRIMARY_MODEL_ID`, `BEDROCK_FALLBACK_MODEL_ID`, `CRYPTOPANIC_API_TOKEN`).
- Time injection: `clock.py`; shared interfaces: `ports.py`.
- Stage order: `orchestration/pipeline.py`; deadline math: `orchestration/deadline.py`; progress/state: `orchestration/run_state.py`.
- Formulas: `data/indicators.py`; source cutover: `data/market_series.py`; deterministic branch assembly: `data/market_worker.py`.
- One provider per flat adapter file: `organizer_csv.py`, `binance.py`, `coingecko.py`, `cryptopanic.py`, `rss.py`, `official.py`, `alternative_me.py`, `bedrock.py`.
- Evidence reliability, independence, dedup, confidence caps: `evidence/policies.py`; processing: `processor.py`; ledger operations: `ledger.py`.
- Planner, bounded extraction, Arbiter, and disabled H3 interface stay in their named `reasoning/` files.
- Versioned prompt bodies stay in root `prompts/*-v1.md`; Python files load them and record version/checksum.
- Fixed artifact names/atomic writes: `reporting/artifacts.py`; Markdown: `renderer.py`; recommendation lint: `lint.py`.

## Test Placement

- `unit/`: schemas, policies, formulas, clock/deadlines, renderer.
- `contract/`: mocked HTTP/Bedrock shapes and error mapping.
- `integration/`: module collaboration and degradation paths.
- `acceptance/`: rehearsal end-to-end requirements and four-artifact validation.
- `live/`: manually invoked provider smoke tests, excluded from default CI.
- `fixtures/`: immutable CSV/API/LLM inputs; production code must never import them.

Tests mirror production names. Reusable inputs belong in `tests/fixtures/`, not a hidden module-specific folder.

## Change Discipline

- Add no package for a single helper; keep the lean tree through competition delivery.
- H3 is only `reasoning/conflict_extension.py` with a disabled implementation. Do not create Bull/Bear/Judge files.
- Do not duplicate shared models or put business rules in UI/adapters.
- Generated run data belongs under ignored `artifacts/`.
- Competition PDFs/ZIPs, `.env`, logs, caches, credentials, and generated artifacts must not be committed.
