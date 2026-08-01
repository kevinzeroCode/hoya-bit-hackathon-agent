# Live source check — provider drift rehearsal

Records what was actually executed against real providers. No tokens, credentials,
response headers or full payloads are recorded here.

## 2026-08-01 (S8 / Move 2)

**Command**

```powershell
$env:RUN_LIVE_TESTS = "1"
python -m pytest tests/live -m live -q
```

**Result:** `8 passed, 4 skipped in 2.52s`

| Source | Operation | Result |
|---|---|---|
| Binance spot klines | `fetch_binance_daily`, BTC/ETH/SOL/BNB/XRP, daily UTC | ✅ pass — bars present, ordered, completed candles only, `date <= cutoff` for all five |
| First-party outlet RSS (CoinDesk) — **designated baseline research source** | `fetch_rss_news` via `RssResearchAdapter` | ✅ pass — parsed, records carry `original_publisher=coindesk.com` and a usable timestamp |
| Alternative.me Fear & Greed | `fetch_fear_greed` via `FearGreedResearchAdapter` | ✅ pass — `asset=None` on every record (market-wide, never per-coin) |
| Official project feeds (BTC, ETH) | `fetch_official_announcements` | ✅ pass — best-effort contract holds; outcome is `ok`/`empty`/`http_error`, never a hard failure |
| CryptoPanic | `fetch_cryptopanic_news` | ⏸ skipped — `CRYPTOPANIC_API_TOKEN` not configured |
| Bedrock primary (Converse + forced `toolConfig`) | `converse_structured` → `ArbiterOutput` | ⏸ **skipped — no AWS credentials and no `BEDROCK_PRIMARY_MODEL_ID` in this environment** |
| Bedrock fallback model | `converse_structured` | ⏸ skipped — `BEDROCK_FALLBACK_MODEL_ID` not configured |

**No provider schema drift detected** in the sources that ran: no adapter returned
empty because of a renamed field.

## Offline Silver fallback half

```powershell
python scripts/live_silver_run.py --mode fallback --asset BTC
```

`run_20260801_160034_s0034` — `rehearsal`, terminal state `degraded`, 3.3 s,
**four artifacts present**, 5 market evidence items, one independence group
(`organizer-public-market-data`), 0 conflict indicators. Research contributed
nothing by design: with Bedrock forced to fail there is no bounded extraction call,
so the branch is honestly recorded as `degraded` rather than silently empty.

## Still outstanding for Silver

One live Bedrock Converse structured-output call through `adapters/bedrock.py`,
across both baseline paths. Blocked here only by environment, not by code:

```powershell
$env:AWS_REGION = "us-west-2"
$env:BEDROCK_PRIMARY_MODEL_ID = "<current Haiku 4.5 inference-profile id>"
$env:RUN_LIVE_TESTS = "1"
python -m pytest tests/live/test_bedrock_access.py -m live -vv
python scripts/live_silver_run.py --mode live --asset BTC
```

## Environment

| Item | Value |
|---|---|
| Python (local shell) | **3.13.11** — note the deviation: the project targets 3.12 and the image is `python:3.12-slim`. The suite passes on both, but timing/behaviour claims should be made on 3.12. |
| Docker CLI | **not installed in this shell** — container checks remain S11 work |
| AWS CLI | **not installed**; `boto3` reports `NoCredentialsError` |
| Network | outbound HTTPS available (Binance ping 200, CoinDesk feed 200) |
