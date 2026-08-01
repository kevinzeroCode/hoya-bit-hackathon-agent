#!/usr/bin/env python
"""Generate a price analysis report for one asset, as Markdown and/or HTML.

    python scripts/analyze.py BTC
    python scripts/analyze.py ETH --as-of 2025-06-30 --format html
    python scripts/analyze.py XRP --out-dir out --format md,html
    python scripts/analyze.py BNB --skills A1,A3,A5 --stdout
    python scripts/analyze.py BTC --name btc-run-7f3a      # keep runs side by side

Output filenames default to `<asset>-analysis-<as_of>` plus the skill subset
when one is requested. Pass `--name` (a run id, say) when several reports of
the same asset must coexist. Existing files are never overwritten unless
`--force` is given.

This is a development and inspection entry point. It writes plain files with
whatever names you ask for, and deliberately does **not** implement the
run-artifact contract (`final_report.md`, `evidence.json`,
`execution_log.jsonl`, `run_config.json`, shared `run_id`, atomic replace).
That contract belongs to the pipeline's artifact store; a second, weaker
implementation of it here would be worse than none, because it would look
authoritative while skipping the guarantees.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# E402 is deliberate: these imports must follow the sys.path insert above so the
# script also runs from a bare clone, without `pip install -e .`.
from skills import build_report, load_bundle  # noqa: E402
from skills.dataset import DEFAULT_ASSETS, DatasetError  # noqa: E402
from skills.report import SKILL_ORDER  # noqa: E402

DEFAULT_DATA_DIR = REPO_ROOT / "HOYA_BIT_crypto_market_dataset" / "data"


def _parse_date(value: str) -> date:
    """Parse a calendar date.

    ``date.fromisoformat`` rather than ``strptime``: ``as_of`` selects a UTC
    trading day, not an instant, so constructing a datetime here would invent
    a time-of-day that has no meaning for daily bars.
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def _parse_formats(value: str) -> tuple[str, ...]:
    formats = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    unknown = [f for f in formats if f not in ("md", "html")]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown format(s): {', '.join(unknown)}")
    return formats or ("md",)


def _parse_skills(value: str) -> tuple[str, ...]:
    skills = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    unknown = [s for s in skills if s not in SKILL_ORDER]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown skill(s): {', '.join(unknown)}; available: {', '.join(SKILL_ORDER)}"
        )
    return skills or SKILL_ORDER


def _parse_name(value: str) -> str:
    """Validate a custom filename stem.

    Rejects path separators and parent references so a stem can never write
    outside ``--out-dir``; an extension is rejected because the format flags
    choose it.
    """
    name = value.strip()
    if not name:
        raise argparse.ArgumentTypeError("name must not be empty")
    if any(sep in name for sep in ("/", "\\", "..")) or Path(name).is_absolute():
        raise argparse.ArgumentTypeError(
            f"name must be a plain filename stem without path separators, got {value!r}"
        )
    if name.endswith((".md", ".html")):
        raise argparse.ArgumentTypeError(
            f"give the stem without an extension; --format chooses it (got {value!r})"
        )
    return name


def default_stem(asset: str, as_of, skills: tuple[str, ...]) -> str:
    """Build the default stem.

    A requested subset is folded into the name, so that a partial run and a
    full run of the same asset and date do not land on the same file.
    """
    stem = f"{asset.lower()}-analysis"
    if as_of:
        stem += f"-{as_of.isoformat()}"
    if tuple(skills) != SKILL_ORDER:
        stem += "-" + "-".join(s.lower() for s in skills)
    return stem


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic price analysis report for one asset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("asset", help=f"asset symbol, e.g. {', '.join(DEFAULT_ASSETS)}")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="directory holding <ASSET>_daily_ohlcv.csv files")
    parser.add_argument("--out-dir", type=Path, default=Path("."),
                        help="where to write the report files (default: current directory)")
    parser.add_argument("--as-of", type=_parse_date, default=None,
                        help="report as of this date (YYYY-MM-DD); later bars are ignored")
    parser.add_argument("--format", type=_parse_formats, default=("md", "html"),
                        help="comma-separated: md, html (default: md,html)")
    parser.add_argument("--skills", type=_parse_skills, default=SKILL_ORDER,
                        help=f"comma-separated subset of {', '.join(SKILL_ORDER)}")
    parser.add_argument("--benchmark", default="BTC",
                        help="benchmark asset for attribution (default: BTC)")
    parser.add_argument("--name", type=_parse_name, default=None,
                        help="output filename stem without extension; pass a run id here "
                             "to keep several reports of one asset side by side")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing output files (refused by default)")
    parser.add_argument("--stdout", action="store_true",
                        help="print to stdout instead of writing files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    asset = args.asset.upper()

    try:
        bundle, load_report = load_bundle(
            args.data_dir, asset, as_of=args.as_of, benchmark=args.benchmark.upper()
        )
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_report(bundle, skill_ids=args.skills)

    if args.stdout:
        print(report.html if args.format == ("html",) else report.markdown)
        return 0

    stem = args.name or default_stem(asset, bundle.as_of, args.skills)
    targets = {fmt: args.out_dir / f"{stem}.{fmt}" for fmt in args.format}

    # Check every target before writing any, so a refusal leaves nothing behind.
    existing = [p for p in targets.values() if p.exists()]
    if existing and not args.force:
        print(
            "error: refusing to overwrite existing report(s):\n"
            + "\n".join(f"  {p}" for p in existing)
            + "\nuse --name <stem> to write alongside them, or --force to replace them.",
            file=sys.stderr,
        )
        return 3

    args.out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt, path in targets.items():
        path.write_text(report.markdown if fmt == "md" else report.html, encoding="utf-8")
        written.append(path)

    # Report what happened, including anything that could not be determined.
    print(f"{asset}  as_of={bundle.as_of}  bars={bundle.bars}")
    if not load_report.integrity.is_clean:
        print("  warning: OHLCV integrity check reported problems")
    if load_report.peers_missing:
        print(f"  peers missing: {', '.join(load_report.peers_missing)}")
    print("  " + "  ".join(f"{r.skill_id}={r.status}" for r in report.results))
    for path in written:
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
