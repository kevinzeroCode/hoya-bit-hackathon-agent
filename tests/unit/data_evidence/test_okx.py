"""Tests for the OKX daily candles adapter (second independent exchange source)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

from hoya_agent.adapters.okx import INDEPENDENCE_GROUP, fetch_okx_daily
from hoya_agent.data.types import MarketBar

UTC = timezone.utc
AS_OF = datetime(2026, 6, 3, tzinfo=UTC)


def _candle(day: date, o: float, h: float, low: float, c: float, v: float, confirm: str = "1") -> list:
    open_ms = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    # OKX row: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    return [str(open_ms), f"{o}", f"{h}", f"{low}", f"{c}", f"{v}", "0", "0", confirm]


# OKX returns newest-first; the adapter must sort ascending and drop the rest.
DATA = {
    "code": "0",
    "msg": "",
    "data": [
        _candle(date(2026, 6, 5), 118, 130, 117, 125, 30),              # after AS_OF -> excluded
        _candle(date(2026, 6, 3), 118, 121, 110, 119, 25, confirm="0"),  # not closed -> excluded
        _candle(date(2026, 6, 2), 105, 120, 104, 118, 20),
        _candle(date(2026, 6, 1), 100, 110, 95, 105, 10),
    ],
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_candles_sorted_closed_and_within_cutoff():
    bars, degradation = fetch_okx_daily(
        "BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=DATA))
    )
    assert all(isinstance(b, MarketBar) for b in bars)
    assert [b.date for b in bars] == [date(2026, 6, 1), date(2026, 6, 2)]  # sorted; 6/5 & unconfirmed 6/3 excluded
    assert bars[0].close == 105.0
    assert INDEPENDENCE_GROUP == "okx.com"


def test_symbol_mapping_and_utc_bar_in_request():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=DATA)

    fetch_okx_daily("ETH", analysis_as_of=AS_OF, client=_client(handler))
    assert "ETH-USDT" in captured["url"]
    assert "1Dutc" in captured["url"]  # UTC-aligned daily, matches organizer CSV


def test_unsupported_asset_raises():
    with pytest.raises(ValueError):
        fetch_okx_daily("DOGE", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(200, json=DATA)))


def test_error_code_is_degradation():
    bars, degradation = fetch_okx_daily(
        "BTC", analysis_as_of=AS_OF,
        client=_client(lambda r: httpx.Response(200, json={"code": "50011", "msg": "rate limit", "data": []})),
    )
    assert bars == []
    assert degradation


def test_http_error_is_degradation_not_crash():
    bars, degradation = fetch_okx_daily(
        "BTC", analysis_as_of=AS_OF, client=_client(lambda r: httpx.Response(500))
    )
    assert bars == []
    assert degradation
