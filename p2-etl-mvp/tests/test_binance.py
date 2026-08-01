"""Tests for the Binance daily klines adapter (live market source)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

from adapters.binance import fetch_binance_daily
from data.types import MarketBar

UTC = timezone.utc
AS_OF = datetime(2026, 6, 3, tzinfo=UTC)


def _kline(day: date, o: float, h: float, low: float, c: float, v: float) -> list:
    open_ms = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    close_ms = open_ms + 86_400_000 - 1
    return [open_ms, f"{o}", f"{h}", f"{low}", f"{c}", f"{v}", close_ms, "0", 0, "0", "0", "0"]


KLINES = [
    _kline(date(2026, 6, 1), 100, 110, 95, 105, 10),
    _kline(date(2026, 6, 2), 105, 120, 104, 118, 20),
    _kline(date(2026, 6, 5), 118, 130, 117, 125, 30),  # closes after AS_OF -> excluded
]


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_klines_into_marketbars_up_to_as_of():
    bars, degradation = fetch_binance_daily("BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=KLINES)))
    assert all(isinstance(b, MarketBar) for b in bars)
    assert [b.date for b in bars] == [date(2026, 6, 1), date(2026, 6, 2)]  # 6/5 excluded
    assert bars[0].close == 105.0


def test_symbol_mapping_in_request():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=KLINES)

    fetch_binance_daily("ETH", analysis_as_of=AS_OF, client=_client(handler))
    assert "ETHUSDT" in captured["url"]


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_binance_daily("DOGE", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=KLINES)))


def test_http_error_is_degradation_not_crash():
    bars, degradation = fetch_binance_daily("BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500)))
    assert bars == []
    assert degradation
