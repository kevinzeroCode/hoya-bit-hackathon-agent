# Codebase Information

## Project Identity

- **Name:** HOYA BIT Hackathon AI Agent (`hoya-agent`)
- **Language:** Python 3.12
- **Purpose:** Evidence-first crypto market analysis agent for a two-day hackathon competition
- **Report Language:** Traditional Chinese (繁體中文)
- **Architecture:** H2-Lite bounded workflow (single pass, no debate loops)
- **Status:** Core implementation in progress; H3 debate, Streamlit UI, deployment not yet started

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
| UI | Streamlit (not yet implemented) |
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
├── src/hoya_agent/          # Production source code
│   ├── models.py            # 29 Pydantic domain models (canonical contracts)
│   ├── application.py       # ApplicationService entry point
│   ├── _provisional_seams.py# Temporary runtime type stubs (pre-Task 1b)
│   ├── adapters/            # External I/O (flat, one file per provider)
│   ├── data/                # Deterministic market indicators & series
│   ├── evidence/            # Ledger, policies, processor
│   ├── reasoning/           # Planner, ResearchAgent, Arbiter, H3 stub
│   ├── reporting/           # Deterministic renderer, atomic artifact store
│   └── orchestration/       # Pipeline coordination
├── prompts/                 # Versioned LLM prompt markdown files
├── tests/                   # Layered test suite
│   ├── unit/                # Schema, policy, indicator, renderer tests
│   ├── contract/            # Mocked adapter/Bedrock interaction tests
│   ├── integration/         # Module collaboration & degradation paths
│   ├── acceptance/          # End-to-end requirement validation
│   ├── live/                # Manual opt-in live API tests
│   └── fixtures/            # Immutable test data (JSON, CSV)
├── p2-etl-mvp/             # Parallel prototype (will be superseded)
├── HOYA_BIT_crypto_market_dataset/  # Competition OHLCV CSV data
├── docs/                    # Design docs, specs, playbooks
├── .kiro/                   # Kiro steering & spec files
└── pyproject.toml           # Project configuration
```

## Key Metrics

| Metric | Value |
|---|---|
| Total files | ~627 |
| Core source files | ~40 |
| Test files | ~50 |
| Core models (models.py) | 29 classes/enums |
| Adapter count | 7 (bedrock, binance, cryptopanic, organizer_csv, alternative_me, rss, _assets) |
| Prompt files | 3 versioned (planner-v1, research-extraction-v1, arbiter-v1) |
| Test layers | 5 (unit, contract, integration, acceptance, live) |

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
