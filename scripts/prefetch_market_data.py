"""Prefetch five years of Binance daily OHLCV into the local market cache.

Usage:
    python scripts/prefetch_market_data.py --output-dir market_cache
    python scripts/prefetch_market_data.py --assets BTC ETH --as-of 2026-08-02
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
import tempfile
from datetime import UTC, date, datetime, time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hoya_agent.adapters.binance import fetch_binance_daily_history  # noqa: E402
from hoya_agent.models import Asset  # noqa: E402


def _write_csv(path: Path, bars: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("date", "open", "high", "low", "close", "volume"))
            for bar in bars:
                writer.writerow((bar.date.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def _prefetch(assets: list[str], output_dir: Path, as_of: datetime, days: int) -> int:
    async with httpx.AsyncClient() as client:
        for asset in assets:
            bars, notes = await fetch_binance_daily_history(
                asset,
                analysis_as_of=as_of,
                client=client,
                days=days,
            )
            if not bars:
                print(f"{asset}: no bars fetched; {'; '.join(notes)}", file=sys.stderr)
                return 1
            path = output_dir / f"{asset}_daily_ohlcv.csv"
            _write_csv(path, bars)
            print(f"{asset}: {len(bars)} daily bars {bars[0].date}..{bars[-1].date} -> {path}")
            for note in notes:
                print(f"  note: {note}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assets",
        nargs="+",
        choices=[asset.value for asset in Asset],
        default=[asset.value for asset in Asset],
    )
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--output-dir", type=Path, default=Path(os.getenv("HOYA_MARKET_CACHE_DIR", "market_cache")))
    args = parser.parse_args()
    if args.years <= 0:
        parser.error("--years must be positive")
    as_of = datetime.combine(args.as_of, time.max, tzinfo=UTC)
    return asyncio.run(_prefetch(args.assets, args.output_dir, as_of, args.years * 365 + 2))


if __name__ == "__main__":
    raise SystemExit(main())
