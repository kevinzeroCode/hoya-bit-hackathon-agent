"""Tests for the seven analysis skills.

Golden values come from ``docs/price-data-analysis-outputs.html`` (as of
2026-05-31), already independently verified against the CSVs. Beyond the
numbers, these tests enforce the contract that matters most: a skill degrades
honestly instead of inventing a figure, and never raises.
"""

from __future__ import annotations

import pytest

from skills import (
    DEGRADED,
    OK,
    UNAVAILABLE,
    a1_regime,
    a2_position,
    a3_risk,
    a4_participation,
    a5_attribution,
    a7_analogs,
    a9_verification,
)
from skills.base import MarketBundle
from skills.lint import find_prohibited_terms

ALL_ASSETS = ("BTC", "ETH", "SOL", "BNB", "XRP")
ALL_RUNNERS = (
    a1_regime.run,
    a2_position.run,
    a3_risk.run,
    a4_participation.run,
    a5_attribution.run,
    a7_analogs.run,
    a9_verification.run,
)


# --------------------------------------------------------------------------
# A1 regime
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,label",
    [("BTC", "mixed"), ("ETH", "trending_down"), ("SOL", "range_bound"),
     ("BNB", "trending_up"), ("XRP", "range_bound")],
)
def test_a1_reproduces_the_spec_labels(bundles, asset, label):
    """Exercises the §16.3 rule order end to end against real data."""
    result = a1_regime.run(bundles[asset])

    assert result.findings["label"] == label


def test_a1_persists_the_metrics_and_thresholds_it_used(bundles):
    result = a1_regime.run(bundles["BTC"])

    assert result.findings["metrics"]["return_window"] == pytest.approx(-0.0582, abs=5e-5)
    assert result.findings["metrics"]["realized_vol_pctile"] == pytest.approx(0.016, abs=0.005)
    assert result.findings["thresholds"] == {
        "trend_return_abs_min": 0.10,
        "range_return_abs_max": 0.05,
        "high_vol_pctile": 0.80,
    }


def test_a1_assignment_order_puts_volatility_first():
    """High volatility wins even when the return would imply a trend."""
    assert a1_regime.assign_label(0.50, 0.95) == "high_volatility"
    assert a1_regime.assign_label(0.50, 0.10) == "trending_up"
    assert a1_regime.assign_label(-0.50, 0.10) == "trending_down"
    assert a1_regime.assign_label(0.01, 0.10) == "range_bound"
    assert a1_regime.assign_label(0.07, 0.10) == "mixed"


def test_a1_discloses_the_compression_the_enum_cannot_express(bundles):
    """The label says range_bound; the data says bottom-of-range volatility."""
    result = a1_regime.run(bundles["XRP"])

    assert result.findings["label"] == "range_bound"
    assert result.findings["compression"]["status"] == "compressed"
    assert result.status == DEGRADED
    assert any("無低波動" in item for item in result.limitations)


def test_a1_does_not_invent_a_label_outside_the_spec_enum(bundles):
    allowed = {"trending_up", "trending_down", "range_bound", "high_volatility", "mixed"}

    for asset in ALL_ASSETS:
        assert a1_regime.run(bundles[asset]).findings["label"] in allowed


def test_a1_unavailable_without_enough_bars(truncated):
    result = a1_regime.run(truncated("BTC", 100))

    assert result.status == UNAVAILABLE
    assert result.findings == {}
    assert "未達" in result.limitations[0]


# --------------------------------------------------------------------------
# A2 position
# --------------------------------------------------------------------------

def test_a2_matches_reported_position_figures(bundles):
    result = a2_position.run(bundles["BTC"])

    assert result.findings["ma_distance"][200] == pytest.approx(-0.0740, abs=5e-4)
    assert result.findings["ath_close"] == pytest.approx(124658.54)
    assert str(result.findings["ath_close_date"]) == "2025-10-06"
    assert result.findings["days_since_ath_close"] == 237


def test_a2_reports_both_drawdown_bases_separately(bundles):
    """The document conflates these two; the skill must not."""
    result = a2_position.run(bundles["BTC"])

    assert result.findings["drawdown_from_ath_close"] == pytest.approx(-0.4090, abs=5e-4)
    assert result.findings["drawdown_from_ath_high"] == pytest.approx(-0.4162, abs=5e-4)
    assert any("兩者不可混用" in item for item in result.limitations)


def test_a2_degrades_per_metric_rather_than_wholesale(truncated):
    """Losing MA200 must not also cost the report MA20."""
    result = a2_position.run(truncated("BTC", 60))

    assert result.status == DEGRADED
    assert result.findings["ma_distance"][20] is not None
    assert result.findings["ma_distance"][50] is not None
    assert result.findings["ma_distance"][200] is None


def test_a2_survives_a_two_bar_series(truncated):
    result = a2_position.run(truncated("BTC", 2))

    assert result.status in (DEGRADED, UNAVAILABLE)


# --------------------------------------------------------------------------
# A3 risk
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,vol,percentile",
    [("BTC", 0.250, 0.02), ("ETH", 0.286, 0.00), ("SOL", 0.393, 0.00),
     ("BNB", 0.455, 0.37), ("XRP", 0.342, 0.02)],
)
def test_a3_matches_reported_volatility(bundles, asset, vol, percentile):
    result = a3_risk.run(bundles[asset])

    assert result.findings["realized_volatility_30d"] == pytest.approx(vol, abs=5e-4)
    assert result.findings["volatility_percentile"] == pytest.approx(percentile, abs=0.005)


def test_a3_matches_reported_tail_shape(bundles):
    btc = a3_risk.run(bundles["BTC"]).findings
    xrp = a3_risk.run(bundles["XRP"]).findings

    assert btc["return_skew"] == pytest.approx(-0.20, abs=0.01)
    assert btc["return_excess_kurtosis"] == pytest.approx(3.86, abs=0.05)
    assert xrp["return_skew"] == pytest.approx(1.36, abs=0.01)
    assert xrp["return_excess_kurtosis"] == pytest.approx(18.55, abs=0.05)


def test_a3_matches_reported_atr(bundles):
    result = a3_risk.run(bundles["BTC"])

    assert result.findings["atr14"] == pytest.approx(1718.77, rel=1e-3)
    assert result.findings["atr14_ratio"] == pytest.approx(0.0233, abs=5e-4)


def test_a3_unavailable_below_the_volatility_window(truncated):
    result = a3_risk.run(truncated("BTC", 10))

    assert result.status == UNAVAILABLE


# --------------------------------------------------------------------------
# A4 participation
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,ratio,percentile",
    [("BTC", 0.74, 0.02), ("ETH", 0.55, 0.08), ("SOL", 0.67, 0.05),
     ("BNB", 0.64, 0.07), ("XRP", 0.64, 0.02)],
)
def test_a4_matches_reported_volume_figures(bundles, asset, ratio, percentile):
    """Ratio and percentile are distinct quantities; both are asserted."""
    result = a4_participation.run(bundles[asset])

    assert result.findings["volume_mean_ratio"] == pytest.approx(ratio, abs=0.005)
    assert result.findings["volume_mean_percentile"] == pytest.approx(percentile, abs=0.006)


def test_a4_identifies_the_single_volume_confirmed_advance(bundles):
    directions = {a: a4_participation.run(bundles[a]).findings["direction"] for a in ALL_ASSETS}

    assert directions["BNB"] == "up_on_rising_volume"
    assert [a for a, d in directions.items() if d == "up_on_rising_volume"] == ["BNB"]


def test_a4_shortens_the_baseline_window_rather_than_dropping_the_section(truncated):
    result = a4_participation.run(truncated("BTC", 200))

    assert result.status == DEGRADED
    assert result.findings["long_window"] == 90
    assert any("視窗已縮短" in item for item in result.limitations)


def test_a4_always_discloses_the_cross_asset_volume_limit(bundles):
    result = a4_participation.run(bundles["BTC"])

    assert any("跨幣量能不可直接比較" in item for item in result.limitations)


# --------------------------------------------------------------------------
# A5 attribution
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asset,correlation,beta",
    [("ETH", 0.93, 1.23), ("SOL", 0.86, 1.12), ("XRP", 0.86, 0.89), ("BNB", 0.71, 0.72)],
)
def test_a5_matches_reported_correlation_and_beta(bundles, asset, correlation, beta):
    result = a5_attribution.run(bundles[asset])

    assert result.findings["correlation_90d"] == pytest.approx(correlation, abs=0.005)
    assert result.findings["beta_90d"] == pytest.approx(beta, abs=0.005)


def test_a5_refuses_to_correlate_the_benchmark_with_itself(btc):
    """Self-correlation is 1.0 and meaningless; it must not be published."""
    result = a5_attribution.run(btc)

    assert result.status == UNAVAILABLE
    assert "恆為 1" in result.limitations[0]


def test_a5_separates_the_decoupled_asset_from_the_synchronised_ones(bundles):
    assert a5_attribution.run(bundles["BNB"]).findings["relative_strength_percentile_1y"] > 0.5

    for asset in ("ETH", "SOL", "XRP"):
        findings = a5_attribution.run(bundles[asset]).findings
        assert findings["relative_strength_percentile_1y"] < 0.2
        assert findings["correlation_90d"] > 0.85


def test_a5_reading_never_asserts_a_cause(bundles):
    """Price data cannot supply a reason, and the wording must not imply one."""
    section = a5_attribution.run(bundles["BNB"]).section_markdown

    assert "價格資料無法指出該因素為何" in section
    assert any("不表示任一方向的因果關係" in i
               for i in a5_attribution.run(bundles["BNB"]).limitations)


def test_a5_unavailable_without_the_benchmark(bundles):
    lonely = MarketBundle(asset="ETH", frame=bundles["ETH"].frame, peers={}, benchmark="BTC")
    result = a5_attribution.run(lonely)

    assert result.status == UNAVAILABLE


# --------------------------------------------------------------------------
# A7 analogs
# --------------------------------------------------------------------------

def test_a7_defaults_to_the_bias_free_mode(bundles):
    result = a7_analogs.run(bundles["BTC"])

    assert result.findings["mode"] == "expanding"
    assert any("擴張視窗" in item for item in result.limitations)


def test_a7_reports_all_three_sample_measures(bundles):
    """Observations alone would overstate the evidence; all three ship."""
    findings = a7_analogs.run(bundles["BTC"]).findings

    assert findings["observations"] > findings["distinct_episodes"]
    assert findings["effective_n"] < findings["observations"]
    assert findings["distinct_episodes"] > 0


def test_a7_section_states_counts_and_never_a_percentage(bundles):
    """Rates render as hits/total, and the only mention of 機率 forbids it."""
    section = a7_analogs.run(bundles["BTC"]).section_markdown
    body = section.split("**限制與揭露**")[0]

    rate_lines = [line for line in body.splitlines() if "日後" in line]
    assert rate_lines
    for line in rate_lines:
        assert "／" in line  # hits／total
        assert "%" not in line  # never a percentage

    assert "非對未來的預測" in body
    assert "不構成機率陳述" in body


def test_a7_keeps_volatility_and_direction_apart(bundles):
    findings = a7_analogs.run(bundles["BTC"], mode="full_sample").findings

    assert findings["volatility_expansion"]["strength"] == "strong"
    assert findings["direction_up"]["strength"] == "weak"


def test_a7_full_sample_mode_discloses_the_look_ahead(bundles):
    result = a7_analogs.run(bundles["BTC"], mode="full_sample")

    assert any("前視偏誤" in item for item in result.limitations)


def test_a7_unavailable_on_short_history(truncated):
    result = a7_analogs.run(truncated("BTC", 300))

    assert result.status == UNAVAILABLE


# --------------------------------------------------------------------------
# A9 verification
# --------------------------------------------------------------------------

def test_a9_can_never_report_ok_without_sources(bundles):
    """An unverified analysis must not be presentable as a verified one."""
    for asset in ALL_ASSETS:
        result = a9_verification.run(bundles[asset])
        assert result.status == DEGRADED
        assert result.findings["sources_available"] == 0
        assert result.findings["verification_performed"] is False


def test_a9_states_the_missing_capability_explicitly(bundles):
    result = a9_verification.run(bundles["BTC"])

    assert any("無法進行跨來源驗證" in item for item in result.limitations)


def test_a9_flags_unexplained_moves_without_asserting_a_cause(bundles):
    result = a9_verification.run(bundles["XRP"], lookback_days=400)

    assert result.findings["unexplained_moves"]
    assert any("無法指出原因" in item for item in result.limitations)


def test_a9_emits_facts_a_later_narrative_can_be_checked_against(bundles):
    facts = a9_verification.run(bundles["BTC"]).findings["checkable_price_facts"]

    assert facts["return_30d"] == pytest.approx(-0.0582, abs=5e-5)
    assert facts["volatility_percentile"] == pytest.approx(0.016, abs=0.005)
    assert "price_volume_direction" in facts


def test_a9_reports_a_quiet_window_as_quiet(bundles):
    result = a9_verification.run(bundles["BTC"], lookback_days=5)

    assert result.findings["unexplained_moves"] == []
    assert "無超過" in result.section_markdown


# --------------------------------------------------------------------------
# contract held by every skill
# --------------------------------------------------------------------------

@pytest.mark.parametrize("runner", ALL_RUNNERS)
@pytest.mark.parametrize("asset", ALL_ASSETS)
def test_no_skill_emits_advice_language(bundles, runner, asset):
    assert find_prohibited_terms(runner(bundles[asset]).section_markdown) == []


@pytest.mark.parametrize("runner", ALL_RUNNERS)
@pytest.mark.parametrize("bars", [0, 1, 5, 40, 300])
def test_no_skill_raises_on_short_history(truncated, runner, bars):
    """Insufficient data is an outcome to report, never an exception."""
    result = runner(truncated("BTC", bars))

    assert result.status in (OK, DEGRADED, UNAVAILABLE)


@pytest.mark.parametrize("runner", ALL_RUNNERS)
def test_unavailable_results_carry_a_reason_and_no_findings(truncated, runner):
    result = runner(truncated("BTC", 5))

    if result.status == UNAVAILABLE:
        assert result.limitations
        assert not result.findings
        assert "無法產出" in result.section_markdown or result.section_markdown


@pytest.mark.parametrize("runner", ALL_RUNNERS)
def test_every_skill_labels_its_section_and_asset(bundles, runner):
    result = runner(bundles["ETH"])

    assert result.asset == "ETH"
    assert result.skill_id in result.section_markdown
    assert result.skill_name in result.section_markdown


@pytest.mark.parametrize("runner", ALL_RUNNERS)
def test_usable_results_carry_provenance_for_their_figures(bundles, runner):
    result = runner(bundles["ETH"])

    if result.is_usable:
        assert result.evidence_refs
        for ref in result.evidence_refs:
            assert ref.computed_by
            assert ref.reliability == "high"
            assert ref.source_type == "market"
