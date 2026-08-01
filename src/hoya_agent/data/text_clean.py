"""Deterministic text cleaning for news bodies before the LLM sees them.

Strips HTML tags, unescapes entities, and collapses whitespace. This is the
"把資料處理乾淨" step: the LLM receives clean prose, not markup or boilerplate.
No LLM, no network.
"""

from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")


def clean_text(raw: str | None) -> str:
    if not raw:
        return ""
    no_tags = _TAG.sub(" ", raw)
    unescaped = html.unescape(no_tags)
    return " ".join(unescaped.split())
