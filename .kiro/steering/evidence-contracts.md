---
inclusion: always
---

# Evidence and Reasoning Contracts

This document is normative. Python models, prompts, adapters, fixtures, artifacts, and tests must use these field names and invariants.

## 1. Common Types

- `Asset`: `BTC | ETH | SOL | BNB | XRP`.
- `RunMode`: `official | rehearsal | demo`.
- `SourceType`: `official | market | news | onchain | social | macro`.
- `Reliability`: `high | medium | low`.
- `Stance`: `supports | opposes | neutral`.
- `ClaimType`: `fact | inference | conclusion`.
- All persisted timestamps are ISO 8601 UTC strings ending in `Z`.
- `analysis_as_of` is immutable during a run; evidence published after it is rejected.
- IDs are run-local, deterministic after sorting, and formatted as `ev_001`, `cl_001`, and `run_YYYYMMDD_HHMMSS_<suffix>`.
- Unknown fields are rejected (`extra="forbid"`). Text fields are stripped and must not be empty.

## 2. Analysis Request

```json
{
  "question": "What factors explain BTC's recent market behavior?",
  "assets": ["BTC"],
  "requested_at": "2026-07-17T06:00:00Z",
  "analysis_as_of": "2026-07-17T06:00:00Z",
  "deadline_seconds": 900,
  "run_mode": "official",
  "enable_conditional_debate": false
}
```

Rules:

- `assets` contains one or two unique supported assets.
- `question` has a bounded configured length and is treated as untrusted input.
- In `official`, omitted `analysis_as_of` is frozen to current UTC. Rehearsal/demo may supply it.
- If question text and `assets` disagree, `assets` wins and a warning is logged.
- In MVP, `enable_conditional_debate=true` is accepted but recorded as disabled/ignored in every run mode; execution still routes to Arbiter.

## 3. Evidence Item

```json
{
  "evidence_id": "ev_001",
  "asset": "BTC",
  "source_type": "market",
  "source_name": "Binance Spot",
  "source_url": "https://api.binance.com/api/v3/klines",
  "published_at": "2026-07-17T00:00:00Z",
  "fetched_at": "2026-07-17T06:01:00Z",
  "query_or_parameters": "symbol=BTCUSDT&interval=1d; credentials removed",
  "content_reference": "2026-07-16 UTC close and computed 14-day return input range",
  "normalized_fact": "BTC's 14-day return was X% through 2026-07-16 UTC.",
  "reliability": "high",
  "independence_group": "binance.com",
  "content_hash": "<64 lowercase hex characters>",
  "is_cached": false,
  "cache_time": null,
  "is_stale": false
}
```

Field rules:

- `asset` is a supported asset or `null` only for genuinely market-wide context such as Fear & Greed.
- `source_url` is the direct source/API/original publisher URL, never a fabricated link.
- `published_at` may be `null` only when the provider truly supplies no source time; the limitation must be recorded.
- `fetched_at` is required and cannot precede a known `published_at` by more than clock tolerance.
- `query_or_parameters` contains reproducibility parameters but no token, header, credential, or signed URL.
- `content_reference` is a short quotation, metric/range, or bounded source summary. It is not an entire copyrighted article.
- `normalized_fact` is one factual proposition. It contains no recommendation, unsupported causal inference, or stance.
- `content_hash` is SHA-256 over the canonicalized source payload or normalized content reference only. Source name, URL, and repost timestamp are excluded so byte-equivalent reposts can collapse; no fuzzy or semantic matching is allowed.
- Cache fields are consistent: `is_cached=false` requires `cache_time=null`; `is_cached=true` requires `cache_time` and a computed `is_stale`.
- `is_stale` is metadata. Policy may cap confidence or disclose age; Alternative.me is already `low` and is not demoted below `low`.

## 4. Reliability Policy

Reliability is deterministic and static by source class:

| Reliability | Eligible sources |
|---|---|
| `high` | Organizer OHLCV benchmark, originating exchange API market data, verified official project announcement/feed, deterministic calculation whose inputs are high-reliability evidence |
| `medium` | Identifiable original news page with URL and timestamp |
| `low` | Aggregator or repost records whose original page was not fetched, Alternative.me Fear & Greed, social/community claims, missing-author/missing-time summaries, unverifiable secondary commentary |

- An LLM never assigns or upgrades reliability.
- Corroboration affects claim confidence, not the Evidence Item's source reliability.
- A CryptoPanic or RSS record remains `low` when only the aggregator/feed item was fetched, even if it names the upstream publisher. It becomes `medium` only when the original news page is actually fetched and cited.
- Stale data is marked and disclosed. It may cap claim confidence through deterministic policy, but Alternative.me remains `low` rather than receiving another downgrade.
- A cached official/high source retains its source class while cache age is disclosed; stale cache cannot by itself support a high-confidence current-state conclusion.

## 5. Independence Group Policy

Use the first applicable rule:

1. Original publisher/producer ID when the upstream producer is known.
2. Registered domain of the original source URL, normalized to lowercase without `www`.
3. Configured provider ID when no original URL exists.

Fixed examples:

- Organizer CSV: `organizer-public-market-data`.
- Binance: `binance.com`.
- Alternative.me: `alternative.me`.
- CryptoPanic item: original publisher domain when present; otherwise `cryptopanic.com`.
- A repost and its original publisher share the original publisher's group when provenance is known.

Different URLs, endpoints, or articles from the same upstream producer do not create independent groups.

## 6. Deduplication

- Collapse only exact matching `content_hash` values.
- Preserve the earliest canonical Evidence Item and attach safe provenance aliases internally if needed.
- Do not implement embeddings, fuzzy similarity, title similarity, or paraphrase clustering in MVP.
- Deduplication never merges two opposing facts solely because they concern the same topic.

## 7. Claim

```json
{
  "claim_id": "cl_002",
  "claim_type": "inference",
  "assets": ["BTC"],
  "time_range": {
    "start": "2026-07-03",
    "end": "2026-07-17"
  },
  "text": "The recent move is accompanied by above-normal quote volume.",
  "based_on_claim_ids": ["cl_001"],
  "confidence": "medium",
  "limitations": ["Live volume comes from one exchange."],
  "invalidation_conditions": ["Comparable quote volume falls below its rolling baseline."]
}
```

Rules:

- `assets` contains one or two supported assets relevant to the claim.
- `time_range.start <= time_range.end <= analysis_as_of`.
- `fact`: `based_on_claim_ids` is empty and at least one non-neutral Evidence Link is required.
- `inference`: depends on at least one earlier fact/inference and has supporting evidence links.
- `conclusion`: depends on at least one fact or inference and has supporting evidence links unless the result is explicitly `insufficient_data=true`.
- Claim dependencies resolve within the same result and form a directed acyclic graph.
- Claims must not contain direct buy/sell/position-size instructions.

## 8. Claim-Evidence Link

```json
{
  "claim_id": "cl_001",
  "evidence_id": "ev_001",
  "stance": "supports",
  "reason": "The calculated return directly measures the claim's stated period."
}
```

- Both IDs must resolve.
- `reason` explains the relationship for this claim; it does not restate the evidence.
- Stance belongs on the link, never on the Evidence Item. One Evidence Item may support one claim and oppose another.
- `neutral` can provide context but cannot satisfy conclusion coverage.

## 9. Material Conflict

A claim has a material conflict exactly when all are true:

1. It has at least one `supports` link and at least one `opposes` link.
2. Evidence on both sides has reliability `high` or `medium`.
3. At least one supporting/opposing pair comes from different `independence_group` values.

The Evidence Processor produces a deterministic `ConflictIndicator` listing claim ID, supporting evidence IDs, opposing evidence IDs, groups, and rule version. H3 does not need to execute for the conflict to be preserved. Arbiter and Renderer must show both sides, and affected claim confidence is capped at `low` until the conflict is resolved.

## 10. Confidence Rubric and Caps

`high` requires:

- at least two independent groups with `high`/`medium` supporting evidence;
- no material conflict;
- no missing source central to the claim;
- a reproducible deterministic market measurement when the claim concerns market behavior.

`medium` applies when evidence is relevant but there is only one strong independent group, some support is low reliability, the sample is limited, or a non-central source is missing.

`low` applies when evidence is insufficient, a material conflict exists, central data is stale/unavailable, or the evidence does not directly answer the claim.

Deterministic maximums:

- `insufficient_data=true` -> overall confidence `low`.
- material conflict on a conclusion -> that conclusion `low`; overall confidence cannot be `high`.
- fewer than two supporting independence groups -> claim cannot be `high`.
- only `low` evidence -> claim is `low`.
- stale cache as the only current evidence -> current-state claim is `low`.

Arbiter supplies `confidence_rationale` naming applicable rubric conditions. Numeric probabilities are forbidden.

## 11. Analysis Result

```json
{
  "run_id": "run_20260717_060000_ab12",
  "question": "What factors explain BTC's recent market behavior?",
  "assets": ["BTC"],
  "analysis_as_of": "2026-07-17T06:00:00Z",
  "direct_answer": "The evidence supports a qualified explanation...",
  "market_context": {
    "summary": "BTC market context through the frozen cutoff.",
    "time_range": {"start": "2026-07-03", "end": "2026-07-17"}
  },
  "claims": [],
  "claim_evidence_links": [],
  "confidence": "medium",
  "confidence_rationale": "Two independent sources support the main observation, with a news coverage limitation.",
  "limitations": [],
  "invalidation_conditions": [],
  "watch_items": [],
  "insufficient_data": false,
  "degradation_notes": []
}
```

Result invariants:

- Run/question/assets/cutoff equal the frozen request context.
- Every link and dependency resolves; the claim graph is acyclic.
- Every conclusion is traceable to evidence and upstream facts/inferences, except an explicit insufficient-data result.
- Direct answer and report statements are entailed by validated claims; the renderer adds no new facts.
- All material conflicts, missing branches, source fallbacks, stale/cache states, and LLM fallback states appear in limitations or degradation notes.

## 12. Evidence Ledger Artifact

`evidence.json` contains:

```json
{
  "schema_version": "1.0",
  "run_id": "run_20260717_060000_ab12",
  "analysis_as_of": "2026-07-17T06:00:00Z",
  "run_mode": "official",
  "items": [],
  "conflict_indicators": [],
  "degradation_events": []
}
```

Items are sorted by `evidence_id`. A zero-item ledger is valid only with `degradation_events` explaining why.

## 13. Execution Log Contract

Each line of `execution_log.jsonl` is one JSON object with:

- `schema_version`, `timestamp`, `run_id`, `run_mode`;
- `stage`, `event_type`, `status`, `duration_ms`;
- `provider_or_model`, sanitized `parameters`, `attempt`;
- `input_count`, `output_count`, `error_category`, public-safe `message`.

Allowed event categories include run/stage/tool start/end, timeout, retry, cancellation, degradation, mode fallback, schema repair, artifact write, and run terminal state. Do not log full prompts, chain-of-thought, authorization data, or secrets.

## 14. Run Config Contract

`run_config.json` snapshots:

- schema/prompt/policy versions;
- sanitized request and immutable cutoff;
- requested and effective run/data modes;
- deadlines and actual stage durations;
- configured source/model identifiers;
- booleans indicating optional key presence, never key values;
- fallback/cache/stale states;
- terminal status and artifact checksums.

Configuration names are fixed: `BEDROCK_PRIMARY_MODEL_ID`, `BEDROCK_FALLBACK_MODEL_ID`, and `CRYPTOPANIC_API_TOKEN`.

## 15. Market Metric Contracts

- All windows and parameters are persisted with the resulting evidence.
- Use UTC daily bars at or before `analysis_as_of`.
- Historical return is `close_t / close_(t-n) - 1` when both points exist.
- Drawdown is `close_t / cumulative_max_close_t - 1`; maximum drawdown is the minimum over the requested window.
- Volatility uses a declared return frequency/window and sample standard deviation; annualization, if used, must state its factor.
- Volume z-score compares an asset to its own rolling base-volume history only.
- Cross-asset liquidity comparisons use comparable quote/USD volume from the same provider and period.
- Missing input bars produce unavailable metrics, not forward-filled synthetic facts.
- Golden fixtures define rounding and boundary behavior; calculations retain full internal precision and round only in rendering.
