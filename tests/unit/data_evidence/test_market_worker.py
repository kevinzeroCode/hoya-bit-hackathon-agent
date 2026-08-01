"""Tests for the Market Worker: indicators -> traceable EvidenceDraft (no LLM)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from hoya_agent.adapters.organizer_csv import (
    INDEPENDENCE_GROUP,
    default_data_dir,
    load_organizer_csv,
)
from hoya_agent.data.indicators import simple_return
from hoya_agent.data.market_series import closes
from hoya_agent.data.market_worker import WorkerResult, build_market_evidence
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.types import EvidenceDraft

RETURN = "return_14d"
VOL = "realized_vol_30d"
MDD = "max_drawdown_90d"
VZ = "volume_zscore_30d"


def make_bars(n: int, start: date = date(2026, 1, 1)) -> list[MarketBar]:
    bars = []
    for i in range(n):
        c = 100.0 + i  # varying closes -> non-zero return variance
        bars.append(MarketBar(start + timedelta(days=i), c, c + 1, c - 1, c, 1000.0 + i))
    return bars


def test_completed_produces_four_drafts():
    bars = make_bars(120)
    result = build_market_evidence("BTC", bars, analysis_as_of=bars[-1].date)
    assert isinstance(result, WorkerResult)
    assert result.status == "completed"
    assert {d.metric_name for d in result.drafts} == {RETURN, VOL, MDD, VZ}


def test_draft_is_traceable_high_reliability_market():
    bars = make_bars(120)
    drafts = build_market_evidence("ETH", bars, analysis_as_of=bars[-1].date).drafts
    for d in drafts:
        assert isinstance(d, EvidenceDraft)
        assert d.asset == "ETH"
        assert d.source_type == "market"
        assert d.reliability == "high"
        assert d.independence_group == INDEPENDENCE_GROUP
        assert d.normalized_fact.strip()
        assert d.content_reference.strip()
        assert d.query_or_parameters.strip()
        assert d.fetched_at.tzinfo is not None  # timezone-aware UTC


def test_return_value_matches_indicator():
    bars = make_bars(120)
    drafts = build_market_evidence("BTC", bars, analysis_as_of=bars[-1].date).drafts
    ret = next(d for d in drafts if d.metric_name == RETURN)
    assert ret.metric_value == pytest.approx(simple_return(closes(bars), 14))


def test_partial_when_only_some_windows_fit():
    bars = make_bars(20)  # enough for return(15) only
    result = build_market_evidence("SOL", bars, analysis_as_of=bars[-1].date)
    assert result.status == "partial"
    assert {d.metric_name for d in result.drafts} == {RETURN}
    assert result.degradation  # at least one gap disclosed


def test_failed_when_no_metric_computable():
    bars = make_bars(5)
    result = build_market_evidence("XRP", bars, analysis_as_of=bars[-1].date)
    assert result.status == "failed"
    assert result.drafts == []
    assert result.degradation


def test_respects_analysis_as_of():
    bars = make_bars(100)
    as_of = bars[49].date  # keep only first 50 bars
    result = build_market_evidence("BNB", bars, analysis_as_of=as_of)
    ret = next(d for d in result.drafts if d.metric_name == RETURN)
    assert ret.metric_value == pytest.approx(simple_return(closes(bars[:50]), 14))


@pytest.mark.skipif(
    not (default_data_dir() / "BTC_daily_ohlcv.csv").exists(),
    reason="organizer dataset not reachable",
)
def test_real_btc_return_draft_matches_golden():
    bars = load_organizer_csv(default_data_dir() / "BTC_daily_ohlcv.csv")
    result = build_market_evidence("BTC", bars, analysis_as_of=date(2026, 5, 31))
    ret = next(d for d in result.drafts if d.metric_name == RETURN)
    assert ret.metric_value == pytest.approx(-0.048843, abs=1e-6)
    assert ret.reliability == "high"
