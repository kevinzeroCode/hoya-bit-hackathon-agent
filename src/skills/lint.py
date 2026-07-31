"""Last-line check that generated report text contains no investment advice.

The analysis layer describes what the data shows; recommending an action is
a different act, and this package must never perform it. Every rendered
section passes through here before it can be returned, so a phrasing slip in
one template cannot reach a report.

This is a blunt substring check on purpose. It is a backstop for text that is
already deterministic and template-generated, not a general-purpose classifier.
"""

from __future__ import annotations

PROHIBITED_TERMS: tuple[str, ...] = (
    # position actions
    "買入", "買進", "賣出", "賣掉", "買超", "賣超",
    "加倉", "減倉", "加碼", "減碼", "建倉", "平倉", "補倉",
    "做多", "做空", "放空", "軋空",
    "進場", "出場", "抄底", "逃頂",
    # targets and risk instructions
    "停損", "停利", "目標價", "支撐價位可承接", "槓桿",
    # explicit advice framing
    "投資建議", "操作建議", "交易建議", "應該買", "應該賣",
    "值得買", "可以買", "可以賣", "建議持有", "建議配置", "資產配置",
)


class ProhibitedAdviceError(AssertionError):
    """Raised when generated text contains investment-advice language."""

    def __init__(self, found: list[str], excerpt: str) -> None:
        self.found = found
        super().__init__(
            f"generated text contains prohibited advice terms {found}; excerpt: {excerpt!r}"
        )


def find_prohibited_terms(text: str) -> list[str]:
    """Return every prohibited term present, in declaration order."""
    return [term for term in PROHIBITED_TERMS if term in text]


def assert_no_advice(text: str) -> str:
    """Return ``text`` unchanged, or raise if it reads as advice.

    Raising rather than scrubbing is deliberate: silently deleting the phrase
    would leave a sentence that no longer says what its author intended, and
    hide a template that needs fixing.
    """
    found = find_prohibited_terms(text)
    if found:
        first = text.find(found[0])
        excerpt = text[max(0, first - 40) : first + 40]
        raise ProhibitedAdviceError(found, excerpt)
    return text
