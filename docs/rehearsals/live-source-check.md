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

## 2026-08-02 (S11) — CSV / Binance overlap check

§3.2 的 S11 人工項目：主辦方 CSV 與 Binance 在重疊區間 **2026-05-01 ～ 2026-05-31** 的收盤差異，五幣全查。

**執行**：`adapters/organizer_csv.load_organizer_csv` 對上 `adapters/binance.fetch_binance_daily`，
逐日比對 close。（一次性檢查，未新增追蹤腳本。）

| 資產 | 重疊天數 | 平均 \|差異\| % | 最大 \|差異\| % |
|---|---:|---:|---:|
| BTC | 31 | 0.0000% | 0.0000% |
| ETH | 31 | 0.0000% | 0.0000% |
| SOL | 31 | 0.0000% | 0.0000% |
| BNB | 31 | 0.0000% | 0.0000% |
| XRP | 31 | 0.0000% | 0.0000% |

抽樣（BTC，close 與 volume 皆到小數點後四位完全相同）：

| date | CSV close | Binance close | CSV volume | Binance volume |
|---|---:|---:|---:|---:|
| 2026-05-01 | 78231.1300 | 78231.1300 | 17315.4650 | 17315.4650 |
| 2026-05-15 | 79113.2100 | 79113.2100 | 17351.2708 | 17351.2708 |
| 2026-05-31 | 73674.3900 | 73674.3900 | 6986.4571 | 6986.4571 |

**怎麼陳述這件事（重要）**

- ✅ 可以說：兩個來源在這段重疊區間的數值**一致**，所以 2026-06-01 的 CSV → live 來源切換
  在數值上不會出現斷階。
- 🚫 **不可以說**：CSV「來自 Binance」。數值一致是**吻合**，不是**出處**。
  競賽規則明訂主辦方 CSV 的 metadata 只標 `public_market_data`，不得推定其上游交易所
  （`.kiro/steering/competition-rules.md` → Approved Data Policy）。
- 兩者仍計為**不同來源**。跨越 2026-06-01 時照樣標記來源切換點並揭露差異（此處差異為零）。
- 實作上這已經是對的：ledger 裡 CSV 證據的 `independence_group` 是
  `organizer-public-market-data`，`source_name` 是 `public_market_data`，兩者都沒有提到交易所。
