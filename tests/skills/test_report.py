"""Tests for dataset loading and combined report assembly."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from skills import (
    DEGRADED,
    OK,
    UNAVAILABLE,
    build_report,
    load_bundle,
    render_report,
    run_skills,
)
from skills.base import MarketBundle
from skills.dataset import DatasetError
from skills.lint import find_prohibited_terms
from skills.report import SKILL_ORDER

# --------------------------------------------------------------------------
# dataset loading
# --------------------------------------------------------------------------

def test_loader_returns_bundle_peers_and_integrity(loaded):
    bundle, report = loaded

    assert bundle.asset == "ETH"
    assert bundle.bars == 1826
    assert set(bundle.peers) == {"BTC", "SOL", "BNB", "XRP"}
    assert report.integrity.is_clean
    assert report.peers_missing == ()


def test_loader_slices_to_as_of_and_reports_that_it_did(dataset_dir):
    bundle, report = load_bundle(dataset_dir, "BTC", as_of=date(2025, 1, 31))

    assert bundle.as_of == date(2025, 1, 31)
    assert report.truncated_to_as_of
    assert bundle.frame.index.max() == pd.Timestamp("2025-01-31")


def test_as_of_slicing_applies_to_peers_too(dataset_dir):
    """A peer left un-sliced would leak future bars into the attribution."""
    bundle, _ = load_bundle(dataset_dir, "ETH", as_of=date(2025, 1, 31))

    for frame in bundle.peers.values():
        assert frame.index.max() <= pd.Timestamp("2025-01-31")


def test_missing_asset_raises_but_missing_peer_does_not(dataset_dir):
    with pytest.raises(DatasetError):
        load_bundle(dataset_dir, "DOGE")

    bundle, report = load_bundle(dataset_dir, "BTC", peers=("ETH", "DOGE"))

    assert "DOGE" in report.peers_missing
    assert "ETH" in report.peers_loaded
    assert "DOGE" not in bundle.peers


def test_as_of_before_the_series_start_is_rejected(dataset_dir):
    with pytest.raises(DatasetError, match="no bars"):
        load_bundle(dataset_dir, "BTC", as_of=date(2000, 1, 1))


# --------------------------------------------------------------------------
# report assembly
# --------------------------------------------------------------------------

def test_report_runs_every_skill_in_order(bnb):
    report = build_report(bnb)

    assert tuple(r.skill_id for r in report.results) == SKILL_ORDER


def test_report_contains_every_section(bnb):
    report = build_report(bnb)

    for result in report.results:
        assert f"### {result.skill_id}" in report.markdown


def test_report_carries_no_advice_language(bundles):
    for asset in ("BTC", "BNB", "XRP"):
        assert find_prohibited_terms(build_report(bundles[asset]).markdown) == []


def test_report_states_the_as_of_and_sample_size(bnb):
    report = build_report(bnb)

    assert "2026-05-31" in report.markdown
    assert "1826 根" in report.markdown


def test_coverage_table_shows_degraded_status_honestly(bnb):
    """A9 has no sources, so the table must not present the run as complete."""
    report = build_report(bnb)

    assert report.statuses["A9"] == DEGRADED
    assert "部分降級" in report.markdown


def test_btc_report_marks_attribution_unavailable_rather_than_omitting_it(btc):
    """The benchmark cannot be attributed against itself; the gap is shown."""
    report = build_report(btc)

    assert report.statuses["A5"] == UNAVAILABLE
    assert "### A5" in report.markdown
    assert "不可得" in report.markdown


def test_combined_limitations_are_deduplicated_and_attributed(bnb):
    report = build_report(bnb)
    tail = report.markdown.split("## 總體限制與揭露")[1]

    assert "（A7）" in tail
    assert "（A9）" in tail
    lines = [line for line in tail.splitlines() if line.startswith("- ")]
    assert len(lines) == len(set(lines))


def test_report_can_run_a_subset_of_skills(bnb):
    report = build_report(bnb, skill_ids=("A1", "A3"))

    assert tuple(r.skill_id for r in report.results) == ("A1", "A3")
    assert "### A5" not in report.markdown


def test_result_lookup_by_skill_id(bnb):
    report = build_report(bnb)

    assert report.result("A1").skill_id == "A1"
    assert report.result("A8") is None


def test_a_broken_skill_does_not_take_the_report_with_it(bnb, monkeypatch):
    """Skills are not supposed to raise; the report survives it if one does."""
    from skills import report as report_module

    def explode(bundle):
        raise RuntimeError("simulated skill failure")

    monkeypatch.setitem(report_module.SKILL_RUNNERS, "A3", explode)
    results = run_skills(bnb)

    statuses = {r.skill_id: r.status for r in results}
    assert statuses["A3"] == UNAVAILABLE
    assert statuses["A1"] in (OK, DEGRADED)
    assert len(results) == len(SKILL_ORDER)


def test_report_is_deterministic(bnb):
    """Same input, same as_of, byte-identical output."""
    assert build_report(bnb).markdown == build_report(bnb).markdown


def test_report_on_a_thin_bundle_still_renders(bundles):
    """Five bars: nothing can be reported in full, and the document says so.

    A2 still returns ``degraded`` rather than ``unavailable`` -- it needs only
    two bars and honestly reports the handful of figures it can derive.
    """
    thin = MarketBundle(asset="BTC", frame=bundles["BTC"].frame.iloc[:5], peers={})
    report = build_report(thin)

    assert all(r.status in (DEGRADED, UNAVAILABLE) for r in report.results)
    assert not any(r.status == OK for r in report.results)
    assert report.statuses["A1"] == UNAVAILABLE
    assert "## 產出覆蓋狀態" in report.markdown
    assert find_prohibited_terms(report.markdown) == []


def test_render_report_accepts_precomputed_results(bnb):
    results = run_skills(bnb, ("A1", "A2"))
    markdown = render_report(bnb, results)

    assert "### A1" in markdown
    assert "### A3" not in markdown
