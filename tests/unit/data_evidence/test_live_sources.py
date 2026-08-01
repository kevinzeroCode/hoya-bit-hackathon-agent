"""Live source composition wrappers (network-free via monkeypatch)."""

from __future__ import annotations

from datetime import datetime, timezone
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


def test_fear_greed_drafts_returns_drafts_and_degradation(monkeypatch):
    result = SimpleNamespace(status="ok", drafts=["fng-draft"], degradation=["note"])

    async def _fake(**k):
        return result

    monkeypatch.setattr(live_sources, "fetch_fear_greed", _fake)
    drafts, degradation = live_sources.fear_greed_drafts(_NOW)()
    assert drafts == ["fng-draft"]
    assert degradation == ["note"]
