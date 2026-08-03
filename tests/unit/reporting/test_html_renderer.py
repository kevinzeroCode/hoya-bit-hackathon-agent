
"""Contract tests for the self-contained P4 HTML report renderer."""

from __future__ import annotations

from hoya_agent.models import (
    ConsistencyDimension,
    FreshnessDimension,
    ReliabilityMix,
    SourceDiversityDimension,
    SourceIndependenceDimension,
    TrustLevel,
    TrustScorecard,
)
from hoya_agent.reporting.advice_lint import advice_violations
from hoya_agent.reporting.html_renderer import render_html


def test_html_report_is_complete_self_contained_and_traceable(result, ledger) -> None:
    report = render_html(result, ledger, lint=advice_violations)

    assert report.startswith("<!doctype html>")
    assert '<html lang="zh-Hant"' in report
    assert '<meta charset="utf-8">' in report
    for section_id in (
        "answer",
        "market",
        "reasoning",
        "evidence",
        "trust",
        "limits",
        "watch",
        "ledger",
        "reproduce",
    ):
        assert f'<section id="{section_id}">' in report
    for claim in result.claims:
        assert claim.claim_id in report
    for item in ledger.items:
        assert item.evidence_id in report

    assert "@media print" in report
    assert "prefers-reduced-motion" in report
    assert "data-theme=\"light\"" in report
    assert "window.print()" in report
    assert "<link" not in report
    assert "src=" not in report
    assert "fetch(" not in report
    assert "XMLHttpRequest" not in report


def test_html_report_escapes_all_dynamic_text(result, ledger) -> None:
    unsafe = '<script>alert("x")</script>'
    changed = result.model_copy(update={"question": unsafe, "direct_answer": unsafe})

    report = render_html(changed, ledger)

    assert unsafe not in report
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in report


def test_html_report_is_deterministic(result, ledger) -> None:
    first = render_html(result, ledger, terminal_state="degraded")
    second = render_html(result, ledger, terminal_state="degraded")
    assert first == second


def test_html_report_artifact_carries_no_streamlit_embed_script(result, ledger) -> None:
    """The downloadable artifact stays portable: the Streamlit frame-sizing
    script is injected by the UI layer only, never by the renderer."""
    assert "hoya-report-toc" not in render_html(result, ledger)


def test_html_report_preserves_run_mode_disclosure(result, ledger) -> None:
    report = render_html(result, ledger)
    assert "rehearsal 可重現資料結果" in report
    assert "不得標示為 live official" in report


def _trust_scorecard(claim_id: str) -> TrustScorecard:
    return TrustScorecard(
        claim_id=claim_id,
        source_independence=SourceIndependenceDimension(level=TrustLevel.strong, distinct_groups=3),
        source_diversity=SourceDiversityDimension(level=TrustLevel.moderate, distinct_source_types=2),
        reliability_mix=ReliabilityMix(high=2, medium=1, low=0),
        consistency=ConsistencyDimension(
            level=TrustLevel.weak, has_material_conflict=True, opposing_count=1
        ),
        freshness=FreshnessDimension(level=TrustLevel.strong, has_stale=False, newest_evidence_age_hours=2.0),
        rationale="測試用 rationale",
    )


def test_trust_section_renders_a_radar_svg_per_conclusion_scorecard(result, ledger) -> None:
    """Task 20 additional visualization: one deterministic SVG radar chart per
    conclusion's Trust Scorecard, not just a text/pip summary."""
    conclusion_id = result.claims[-1].claim_id
    with_card = result.model_copy(update={"trust_scorecards": [_trust_scorecard(conclusion_id)]})

    report = render_html(with_card, ledger)

    assert "<svg" in report
    assert f'aria-label="Trust Scorecard radar for {conclusion_id}"' in report
    # Five axis labels, one per Trust Scorecard dimension.
    for axis in ("獨立性", "多樣性", "可信度", "一致性", "時效性"):
        assert axis in report
    # No raster/remote image and no new script surface introduced by the chart.
    assert "src=" not in report
    assert "<script" not in report or "window.print()" in report  # only the pre-existing print button


def test_trust_section_omits_the_radar_when_no_scorecard_exists(result, ledger) -> None:
    """No conclusion scorecard (e.g. an insufficient-data run) must degrade to
    the existing text-only summary, never a fabricated or empty chart."""
    without_cards = result.model_copy(update={"trust_scorecards": []})
    assert "<svg" not in render_html(without_cards, ledger)


def test_trust_radar_renders_one_svg_per_conclusion_when_there_are_several(result, ledger) -> None:
    cards = [_trust_scorecard(result.claims[-1].claim_id), _trust_scorecard(result.claims[-1].claim_id)]
    report = render_html(result.model_copy(update={"trust_scorecards": cards}), ledger)
    assert report.count("<svg") == 2

