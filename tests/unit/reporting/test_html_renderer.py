
"""Contract tests for the self-contained P4 HTML report renderer."""

from __future__ import annotations

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

