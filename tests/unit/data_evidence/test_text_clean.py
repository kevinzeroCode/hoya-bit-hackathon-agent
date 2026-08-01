"""Tests for deterministic news-text cleaning (before the LLM sees it)."""

from __future__ import annotations

from hoya_agent.data.text_clean import clean_text


def test_strips_html_tags():
    assert clean_text("<p>Bitcoin ETF <b>inflows</b> hit record</p>") == "Bitcoin ETF inflows hit record"


def test_unescapes_entities():
    assert clean_text("BTC &amp; ETH &lt;news&gt;") == "BTC & ETH <news>"


def test_collapses_whitespace():
    assert clean_text("line one\n\n   line   two\t\tend") == "line one line two end"


def test_empty_and_none():
    assert clean_text("") == ""
    assert clean_text(None) == ""  # type: ignore[arg-type]
