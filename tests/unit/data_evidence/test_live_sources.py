"""Live source composition wrappers (network-free via monkeypatch)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from hoya_agent.adapters import live_sources

UTC = timezone.utc
_NOW = datetime(2026, 8, 1, tzinfo=UTC)


def test_binance_loader_returns_bars(monkeypatch):
    sentinel = ["bar-a", "bar-b"]

    async def _fake(*a, **k):  # fetch_binance_daily is async (httpx.AsyncClient)
        return (sentinel, [])

    monkeypatch.setattr(live_sources, "fetch_binance_daily", _fake)
    load = live_sources.binance_bar_loader(_NOW)
    assert list(load("BTC")) == sentinel


def test_binance_loader_raises_when_empty_so_pipeline_degrades(monkeypatch):
    async def _fake(*a, **k):
        return ([], ["Binance fetch failed"])

    monkeypatch.setattr(live_sources, "fetch_binance_daily", _fake)
    load = live_sources.binance_bar_loader(_NOW)
    with pytest.raises(ValueError, match="Binance fetch failed"):
        load("BTC")


def test_binance_loader_prefers_local_cache(tmp_path: Path, monkeypatch):
    cache = tmp_path / "BTC_daily_ohlcv.csv"
    cache.write_text(
        "date,open,high,low,close,volume\n2026-07-31,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    async def _unexpected(*a, **k):
        raise AssertionError("cache hit must not call Binance")

    monkeypatch.setattr(live_sources, "fetch_binance_daily", _unexpected)
    load = live_sources.binance_bar_loader(_NOW, cache_dir=tmp_path)
    assert load("BTC")[0].close == 1.5


def test_fear_greed_drafts_returns_drafts_and_degradation(monkeypatch):
    result = SimpleNamespace(status="ok", drafts=["fng-draft"], degradation=["note"])

    async def _fake(**k):
        return result

    monkeypatch.setattr(live_sources, "fetch_fear_greed", _fake)
    drafts, degradation = live_sources.fear_greed_drafts(_NOW)()
    assert drafts == ["fng-draft"]
    assert degradation == ["note"]


def test_coingecko_drafts_fetches_every_asset_and_merges_results(monkeypatch):
    calls: list[str] = []

    async def _fake(asset, **k):
        calls.append(asset)
        return SimpleNamespace(drafts=[f"cg-{asset}"], degradation=[])

    monkeypatch.setattr(live_sources, "fetch_coingecko_price", _fake)
    drafts, degradation = live_sources.coingecko_drafts(["BTC", "ETH"])()
    assert calls == ["BTC", "ETH"]
    assert drafts == ["cg-BTC", "cg-ETH"]
    assert degradation == []


def test_coingecko_drafts_one_asset_failing_does_not_drop_the_others(monkeypatch):
    async def _fake(asset, **k):
        if asset == "ETH":
            return SimpleNamespace(drafts=[], degradation=["ETH failed"])
        return SimpleNamespace(drafts=[f"cg-{asset}"], degradation=[])

    monkeypatch.setattr(live_sources, "fetch_coingecko_price", _fake)
    drafts, degradation = live_sources.coingecko_drafts(["BTC", "ETH"])()
    assert drafts == ["cg-BTC"]
    assert degradation == ["ETH failed"]


def test_combine_extra_drafts_concatenates_every_factory():
    a = lambda: (["a-draft"], ["a-note"])  # noqa: E731 - test-local, no signature to name
    b = lambda: ([], ["b-note"])  # noqa: E731

    drafts, degradation = live_sources.combine_extra_drafts(a, b)()
    assert drafts == ["a-draft"]
    assert degradation == ["a-note", "b-note"]


def test_combine_extra_drafts_with_no_factories_is_empty():
    assert live_sources.combine_extra_drafts()() == ([], [])
