"""Unit tests for the deterministic PDF export (Task 20).

`pypdf` is not listed separately in pyproject.toml — it is a transitive
dependency of `xhtml2pdf`, which is a direct dependency, so its presence is
guaranteed by the same lockstep. Used here only to prove round-trip
correctness (the PDF's text layer actually contains the source text), not as
an additional runtime dependency of `hoya_agent` itself.
"""

from __future__ import annotations

import io

import pytest

from hoya_agent.reporting.pdf_renderer import markdown_to_pdf_html, render_pdf


def test_headings_tables_bullets_and_inline_formatting_convert():
    md = (
        "# HOYA 市場分析報告\n\n"
        "| 項目 | 內容 |\n|---|---|\n| Run ID | `run_001` |\n\n"
        "> 本報告不含投資建議。\n\n"
        "## 1. 直接回答\n\n"
        "BTC 過去 14 日呈現小幅回落。\n\n"
        "- **`cl_001`**（confidence：high）BTC 下跌。\n"
        "  - 時間範圍：2026-05-17 ~ 2026-05-31\n"
        "- 另一筆 [連結文字](https://example.com/x)\n"
    )
    html = markdown_to_pdf_html(md)

    assert "<h1>HOYA 市場分析報告</h1>" in html
    assert "<h2>1. 直接回答</h2>" in html
    assert "<th>項目</th>" in html and "<th>內容</th>" in html
    assert "<td><code>run_001</code></td>" in html
    assert "<blockquote>本報告不含投資建議。</blockquote>" in html
    assert "<li>" in html and "</ul>" in html
    assert "<b>" in html and "<code>cl_001</code>" in html
    assert '<a href="https://example.com/x">連結文字</a>' in html


def test_output_is_a_single_self_contained_html_document():
    html = markdown_to_pdf_html("# 標題\n\n內容段落。\n")
    assert html.startswith("<html>")
    assert "<style>" in html
    assert html.count("<html>") == 1


def test_render_pdf_produces_valid_pdf_bytes_with_correct_cjk_text_layer():
    md = "# HOYA 市場分析報告\n\nBTC 過去 14 日呈現小幅回落，屬於量能放大下的區間整理。\n"
    pdf_bytes = render_pdf(md)

    assert pdf_bytes.startswith(b"%PDF")

    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    extracted = reader.pages[0].extract_text()
    assert "HOYA 市場分析報告" in extracted
    assert "量能放大下的區間整理" in extracted


def test_render_pdf_covers_every_report_section_end_to_end(result, ledger):
    """Runs the exact same Markdown `final_report.md` gets, through the exact
    same PDF path, and confirms nothing was silently dropped or re-summarized —
    every claim/evidence ID that appears in the Markdown also appears in the
    PDF's extracted text layer."""
    from hoya_agent.reporting.renderer import render

    md = render(result, ledger)
    pdf_bytes = render_pdf(md)

    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    extracted = "\n".join(page.extract_text() for page in reader.pages)

    for item in ledger.items:
        assert item.evidence_id in extracted
    for claim in result.claims:
        assert claim.claim_id in extracted


def test_empty_report_does_not_crash():
    html = markdown_to_pdf_html("")
    assert html.startswith("<html>")
    pdf_bytes = render_pdf("# 空報告\n")
    assert pdf_bytes.startswith(b"%PDF")
