"""Loading and slicing the organizer OHLCV files into a ``MarketBundle``.

The only module in this package that touches the filesystem. It also runs the
integrity check on the way in, so a malformed file surfaces here rather than
as a strange number several layers downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from calc.data_quality import IntegrityReport, check_ohlc_integrity

from .base import MarketBundle

DEFAULT_ASSETS: tuple[str, ...] = ("BTC", "ETH", "SOL", "BNB", "XRP")
DEFAULT_BENCHMARK = "BTC"


class DatasetError(RuntimeError):
    """Raised when the requested asset data cannot be loaded at all."""


@dataclass(frozen=True)
class LoadReport:
    """What was loaded and what the integrity check found."""

    asset: str
    integrity: IntegrityReport
    peers_loaded: tuple[str, ...]
    peers_missing: tuple[str, ...]
    as_of: date | None
    truncated_to_as_of: bool


def _read_csv(directory: Path, asset: str) -> pd.DataFrame:
    path = directory / f"{asset}_daily_ohlcv.csv"
    if not path.exists():
        raise DatasetError(f"no OHLCV file for {asset} at {path}")
    frame = pd.read_csv(path, parse_dates=["date"])
    return frame.sort_values("date").reset_index(drop=True)


def _slice_to(frame: pd.DataFrame, as_of: date | None) -> tuple[pd.DataFrame, bool]:
    """Drop bars after ``as_of``.

    A skill asked to report "as of" a past date must not see later bars; this
    is where that guarantee is enforced, once, rather than in each skill.
    """
    indexed = frame.set_index("date")
    if as_of is None:
        return indexed, False
    cutoff = pd.Timestamp(as_of)
    truncated = bool((indexed.index > cutoff).any())
    return indexed.loc[indexed.index <= cutoff], truncated


def load_bundle(
    directory: str | Path,
    asset: str,
    as_of: date | None = None,
    peers: tuple[str, ...] | None = None,
    benchmark: str = DEFAULT_BENCHMARK,
) -> tuple[MarketBundle, LoadReport]:
    """Load one asset plus its peers, sliced to ``as_of``.

    A peer that fails to load is recorded as missing rather than raising: the
    attribution skill can degrade, while everything else still runs.
    """
    directory = Path(directory)
    frame = _read_csv(directory, asset)
    integrity = check_ohlc_integrity(frame)
    sliced, truncated = _slice_to(frame, as_of)

    if sliced.empty:
        raise DatasetError(f"{asset} has no bars at or before {as_of}")

    wanted = tuple(peers) if peers is not None else DEFAULT_ASSETS
    loaded_peers: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for name in wanted:
        if name == asset:
            continue
        try:
            peer_sliced, _ = _slice_to(_read_csv(directory, name), as_of)
        except DatasetError:
            missing.append(name)
            continue
        if peer_sliced.empty:
            missing.append(name)
        else:
            loaded_peers[name] = peer_sliced

    bundle = MarketBundle(asset=asset, frame=sliced, peers=loaded_peers, benchmark=benchmark)
    report = LoadReport(
        asset=asset,
        integrity=integrity,
        peers_loaded=tuple(sorted(loaded_peers)),
        peers_missing=tuple(missing),
        as_of=bundle.as_of,
        truncated_to_as_of=truncated,
    )
    return bundle, report
