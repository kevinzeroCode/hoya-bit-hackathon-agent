# `scripts/analyze.py` — usage guide

Operational reference for an agent driving the price-analysis report generator.
Everything below is verified against the current script.

---

## 1. What it is, and what it is not

Generates a deterministic price analysis report for **one asset**, as Markdown
and/or HTML, from the organizer OHLCV CSVs. Same inputs and same `as_of`
always produce byte-identical output. No model is invoked; no network is used.

**It does not implement the run-artifact contract.** It never writes
`final_report.md`, `evidence.json`, `execution_log.jsonl` or `run_config.json`,
does not share a `run_id` across files, and does not use atomic replace. Do not
treat its output as a run artifact or as evidence of a completed run. That
contract belongs to the pipeline's artifact store.

**Prefer the in-process API when you need data rather than files** — see §9.
Use this CLI when the deliverable is a file a human will open.

---

## 2. Invocation

```bash
python scripts/analyze.py <ASSET> [options]
```

Run from the repository root. The script inserts `src/` on `sys.path` itself,
so no install step and no `PYTHONPATH` are required. Requires `pandas` and
`numpy` only.

`<ASSET>` is case-insensitive (`btc` == `BTC`). Assets available in the shipped
dataset: `BTC`, `ETH`, `SOL`, `BNB`, `XRP`.

On Windows terminals, set `PYTHONIOENCODING=utf-8` before invoking, or the
Traditional Chinese output will be mangled on stdout. File output is always
written as UTF-8 regardless.

---

## 3. Options

| Flag | Default | Meaning |
|---|---|---|
| `--data-dir PATH` | `HOYA_BIT_crypto_market_dataset/data` | Directory holding `<ASSET>_daily_ohlcv.csv` |
| `--out-dir PATH` | `.` (current directory) | Where report files are written; created if missing |
| `--as-of YYYY-MM-DD` | last bar in the file | Report as of this date; **all later bars are dropped**, for the asset and every peer |
| `--format md,html` | `md,html` | Comma-separated; only `md` and `html` are valid |
| `--skills A1,A3` | all seven | Comma-separated subset of `A1,A2,A3,A4,A5,A7,A9` |
| `--benchmark ASSET` | `BTC` | Benchmark for A5 attribution |
| `--name STEM` | see §6 | Output filename stem, no extension |
| `--force` | off | Permit overwriting existing output files |
| `--stdout` | off | Print to stdout, write nothing |

Notes:

- `--as-of` is enforced in the loader, once, for the asset **and its peers** —
  no skill can see a bar after it. Use this for reproducible historical runs.
- `--name` rejects path separators, `..`, absolute paths, and `.md`/`.html`
  extensions. A stem can never write outside `--out-dir`.
- `--stdout` prints **HTML only when `--format html` is given exactly**;
  in every other case (including the default `md,html`) it prints Markdown.
  `--name` and `--force` are ignored in this mode.

---

## 4. Exit codes

| Code | Meaning | Retry? |
|---|---|---|
| `0` | Success | — |
| `2` | Either invalid arguments **or** dataset error — disambiguate via stderr (below) | Fix the invocation |
| `3` | Refused to overwrite existing output file(s) | Re-run with `--name` or `--force` |

**Exit code 2 is ambiguous** — `argparse` and the dataset loader both use it.
Discriminate on the first line of stderr:

| stderr begins with | Cause | Action |
|---|---|---|
| `usage:` | Invalid flag or value; the message names the offending argument | Correct the invocation |
| `error:` | Asset file missing, or `--as-of` precedes the series start | Check asset symbol / date range |

Examples:

```
error: no OHLCV file for DOGE at .../DOGE_daily_ohlcv.csv
error: BTC has no bars at or before 2000-01-01
analyze.py: error: argument --format: unknown format(s): pdf
```

A non-zero exit writes **no files at all** — see §6 on atomicity.

---

## 5. stdout contract

On success, stdout is stable and parseable:

```
BTC  as_of=2026-05-31  bars=1826
  A1=degraded  A2=ok  A3=ok  A4=ok  A5=unavailable  A7=ok  A9=degraded
  wrote /abs/path/btc-analysis-2026-05-31.md
  wrote /abs/path/btc-analysis-2026-05-31.html
```

Line order is fixed:

1. `<ASSET>  as_of=<date>  bars=<int>`
2. `  warning: OHLCV integrity check reported problems` — **only if** the input
   CSV failed validation. Treat the report as suspect.
3. `  peers missing: X, Y` — **only if** some peer failed to load. A5 may be
   degraded or unavailable as a result.
4. One line of `  <SKILL>=<status>` pairs, in report order.
5. One `  wrote <path>` line per file written.

Status values are exactly `ok`, `degraded`, `unavailable`. Parse line 4 to
decide whether a section is usable before quoting it.

Errors go to stderr; nothing else does.

---

## 6. Output files and collisions

Default stem: `<asset>-analysis-<as_of>`, plus `-<skills>` when a subset was
requested.

| Command | File stem |
|---|---|
| `analyze.py BTC` | `btc-analysis-2026-05-31` |
| `analyze.py BTC --skills A1` | `btc-analysis-2026-05-31-a1` |
| `analyze.py BTC --skills A1,A3` | `btc-analysis-2026-05-31-a1-a3` |
| `analyze.py BTC --name btc-run-7f3a` | `btc-run-7f3a` |

**Existing files are never overwritten.** A collision exits `3` with:

```
error: refusing to overwrite existing report(s):
  /abs/path/btc-analysis-2026-05-31.md
use --name <stem> to write alongside them, or --force to replace them.
```

All target paths are checked **before any file is written**, so a refusal
leaves the directory exactly as it was — there is no half-written pair.

**Recommendation for agent use:** always pass `--name` incorporating your run
id, e.g. `--name btc-{run_id}`. This makes collisions structurally impossible,
keeps multiple reports of one asset side by side, and makes each file traceable
to the run that produced it. Do not rely on `--force` — it destroys a prior
report, which may be the one another step is about to read.

---

## 7. Skills reference

| ID | Name | Needs | Returns `unavailable` when |
|---|---|---|---|
| A1 | 市場體制標籤 | ≥252 bars | Fewer than 252 bars |
| A2 | 價格位置與趨勢快照 | ≥2 bars | Fewer than 2 bars (degrades per-metric otherwise) |
| A3 | 波動與風險輪廓 | ≥31 bars | Fewer than 31 bars |
| A4 | 參與度與流動性檢查 | ≥60 bars | Fewer than 60 bars |
| A5 | 單幣特有 vs 全市場歸因 | ≥91 bars + benchmark | Asset **is** the benchmark, benchmark missing, or too few bars |
| A7 | 歷史類比基準率 | ≥400 bars **and** ≥8 independent episodes | Either condition unmet — see below |
| A9 | 跨來源驗證與衝突旗標 | ≥60 bars | Fewer than 60 bars |

Thresholds verified against the shipped dataset: each skill is `unavailable`
one bar below its stated minimum and produces output at it.

**A7 is the exception: its bar count is necessary but not sufficient.** The
binding constraint is 8 distinct low-volatility episodes, which is
data-dependent — on the shipped files A7 first succeeds at 625 bars (BNB),
655 (BTC), 680 (SOL), 835 (XRP) and 965 (ETH). Expect `unavailable` anywhere
below roughly 1,000 bars, and do not treat 400 bars as enough.

A skill never raises. Insufficient data always becomes a status plus a stated
reason, and the section still appears in the report saying why it is empty.

---

## 8. Behaviours that look like failures but are not

Do not "fix" these by retrying or by switching flags blindly.

**A5 is `unavailable` for BTC.** The default benchmark is BTC, so analysing BTC
would correlate it with itself: correlation 1.00, beta 1.00, flat relative
strength. Those are tautologies, so the skill refuses. Pass `--benchmark ETH`
(or any other loaded asset) to attribute BTC against something. Note the
resulting comparison is against **that single asset**, not a market index; the
section's own limitations say so, and the group dispersion figure in the same
section is the better market-wide signal. Only BTC is affected.

**A9 is always `degraded`, never `ok`.** No research sources exist in this
repository, so cross-source verification cannot be performed. The section
supplies price-side facts for later checking and states the missing capability.
This is by construction — an unverified analysis must not be presentable as a
verified one. Do not report A9 as if verification occurred.

**A1 is usually `degraded`.** When realised volatility is compressed, the
§16.3 label enum has no term for it (`high_volatility` exists; no low
counterpart). A1 emits the spec label, discloses the compression separately,
and marks itself degraded. The label is still correct and usable.

**A "full run" is seven skills, not ten.** A6, A8 and A10 from the source
design document are not implemented. A full run carries no skill suffix in its
filename, so if those are added later the default filename will not change
while its meaning does. Another reason to pass `--name`.

---

## 9. Preferred alternative: in-process API

If you need structured values — not a file for a human — import the package
instead of shelling out. This avoids subprocess overhead, avoids parsing
Markdown back out, and gives you the numbers with their provenance.

```python
import sys; sys.path.insert(0, "src")
from skills import load_bundle, build_report, a1_regime

bundle, load_report = load_bundle(
    "HOYA_BIT_crypto_market_dataset/data", "BTC", as_of=None, benchmark="BTC"
)

report = build_report(bundle)          # runs all seven skills once
report.markdown                        # str — full zh-Hant document
report.html                            # str — full standalone HTML document
report.statuses                        # {"A1": "degraded", ...}
report.result("A1").findings           # dict of the actual numbers
report.result("A1").evidence_refs      # provenance for each figure
report.result("A1").limitations        # tuple[str, ...]
report.result("A1").section_html       # just this section, as HTML

single = a1_regime.run(bundle)         # or run one skill alone
```

`load_bundle` raises `skills.dataset.DatasetError` for a missing asset or an
`as_of` before the series starts. Skills themselves never raise.

Always check `result.status` (or `result.is_usable`) before quoting a figure,
and carry `result.limitations` alongside anything you quote.

---

## 10. Recipes

```bash
# Standard report for one asset, both formats, collision-safe
python scripts/analyze.py ETH --out-dir output --name eth-{run_id}

# Historical point-in-time run (no bars after the date are visible)
python scripts/analyze.py SOL --as-of 2025-06-30 --out-dir output

# BTC with a usable A5
python scripts/analyze.py BTC --benchmark ETH --out-dir output --name btc-vs-eth

# Only the sections you need, HTML only
python scripts/analyze.py XRP --skills A1,A3,A7 --format html --out-dir output

# Inspect without writing anything
python scripts/analyze.py BNB --stdout

# Regenerate over a previous report deliberately
python scripts/analyze.py BNB --out-dir output --force
```

---

## 11. Preconditions checklist

Before invoking, confirm:

- Working directory is the repository root.
- `--data-dir` contains `<ASSET>_daily_ohlcv.csv` for the asset **and** for the
  benchmark (A5 needs the benchmark loaded).
- `--as-of`, if given, falls within the series range.
- `--out-dir` is writable, and the target stem is unused (or `--name` carries a
  run id).
- `PYTHONIOENCODING=utf-8` is set if you will read stdout on Windows.
