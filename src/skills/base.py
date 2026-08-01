"""Shared contract every analysis skill implements.

A skill takes prepared market data and returns one ``SkillResult``: the
numbers, what they were derived from, what could not be determined, and a
ready-to-render Traditional Chinese section.

Two rules hold across every skill:

* **A skill never raises.** Missing or insufficient data is an outcome to be
  reported, not an exception. Anything else lets one thin series abort a
  whole report.
* **A skill never invents a number.** Where a figure cannot be computed the
  field is absent and a limitation says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

OK = "ok"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EvidenceRef:
    """Provenance for a single computed figure.

    Deliberately *not* an ``EvidenceItem``: the real schema (with
    ``fetched_at``, ``content_hash``, ``independence_group``) is owned
    elsewhere. This carries the raw material a mapping to it would need, so
    that mapping stays mechanical rather than reconstructive.
    """

    ref_id: str
    metric: str
    value: Any
    computed_by: str
    window_bars: int | None = None
    source_type: str = "market"
    reliability: str = "high"


@dataclass(frozen=True)
class SkillResult:
    """One analysis output, ready either to render or to convert to evidence."""

    skill_id: str
    skill_name: str
    asset: str
    as_of: date | None
    status: str
    findings: dict[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[EvidenceRef, ...] = ()
    limitations: tuple[str, ...] = ()
    section_markdown: str = ""

    @property
    def is_usable(self) -> bool:
        return self.status in (OK, DEGRADED)

    @property
    def section_html(self) -> str:
        """The same section as HTML, derived from ``section_markdown``.

        Derived rather than separately templated: a second renderer would let
        the HTML and Markdown disagree about a number, which is the one thing
        this package must never do.
        """
        from .html_report import render_section_html

        return render_section_html(self)


@dataclass(frozen=True)
class MarketBundle:
    """Prepared inputs for a skill.

    Skills receive this rather than a path, so they stay pure and testable:
    all file reading happens in ``dataset.py``.
    """

    asset: str
    frame: pd.DataFrame
    peers: dict[str, pd.DataFrame] = field(default_factory=dict)
    benchmark: str = "BTC"

    @property
    def close(self) -> pd.Series:
        return self.frame["close"]

    @property
    def high(self) -> pd.Series:
        return self.frame["high"]

    @property
    def low(self) -> pd.Series:
        return self.frame["low"]

    @property
    def volume(self) -> pd.Series:
        return self.frame["volume"]

    @property
    def bars(self) -> int:
        return len(self.frame)

    @property
    def as_of(self) -> date | None:
        if self.frame.empty:
            return None
        last = self.frame.index[-1]
        return last.date() if isinstance(last, pd.Timestamp) else None

    def benchmark_close(self) -> pd.Series | None:
        """Benchmark closes, or ``None`` when this asset *is* the benchmark.

        Correlating an asset with itself yields 1.0 and means nothing, so the
        caller is forced to handle the case rather than publish a tautology.
        """
        if self.asset == self.benchmark:
            return None
        peer = self.peers.get(self.benchmark)
        return None if peer is None else peer["close"]


def unavailable(
    skill_id: str,
    skill_name: str,
    bundle: MarketBundle,
    reason: str,
) -> SkillResult:
    """Build the standard 'could not be determined' result.

    The reason is rendered into the section too: a reader of the report sees
    the gap and why it exists, rather than a silently missing heading.
    """
    return SkillResult(
        skill_id=skill_id,
        skill_name=skill_name,
        asset=bundle.asset,
        as_of=bundle.as_of,
        status=UNAVAILABLE,
        findings={},
        evidence_refs=(),
        limitations=(reason,),
        section_markdown=f"### {skill_id} {skill_name}\n\n無法產出：{reason}\n",
    )


# --------------------------------------------------------------------------
# formatting helpers (rendering rounds; calculations keep full precision)
# --------------------------------------------------------------------------

def fmt_pct(value: float | None, digits: int = 2, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "不可得"
    return f"{value * 100:+.{digits}f}%" if signed else f"{value * 100:.{digits}f}%"


def fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "不可得"
    return f"{value:,.{digits}f}"


def fmt_ratio(value: float | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "不可得"
    return f"{value:.{digits}f}"


def bullet(label: str, value: str, note: str = "") -> str:
    return f"- {label}：{value}" + (f"（{note}）" if note else "")


def render_section(skill_id: str, name: str, lines: list[str], limitations: tuple[str, ...]) -> str:
    """Assemble a section; limitations are part of the section, not an appendix."""
    body = "\n".join(lines) if lines else "無可用數值。"
    text = f"### {skill_id} {name}\n\n{body}\n"
    if limitations:
        text += "\n**限制與揭露**\n\n" + "\n".join(f"- {item}" for item in limitations) + "\n"
    return text
