"""Prohibited investment-advice lint (competition-rules §Report Safety Rules)."""

from __future__ import annotations

import pytest

from hoya_agent.reporting.advice_lint import advice_violations


def test_clean_analysis_text_has_no_violations():
    text = (
        "# 加密市場分析\n"
        "BTC 過去 14 日報酬為 -4.9%(來源:public_market_data,證據 EV-001)。\n"
        "已實現波動偏高;方向性結論待進一步證據。\n"
        "本報告為研究導向,不含任何模型自行補寫的數值,也不提供投資建議。\n"
    )
    assert advice_violations(text) == ()


def test_factual_directional_language_is_not_flagged():
    """Bare directional verbs in stanceless facts must pass (only prescriptive framing fails)."""
    assert advice_violations("鏈上數據顯示某巨鯨買入 5,000 BTC,另有地址賣出 ETH。") == ()


@pytest.mark.parametrize(
    "phrase",
    ["建議買入", "建議賣出", "加倉", "減倉", "做多", "做空", "資產配置", "下單", "目標價", "個人化投資建議"],
)
def test_each_prohibited_phrase_is_caught(phrase):
    assert phrase in advice_violations(f"分析結論:{phrase}此標的。")


def test_english_signal_language_is_caught_case_insensitively():
    assert "buy signal" in advice_violations("This is a BUY SIGNAL.")


def test_multiple_violations_are_all_reported():
    hits = advice_violations("建議買入並加倉,提供個人化投資建議。")
    assert {"建議買入", "加倉", "個人化投資建議"} <= set(hits)
