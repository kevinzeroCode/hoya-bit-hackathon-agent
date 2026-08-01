"""Tests for the prohibited-advice backstop."""

from __future__ import annotations

import pytest

from skills.lint import ProhibitedAdviceError, assert_no_advice, find_prohibited_terms


def test_clean_descriptive_text_passes_through_unchanged():
    text = "BTC 收盤 73,674.39，低於 MA200 約 7.4%，波動處於自身歷史第 2 百分位。"

    assert assert_no_advice(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "目前價位可考慮買入",
        "建議賣出部分持有",
        "適合做多",
        "可於此區間進場",
        "設定停損於 68000",
        "本文提供投資建議",
        "建議配置 5% 於此資產",
    ],
)
def test_advice_phrasing_is_rejected(text):
    with pytest.raises(ProhibitedAdviceError):
        assert_no_advice(text)


def test_error_names_the_offending_term_and_shows_context():
    with pytest.raises(ProhibitedAdviceError) as excinfo:
        assert_no_advice("分析顯示波動壓縮，因此建議買入並持有至下季。")

    assert "買入" in excinfo.value.found
    assert "買入" in str(excinfo.value)


def test_all_offending_terms_are_reported_not_just_the_first():
    found = find_prohibited_terms("先買入再做空，並設定停損")

    assert {"買入", "做空", "停損"} <= set(found)


def test_clean_text_reports_no_terms():
    assert find_prohibited_terms("波動百分位為 0.02") == []


def test_the_lint_is_strict_enough_to_catch_its_own_disclaimer():
    """A negated mention still trips it -- the check is substring-based.

    This is intended: failing closed on a phrasing it cannot parse is safer
    than attempting to distinguish an assertion from its negation, and it is
    why report text avoids the term entirely rather than disclaiming it.
    """
    with pytest.raises(ProhibitedAdviceError):
        assert_no_advice("本文不含任何投資建議。")
