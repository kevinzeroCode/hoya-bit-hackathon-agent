# Codebase Information

## 2026-08-02 S10 Gold local Exit

Offline Gold acceptance coverage now lives in `tests/acceptance/`, with the
reproducible runner `scripts/run_acceptance.py`. The local gate runs BTC and ETH as
separate single-asset rehearsal requests through `OrganizerCsvPipeline`, checks fixed
artifacts and provenance, and records deterministic degradation in
`docs/rehearsals/run-log.md`. S11 deployment and timed rehearsal remain open.

## Project Identity

- **Name:** HOYA BIT Hackathon AI Agent (`hoya-agent`)
- **Language:** Python 3.12
- **Purpose:** Evidence-first crypto market analysis agent for a two-day hackathon competition
- **Report Language:** Traditional Chinese (繁體中文)
- **Architecture:** H2-Lite bounded workflow (single pass, no debate loops)
- **Status:** Core pipeline + deterministic calc library + analysis skills live; Streamlit Bronze UI (S3) and live Silver pipeline (real-time Binance + Fear & Greed → Bedrock Arbiter) implemented; Docker → ECR → EC2 deployment documented (`docs/deploy-ec2.md`); H3 debate still a disabled stub; `acceptance/` tests not yet created

## Technology Stack

| Area | Choice |
|---|---|
| Language | Python 3.12 with type hints |
| Validation | Pydantic v2 (`extra="forbid"` on all models) |
| Async | stdlib `asyncio` |
| HTTP | `httpx.AsyncClient` |
| Tabular | `pandas` (deterministic indicators only) |
| AWS SDK | `boto3` (Bedrock Runtime Converse API) |
| LLM | Amazon Bedrock (primary + optional fallback model) |
| UI | Streamlit (Bronze UI implemented in `src/hoya_agent/ui/`) |
| Tests | pytest, pytest-asyncio |
| Linting | ruff (py312, line-length=120) |
| Build | hatchling, `src/` layout |
| Deploy | Docker → ECR → single EC2 instance |

## Supported Assets

`BTC`, `ETH`, `SOL`, `BNB`, `XRP` — coin-agnostic pipeline, no per-coin branching.

## Competition Constraints

- **Team:** 4 junior developers, 2-day build
- **Hard deadline:** 900 seconds per run (15 minutes)
- **Internal deadlines:** 720s analysis stop, 780s artifact completion
- **Required artifacts:** `final_report.md`, `evidence.json`, `execution_log.jsonl`, `run_config.json`
- **Run modes:** `official` (live only), `rehearsal` (fixtures), `demo` (recorded fallback)

## Project Layout

```
hoya-bit-hackathon-agent/
├── src/hoya_agent/          # Production source code (canonical contracts + orchestration)
│   ├── models.py            # 43 Pydantic classes/enums (13 enums + 30 models, 1724 LOC)
│   ├── config.py            # Typed Settings from environment variables
│   ├── clock.py             # SystemClock + build_run_context helper
│   ├── ports.py             # All Protocol interfaces (adapters, LLM, workers, clock)
│   ├── application.py       # ApplicationService entry point (run identity, artifact order)
│   ├── composition.py       # Composition root: wires Bedrock + live sources into the pipeline
│   ├── adapters/            # External I/O (flat, one file per provider)
│   │   ├── bedrock.py       # AWS Bedrock Converse — structured output via tool use (FROZEN)
│   │   ├── binance.py       # Daily UTC klines → MarketBar
│   │   ├── cryptopanic.py   # News aggregation (low reliability)
│   │   ├── organizer_csv.py # Competition OHLCV benchmark data
│   │   ├── alternative_me.py# Fear & Greed (low, market-wide, asset=None)
│   │   ├── rss.py           # Original publisher feeds (medium reliability)
│   │   ├── official.py      # Official project announcement feeds (best-effort, high)
│   │   ├── live_sources.py  # Live Binance + Fear & Greed factories for the Silver pipeline
│   │   ├── _assets.py       # Asset symbol utilities
│   │   ├── _errors.py       # Normalized timeout/http_error/malformed/rejected categories
│   │   └── port_adapters.py # Port-conforming async wrappers (CSV, Binance, RSS, CryptoPanic,
│   │                       # Fear & Greed, official)
│   ├── data/                # Deterministic market indicators & series
│   │   ├── indicators.py, market_worker.py, market_series.py, price_analysis.py, regime.py
│   │   ├── text_clean.py    # News text normalization for research extraction
│   │   └── types.py         # MarketBar + shared data-layer types
│   ├── evidence/            # Ledger, policies, processor, trust, grounding, triangulation
│   ├── reasoning/           # Planner, ResearchAgent, Arbiter, mapping, schemas (FROZEN package)
│   │   ├── mapping.py       # ArbiterGeneration → strict AnalysisResult (returns None on failure)
│   │   └── schemas.py       # Lax LLM-boundary generation schemas (GenClaim, ArbiterGeneration, …)
│   ├── reporting/           # Deterministic renderer, advice_lint, atomic artifact store
│   ├── orchestration/       # DeadlineAwarePipeline, deadline, run_state
│   └── ui/                  # Streamlit Bronze UI
│       ├── streamlit_app.py # Judge-facing offline runner (no live HTTP, no Bedrock)
│       └── presenter.py     # Framework-free RunSummary → view-model mappings
├── src/calc/                # Deterministic calc library (no LLM, no network)
│   ├── indicators.py, percentile.py, cross_asset.py, analogs.py, data_quality.py
├── src/skills/              # Analysis skills a1–a9 + report/lint/html_report
│   ├── base.py, dataset.py, a1_regime, a2_position, a3_risk, a4_participation,
│   ├── a5_attribution, a7_analogs, a9_verification, report.py, lint.py, html_report.py
├── prompts/                 # Versioned LLM prompt markdown files (FROZEN)
├── tests/                   # Layered test suite
│   ├── conftest.py          # Minimal sys.path bootstrap
│   ├── fakes.py             # Shared test fakes (FixedClock, FakeLLM, FakeSourceAdapter, etc.)
│   ├── unit/                # Schema, policy, indicator, renderer, skills, ui, calc tests
│   ├── contract/            # Mocked adapter/Bedrock interaction tests
│   ├── integration/         # Module collaboration & degradation paths
│   ├── live/                # Opt-in live network/Bedrock tests (RUN_LIVE_TESTS=1)
│   └── fixtures/            # Immutable test data (JSON, CSV, vertical_slice)
├── HOYA_BIT_crypto_market_dataset/  # Competition OHLCV CSV data
├── docs/                    # Design docs, specs, playbooks, deploy-ec2.md
├── .kiro/                   # Kiro steering & spec files
└── pyproject.toml           # Project configuration (hatchling, src/ layout)
```

## Key Metrics

| Metric | Value |
|---|---|
| Python files under `src/` (excl. `__pycache__`) | 75 (56 in `hoya_agent/` incl. `ui/`, 6 in `calc/`, 13 in `skills/`) |
| Test files under `tests/` (excl. `__pycache__`) | ~87 across unit / contract / integration / live / fixtures |
| Core models (`models.py`) | 43 classes/enums (13 enums + 30 Pydantic models), 1724 LOC |
| Adapter files (`adapters/`, excl. `__init__.py`) | 11 (bedrock, binance, cryptopanic, organizer_csv, alternative_me, rss, official, live_sources, _assets, _errors, port_adapters) |
| Prompt files | 3 versioned (planner-v1, research-extraction-v1, arbiter-v1) |
| Test layers | 5 declared (unit, contract, integration, acceptance, live) — `live/` exists; `acceptance/` not yet created |

## Run Modes

| Mode | Sources | Fixtures | Disclosure |
|---|---|---|---|
| `official` | Live APIs + organizer CSV | Forbidden | Cutoff frozen to current UTC |
| `rehearsal` | Deterministic fixtures | Expected | Labeled in all artifacts |
| `demo` | Recorded fallback on failure | Labeled | Shows capture time |

## Key Design Decisions

1. **Evidence-first:** Every factual claim must trace to a validated `EvidenceItem`; LLM output is never evidence
2. **Deterministic fallback:** All LLM stages produce usable results without the model via static defaults
3. **Single LLM call per stage:** Planner, ResearchAgent, Arbiter each get exactly one generation attempt
4. **Static reliability:** Source reliability assigned by deterministic policy table, never by LLM
5. **Coin-agnostic:** All pipeline stages take `asset` as parameter; no per-coin special cases
6. **Degradation-first errors:** Adapter/service failures produce partial results with disclosure, never crash
7. **Atomic artifacts:** All file writes use tmp+rename pattern; partial runs still produce valid artifacts

## 2026-08-01 S8/S9/S9B additions

New canonical modules: `orchestration/deadline.py`, `orchestration/run_state.py`, `evidence/trust.py`, and the offline acceptance script. `_provisional_seams.py` has been removed; the composition root now lives in `composition.py` and wires canonical `models`/`ports` into the live Silver pipeline. See `s8-s9-s9b.md`.

## Live Silver pipeline & UI (post-S8)

- **Composition root:** `composition.py` — `build_live_pipeline(...)` assembles real-time Binance klines + Alternative.me Fear & Greed evidence (no key) and runs the frozen Arbiter over it via `MappingArbiter` (which degrades to the deterministic insufficient-data report on any mapping failure).
- **Live sources:** `adapters/live_sources.py` — `binance_bar_loader` and `fear_greed_drafts` factories; sync callables bridged from async `httpx.AsyncClient` via a one-shot worker-thread loop.
- **Reasoning mapping:** `reasoning/mapping.py` + `reasoning/schemas.py` — lax LLM-boundary `ArbiterGeneration` projected onto the strict `AnalysisResult` contract (FROZEN package — documented only).
- **Bronze UI:** `ui/streamlit_app.py` (judge-facing, offline-only via `OrganizerCsvPipeline`) + `ui/presenter.py` (framework-free view-model mappings).
- **Deterministic calc library:** `src/calc/` (indicators, percentile, cross_asset, analogs, data_quality) — no LLM, no network.
- **Analysis skills:** `src/skills/` (a1_regime, a2_position, a3_risk, a4_participation, a5_attribution, a7_analogs, a9_verification, base, dataset, report, lint, html_report).
