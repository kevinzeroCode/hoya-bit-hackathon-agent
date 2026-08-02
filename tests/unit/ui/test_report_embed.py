"""The Streamlit report frame is content-sized, not an inner scrolling page.

Sizing the iframe alone leaves its element container at the declared height and
the report overlaps the layout below it, so the embed must go through
`st.iframe(height="content")`, which sizes the container too. `_embeddable_report`
is the only place the TOC script enters the document — the downloadable
`final_report.html` artifact must stay free of it.
"""

from __future__ import annotations

import pytest

from hoya_agent.ui import streamlit_app
from hoya_agent.ui.streamlit_app import _TOC_MARKER, _embed_report, _embeddable_report

_DOC = '<!doctype html><html><body><div class="shell">報告</div></body></html>'


def test_toc_script_is_injected_once_before_body_close() -> None:
    embedded = _embeddable_report(_DOC)

    assert embedded.count(_TOC_MARKER) == 1
    assert embedded.index(_TOC_MARKER) < embedded.index("</body>")


def test_embedding_preserves_the_original_document() -> None:
    embedded = _embeddable_report(_DOC)

    # everything up to the injection point is byte-identical, and the document
    # still closes normally
    assert embedded.startswith('<!doctype html><html><body><div class="shell">報告</div>')
    assert embedded.endswith("</body></html>")


def test_fragment_without_body_still_gets_the_script() -> None:
    assert _TOC_MARKER in _embeddable_report("<div>報告</div>")


def test_embedding_is_deterministic() -> None:
    assert _embeddable_report(_DOC) == _embeddable_report(_DOC)


def test_injected_script_resends_the_measurement() -> None:
    """Streamlit posts a size only when it *changes*, and a srcdoc frame can load
    before the host attaches its listener — losing the one measurement and leaving
    a short frame with an inner scrollbar. The nudge must perturb the height and
    restore it, so a changed size is posted after the listener exists."""
    script = _embeddable_report(_DOC)

    assert "paddingBottom = '1px'" in script
    assert "paddingBottom = ''" in script
    assert "setTimeout(nudge" in script


class _FakeStreamlit:
    """Records which embed API was used and with what sizing."""

    def __init__(self, *, with_iframe: bool) -> None:
        self.calls: list[tuple[str, str, object]] = []
        if with_iframe:
            self.iframe = self._iframe

    def _iframe(self, html: str, *, height: object) -> None:
        self.calls.append(("iframe", html, height))

    class _V1:
        def __init__(self, outer: "_FakeStreamlit") -> None:
            self._outer = outer

        def html(self, html: str, *, height: object, scrolling: bool) -> None:
            self._outer.calls.append(("components", html, height))

    @property
    def components(self):  # noqa: D102 - mirrors st.components.v1.html
        return type("_C", (), {"v1": self._V1(self)})


@pytest.fixture
def fake_st(monkeypatch):
    def _install(*, with_iframe: bool) -> _FakeStreamlit:
        fake = _FakeStreamlit(with_iframe=with_iframe)
        monkeypatch.setattr(streamlit_app, "st", fake)
        return fake

    return _install


def test_report_is_content_sized_so_it_cannot_overlap_the_layout(fake_st) -> None:
    fake = fake_st(with_iframe=True)

    _embed_report(_DOC)

    (api, html, height), = fake.calls
    assert api == "iframe"
    assert height == "content"  # sizes the element container, not just the frame
    assert _TOC_MARKER in html


def test_older_streamlit_falls_back_to_the_fixed_height_component(fake_st) -> None:
    """`pyproject` allows streamlit>=1.36, which predates `st.iframe`."""
    fake = fake_st(with_iframe=False)

    _embed_report(_DOC)

    (api, html, height), = fake.calls
    assert api == "components"
    assert height == 1100  # bounded viewport: scrolls internally, never overlaps
    assert _TOC_MARKER in html
