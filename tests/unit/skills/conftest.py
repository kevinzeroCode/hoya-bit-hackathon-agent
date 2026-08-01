"""Fixtures for skill tests: real bundles, plus deliberately truncated ones."""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.base import MarketBundle
from skills.dataset import load_bundle

# parents[3] == repo root, from tests/unit/skills/
DATASET_DIR = Path(__file__).resolve().parents[3] / "HOYA_BIT_crypto_market_dataset" / "data"


@pytest.fixture(scope="session")
def dataset_dir() -> Path:
    return DATASET_DIR


@pytest.fixture(scope="session")
def bundles(frames) -> dict[str, MarketBundle]:
    """One bundle per asset, each carrying the other four as peers."""
    out: dict[str, MarketBundle] = {}
    for asset, frame in frames.items():
        peers = {name: other for name, other in frames.items() if name != asset}
        out[asset] = MarketBundle(asset=asset, frame=frame, peers=peers, benchmark="BTC")
    return out


@pytest.fixture(scope="session")
def btc(bundles) -> MarketBundle:
    return bundles["BTC"]


@pytest.fixture(scope="session")
def bnb(bundles) -> MarketBundle:
    """BNB is the asset that decoupled -- the interesting case for A5."""
    return bundles["BNB"]


@pytest.fixture
def truncated(bundles):
    """Build a bundle with only the first ``n`` bars, for degradation tests."""

    def _make(asset: str, n: int) -> MarketBundle:
        source = bundles[asset]
        return MarketBundle(
            asset=asset,
            frame=source.frame.iloc[:n],
            peers={name: frame.iloc[:n] for name, frame in source.peers.items()},
            benchmark=source.benchmark,
        )

    return _make


@pytest.fixture(scope="session")
def loaded(dataset_dir):
    """Bundle produced through the real loader, exercising dataset.py."""
    bundle, report = load_bundle(dataset_dir, "ETH")
    return bundle, report
