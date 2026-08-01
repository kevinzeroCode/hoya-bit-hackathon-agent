"""Prohibited investment-advice string lint.

Deterministic, dependency-free. Encodes the report-safety rule from
`.kiro/steering/competition-rules.md` ("禁止明確買入、賣出、加倉、減倉、資產配置、
下單或個人化投資建議;Renderer 必須執行字串 lint") and `.kiro/steering/testing.md`
(禁止「建議買入」「建議賣出」「加倉」「減倉」「做多」「做空」).

Used as the `lint` hook for `reporting.renderer.render` and as the UI/output-level
safety assertion for the Bronze (S3) surface. The list is intentionally coin-agnostic
and stanceless: it forbids prescriptive action/allocation language, not analysis.
"""

from __future__ import annotations

from collections.abc import Sequence

# Prescriptive action / allocation / order / price-prediction phrasing only.
#
# Deliberately NOT bare directional verbs like "買入" / "賣出": those appear in
# legitimate stanceless facts ("某巨鯨買入 5,000 BTC"), and the deterministic
# report's own disclaimer ("...也不提供投資建議。") legitimately contains "投資建議".
# Flagging those would fire on safe text. We forbid the *prescriptive framing*:
# an explicit recommendation, a position/allocation action, an order type, or a
# price target. Sourced from `.kiro/steering/testing.md` (§Report 與安全 lint) and
# `.kiro/steering/competition-rules.md` (§Report Safety Rules).
PROHIBITED_ADVICE_TERMS: tuple[str, ...] = (
    "建議買入",
    "建議賣出",
    "建議買進",
    "建議加碼",
    "建議減碼",
    "建議做多",
    "建議做空",
    "建議持倉",
    "加倉",
    "減倉",
    "做多",
    "做空",
    "資產配置",
    "個人化投資建議",
    "下單",
    "止損",
    "停損",
    "停利",
    "目標價",
    "buy signal",
    "sell signal",
    "price target",
)


def advice_violations(text: str) -> Sequence[str]:
    """Return the prohibited terms present in ``text`` (empty tuple = clean).

    Matches the `LintHook = Callable[[str], Sequence[str]]` contract in
    `reporting.renderer`, so it can be passed straight in as `render(..., lint=...)`.
    """
    lowered = text.casefold()
    hits: list[str] = []
    for term in PROHIBITED_ADVICE_TERMS:
        needle = term.casefold()
        if needle in lowered and term not in hits:
            hits.append(term)
    return tuple(hits)
