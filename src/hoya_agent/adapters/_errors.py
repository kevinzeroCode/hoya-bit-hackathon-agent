"""Normalized provider error categories shared by the flat adapters.

Adapters never raise across a port: a failure becomes a degradation note. But a
note alone loses *why* it failed, and `SourceResult.status` has to distinguish a
timeout from a 500 from a malformed body. So each adapter tags its note with a
stable category token, and the port wrapper reads it back.

The token is appended in a fixed bracketed form so the human-readable part of the
note stays first and stays quotable in the report.
"""

from __future__ import annotations

from xml.etree.ElementTree import ParseError

import httpx

CATEGORY_TIMEOUT = "timeout"
CATEGORY_HTTP_ERROR = "http_error"
CATEGORY_MALFORMED = "malformed"
CATEGORY_REJECTED = "rejected"

_PREFIX = "category="


def classify_error(exc: BaseException) -> str:
    """Map a provider exception onto one normalized category."""
    if isinstance(exc, httpx.TimeoutException):
        return CATEGORY_TIMEOUT
    if isinstance(exc, httpx.HTTPError):
        # Includes HTTPStatusError and the transport errors; both mean "the
        # provider did not give us a usable response".
        return CATEGORY_HTTP_ERROR
    if isinstance(exc, ParseError | ValueError | KeyError | TypeError):
        return CATEGORY_MALFORMED
    return CATEGORY_HTTP_ERROR


def category_note(message: str, category: str) -> str:
    """A degradation note carrying its normalized category."""
    return f"{message} [{_PREFIX}{category}]"


def category_of(notes: object) -> str | None:
    """First category token found in a sequence of degradation notes, if any."""
    if not notes:
        return None
    for note in notes:  # type: ignore[union-attr]
        text = str(note)
        start = text.rfind(f"[{_PREFIX}")
        if start == -1:
            continue
        end = text.find("]", start)
        if end == -1:
            continue
        return text[start + len(_PREFIX) + 1 : end]
    return None
