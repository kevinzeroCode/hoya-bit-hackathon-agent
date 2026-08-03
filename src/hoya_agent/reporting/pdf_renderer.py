"""Deterministic PDF export (Task 20), derived from the same rendered text
`final_report.md` already contains — not a second source of truth for facts
or numbers, and no LLM re-generation.

`xhtml2pdf`'s CSS support is 2.1-era: no CSS variables, no grid/flexbox, no
`clamp()`, and even shorthand like `.1em` (missing the leading `0`) crashes
its parser. Feeding it `reporting/html_renderer.py`'s screen stylesheet
raises outright (confirmed empirically — unresolved `var(--x)` calls reach
reportlab's color parser and blow up, and even after resolving those, other
modern CSS still crashes it deeper in text-fragment handling). Rather than
force-fit a screen stylesheet built for browsers onto a PDF library that
cannot render it, this module converts the plain, already-deterministic
Markdown text into a small, xhtml2pdf-safe HTML subset with a literal-value
stylesheet — same content, a different, print-safe presentation.

This is a special-purpose converter, not a general Markdown implementation:
it only needs to handle the exact patterns `reporting/renderer.py` emits
(headings, GFM tables, bullets, blockquotes, inline bold/code/links), which
is a bounded, known set — not the full CommonMark grammar.
"""

from __future__ import annotations

import io
import re
from html import escape

_INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_INLINE_BOLD = re.compile(r"\*\*([^*]+)\*\*")

#: The report is contractually Traditional Chinese (Features.md §3). xhtml2pdf's
#: base-14 PDF fonts (Helvetica/Courier/...) have no CJK glyphs at all — every
#: Chinese character silently renders as a missing-glyph box, confirmed
#: empirically. `MSung-Light` is one of Adobe's standard, always-available CJK
#: CID fonts (no TTF file to bundle or license): registering it once here is
#: enough for every viewer that has any Traditional Chinese font installed,
#: which is effectively universal.
_CJK_FONT = "MSung-Light"

_CSS = f"""
body{{font-family:{_CJK_FONT};font-size:10pt;color:#151815;line-height:1.5}}
h1{{font-family:{_CJK_FONT};font-size:18pt;margin:0 0 12pt}}
h2{{font-family:{_CJK_FONT};font-size:13pt;color:#087f5b;border-bottom:1pt solid #d8d8cf;
padding-bottom:4pt;margin:18pt 0 8pt}}
p{{margin:6pt 0}}
ul{{margin:4pt 0;padding-left:16pt}}
li{{margin:3pt 0}}
table{{width:100%;border-collapse:collapse;font-size:8pt;margin:8pt 0}}
th,td{{font-family:{_CJK_FONT};border-bottom:0.5pt solid #d8d8cf;padding:4pt;text-align:left;vertical-align:top}}
th{{color:#767d75;font-size:7pt;text-transform:uppercase}}
code{{font-family:Courier,monospace;color:#2867b2}}
blockquote{{font-family:{_CJK_FONT};margin:8pt 0;padding:6pt 10pt;border-left:2pt solid #d8d8cf;color:#4e544e}}
a{{color:#2867b2}}
"""


def _register_cjk_font() -> None:
    """Idempotent: `pdfmetrics` keeps a process-wide font registry, so a
    second call from another render in the same process is a harmless no-op
    rather than a duplicate-registration error."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    if _CJK_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(_CJK_FONT))


def _inline(text: str) -> str:
    """Escape then re-apply the three inline forms `renderer.py` emits."""
    text = escape(text)
    text = _INLINE_LINK.sub(r'<a href="\2">\1</a>', text)
    text = _INLINE_CODE.sub(r"<code>\1</code>", text)
    text = _INLINE_BOLD.sub(r"<b>\1</b>", text)
    return text


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def _is_table_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


def _table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def markdown_to_pdf_html(markdown_text: str) -> str:
    """Convert `renderer.py`'s deterministic Markdown output into a small,
    xhtml2pdf-safe HTML document. Handles exactly the patterns that renderer
    emits: `#`/`##` headings, GFM tables, `-`/`  -` bullets (one nesting
    level), `>` blockquotes, plain paragraphs, and inline bold/code/links.
    """
    lines = markdown_text.splitlines()
    body: list[str] = []
    i = 0
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            close_list()
            i += 1
            continue

        if stripped.startswith("# "):
            close_list()
            body.append(f"<h1>{_inline(stripped[2:])}</h1>")
            i += 1
            continue

        heading_match = re.match(r"^##\s+(.+)$", stripped)
        if heading_match:
            close_list()
            body.append(f"<h2>{_inline(heading_match.group(1))}</h2>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_list()
            body.append(f"<blockquote>{_inline(stripped.lstrip('> ').strip())}</blockquote>")
            i += 1
            continue

        if _is_table_row(stripped):
            close_list()
            header = _table_cells(stripped)
            i += 1
            if i < len(lines) and _is_table_separator(lines[i]):
                i += 1
            rows: list[list[str]] = []
            while i < len(lines) and _is_table_row(lines[i].strip()):
                rows.append(_table_cells(lines[i].strip()))
                i += 1
            head_html = "".join(f"<th>{_inline(c)}</th>" for c in header)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            body.append(f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>")
            continue

        bullet_match = re.match(r"^(\s*)-\s+(.+)$", line)
        if bullet_match:
            if not in_list:
                body.append("<ul>")
                in_list = True
            indent = "&nbsp;&nbsp;&nbsp;&nbsp;" if bullet_match.group(1) else ""
            body.append(f"<li>{indent}{_inline(bullet_match.group(2))}</li>")
            i += 1
            continue

        close_list()
        body.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    close_list()
    return f"<html><head><style>{_CSS}</style></head><body>{''.join(body)}</body></html>"


def render_pdf(markdown_text: str) -> bytes:
    """Render `markdown_text` (the same text written to `final_report.md`) to
    PDF bytes. Raises `ValueError` on any rendering failure — an optional
    export must never claim success it did not achieve.
    """
    from xhtml2pdf import pisa

    _register_cjk_font()
    html = markdown_to_pdf_html(markdown_text)
    buf = io.BytesIO()
    status = pisa.CreatePDF(html, dest=buf)
    if status.err:
        raise ValueError(f"PDF generation failed with {status.err} error(s)")
    return buf.getvalue()
