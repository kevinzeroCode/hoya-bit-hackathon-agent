"""Tests for HTML rendering.

The central guarantee is that HTML and Markdown describe the same numbers,
because one is derived from the other. Several tests below exist to make sure
that derivation is never quietly replaced with a second set of templates.
"""

from __future__ import annotations

import re

import pytest

from skills import (
    build_report,
    markdown_subset_to_html,
    render_report_html,
    render_section_html,
)
from skills.html_report import STATUS_LABEL
from skills.lint import ProhibitedAdviceError, find_prohibited_terms
from skills.report import SKILL_ORDER

TAGS = re.compile(r"<[^>]+>")


def strip_tags(html: str) -> str:
    return TAGS.sub("", html)


# --------------------------------------------------------------------------
# the converter
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "markdown,expected",
    [
        ("# 標題", "<h1>標題</h1>"),
        ("## 標題", "<h2>標題</h2>"),
        ("### A1 名稱", "<h3>A1 名稱</h3>"),
    ],
)
def test_headings(markdown, expected):
    assert markdown_subset_to_html(markdown) == expected


def test_bullets_become_a_list():
    html = markdown_subset_to_html("- 甲\n- 乙")

    assert html == "<ul>\n<li>甲</li>\n<li>乙</li>\n</ul>"


def test_indented_bullets_nest():
    html = markdown_subset_to_html("- 外層\n  - 內層")

    assert html.count("<ul>") == 2
    assert html.count("</ul>") == 2
    assert "<li>內層</li>" in html


def test_inline_bold_and_code():
    html = markdown_subset_to_html("值為 `mixed`，屬 **重要** 判定")

    assert "<code>mixed</code>" in html
    assert "<strong>重要</strong>" in html


def test_pipe_table_drops_the_separator_row():
    html = markdown_subset_to_html("| 產出 | 狀態 |\n|---|---|\n| A1 | 完成 |")

    assert "<th>產出</th>" in html
    assert "<td>A1</td>" in html
    assert "---" not in html
    assert html.count("<tr>") == 2


def test_table_is_horizontally_scrollable():
    """Wide tables must scroll in their own container, not the page body."""
    html = markdown_subset_to_html("| a | b |\n|---|---|\n| 1 | 2 |")

    assert 'class="scroll"' in html


def test_bold_only_paragraph_becomes_a_subheading():
    html = markdown_subset_to_html("**限制與揭露**")

    assert html == '<h4 class="lim">限制與揭露</h4>'


def test_blank_lines_separate_paragraphs():
    html = markdown_subset_to_html("第一段\n\n第二段")

    assert html.count("<p>") == 2


def test_consecutive_lines_join_into_one_paragraph():
    html = markdown_subset_to_html("前半\n後半")

    assert html == "<p>前半 後半</p>"


def test_markup_in_content_is_escaped_not_emitted():
    """Content can never introduce tags: escaping happens before formatting."""
    html = markdown_subset_to_html("- <script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_ampersand_is_escaped():
    assert "&amp;" in markdown_subset_to_html("- A & B")


def test_empty_input_produces_empty_output():
    assert markdown_subset_to_html("") == ""


def test_mixed_blocks_all_survive_in_order():
    source = "### 標題\n\n- 項目\n\n段落\n\n| a |\n|---|\n| 1 |"
    html = markdown_subset_to_html(source)

    assert html.index("<h3>") < html.index("<ul>") < html.index("<p>") < html.index("<table>")


# --------------------------------------------------------------------------
# section rendering
# --------------------------------------------------------------------------

@pytest.mark.parametrize("skill_id", SKILL_ORDER)
def test_every_skill_renders_a_section_with_a_status_badge(bnb, skill_id):
    result = build_report(bnb).result(skill_id)
    html = result.section_html

    assert html.startswith("<section")
    assert f"is-{result.status}" in html
    assert STATUS_LABEL[result.status] in html


def test_section_html_is_available_directly_on_the_result(bnb):
    result = build_report(bnb).result("A1")

    assert result.section_html == render_section_html(result)


def test_badge_is_attached_to_the_heading(bnb):
    html = build_report(bnb).result("A1").section_html

    assert re.search(r"<h3>.*<span class=\"badge[^\"]*\">.*</span></h3>", html)


def test_unavailable_section_still_renders(btc):
    """A5 is unavailable for the benchmark; the gap must still be visible."""
    result = build_report(btc).result("A5")

    assert result.status == "unavailable"
    assert "is-unavailable" in result.section_html
    assert "無法產出" in strip_tags(result.section_html)


# --------------------------------------------------------------------------
# whole document
# --------------------------------------------------------------------------

def test_document_is_self_contained(bnb):
    """No external stylesheet, script, font or image may be referenced."""
    html = build_report(bnb).html

    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    for pattern in ("http://", "https://", "<script", "<link", "src="):
        assert pattern not in html


def test_document_declares_encoding_language_and_viewport(bnb):
    html = build_report(bnb).html

    assert 'charset="utf-8"' in html
    assert 'lang="zh-Hant"' in html
    assert "viewport" in html


def test_document_supports_both_colour_schemes(bnb):
    assert "prefers-color-scheme:dark" in build_report(bnb).html


def test_document_contains_every_section_and_the_coverage_table(bnb):
    report = build_report(bnb)
    text = strip_tags(report.html)

    for result in report.results:
        assert result.skill_id in text
        assert result.skill_name in text
    assert "產出覆蓋狀態" in text
    assert "總體限制與揭露" in text


def test_html_and_markdown_report_the_same_numbers(bundles):
    """The whole point of deriving one from the other.

    Every numeric token in the Markdown must appear in the HTML text too.
    """
    number = re.compile(r"-?\d[\d,]*\.?\d*%?")

    for asset in ("BTC", "BNB", "XRP"):
        report = build_report(bundles[asset])
        html_text = strip_tags(report.html)
        for token in set(number.findall(report.markdown)):
            assert token in html_text, f"{asset}: {token!r} missing from HTML"


def test_html_carries_no_advice_language(bundles):
    for asset in ("BTC", "BNB", "XRP"):
        assert find_prohibited_terms(build_report(bundles[asset]).html) == []


def test_html_rendering_is_deterministic(bnb):
    assert build_report(bnb).html == build_report(bnb).html


def test_html_respects_a_skill_subset(bnb):
    report = build_report(bnb, skill_ids=("A1", "A3"))

    assert "A5" not in strip_tags(report.html)
    assert report.html.count("<section") == 2


def test_lint_runs_over_the_assembled_html(bnb, monkeypatch):
    """A phrasing problem introduced during assembly must not slip through."""
    from skills import html_report

    monkeypatch.setattr(
        html_report, "_document", lambda title, body: f"<html>{body} 建議買入</html>"
    )

    with pytest.raises(ProhibitedAdviceError):
        render_report_html(bnb, build_report(bnb).results)


def test_thin_bundle_still_produces_a_valid_document(bundles):
    from skills.base import MarketBundle

    thin = MarketBundle(asset="BTC", frame=bundles["BTC"].frame.iloc[:5], peers={})
    html = build_report(thin).html

    assert html.startswith("<!doctype html>")
    assert html.count("<section") == len(SKILL_ORDER)
    assert find_prohibited_terms(html) == []
