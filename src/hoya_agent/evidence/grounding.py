"""Deterministic fact-grounding: does an LLM-extracted fact trace to its source?

The Research Agent uses Claude to turn raw article text into `normalized_fact`
strings. This module audits that output *without an LLM* — it extracts the
language-invariant "hard atoms" from a fact (percentages, money amounts, dates,
tickers) and checks each one actually appears in the source excerpt
(`content_reference`). Numbers and precise dates are exactly what an LLM most
often fabricates, and they are checkable with string/tolerance matching across
languages (an English source "fell 8%" grounds a Chinese fact "下跌 8%").

Deliberately dependency-free and LLM-free:
- Respects the `evidence/` boundary (🚫 no `boto3`/`httpx`) — the optional
  semantic check of purely-qualitative claims lives in the reasoning layer
  behind the `LLMClient` port, not here.
- Does NOT mutate static `reliability` (design.md: reliability is static and
  never dynamically rewritten). Grounding routes into confidence caps and
  honest disclosure instead.
- Adds no field to the frozen `EvidenceDraft`/`EvidenceItem` schema: verdicts
  are returned alongside the drafts, never stored on them.

The deterministic pass emits `verified` / `partial` / `unverified`;
`contradicted` requires the semantic (LLM) check and is not produced here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from hoya_agent.evidence.drafts import PendingEvidence

# Only audit facts an LLM extracted from free text. Market/official facts are
# deterministic tool output (or verified announcements), not LLM paraphrase.
LLM_EXTRACTED_SOURCE_TYPES: frozenset[str] = frozenset({"news", "social"})

# Tickers are deliberately NOT grounding atoms: an English source says "Bitcoin"
# where the fact says "BTC", so absence is not evidence of fabrication. We only
# audit the fabrication-prone, language-invariant atoms below.
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
_DATE_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DATE_CJK = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
# Bare numbers worth checking: has a decimal, a thousands separator, or ≥ 100.
# Small integers ("2 weeks", "3 sources") are too noisy to treat as claims.
_NUMBER = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?![\w%])")


class GroundingStatus(str, Enum):
    verified = "verified"      # every checkable hard atom appears in the source
    partial = "partial"        # some hard atom is absent → likely fabricated value
    unverified = "unverified"  # no deterministically checkable atom → defer to semantic check


@dataclass(frozen=True)
class GroundingVerdict:
    status: GroundingStatus
    unverified_atoms: tuple[str, ...] = ()
    note: str = ""


def _norm_number(token: str) -> float:
    return float(token.replace(",", ""))


def _source_numbers(source: str) -> list[float]:
    """Every numeric token in the source, comma-stripped, as floats."""
    out: list[float] = []
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", source):
        try:
            out.append(_norm_number(m.group(0)))
        except ValueError:
            continue
    return out


def _number_present(value: float, source_nums: Sequence[float]) -> bool:
    """Match with rounding tolerance: 7.9 grounds "約 8", 8 grounds "7.9%"."""
    for s in source_nums:
        if abs(value - s) < 1e-9 or abs(value - s) <= 0.5 or round(value) == round(s):
            return True
    return False


def _iso_dates(source: str) -> set[str]:
    dates = set(_DATE_ISO.findall(source))
    for y, mo, d in _DATE_CJK.findall(source):
        dates.add(f"{int(y):04d}-{int(mo):02d}-{int(d):02d}")
    return dates


def _fact_dates(fact: str) -> list[str]:
    dates = list(_DATE_ISO.findall(fact))
    for y, mo, d in _DATE_CJK.findall(fact):
        dates.append(f"{int(y):04d}-{int(mo):02d}-{int(d):02d}")
    return dates


def _checkable_atoms(fact: str) -> list[tuple[str, str, float | None]]:
    """(kind, display, numeric-value-or-None) for each hard atom in the fact.

    Percent, money and date spans are removed before bare-number extraction so a
    date's year (2026) or a percentage's digits are not double-counted as numbers.
    """
    atoms: list[tuple[str, str, float | None]] = []
    for pct in _PERCENT.findall(fact):
        atoms.append(("percent", f"{pct}%", _norm_number(pct)))
    for amt in _MONEY.findall(fact):
        atoms.append(("money", f"${amt}", _norm_number(amt)))
    for d in _fact_dates(fact):
        atoms.append(("date", d, None))

    residual = _PERCENT.sub(" ", fact)
    residual = _MONEY.sub(" ", residual)
    residual = _DATE_ISO.sub(" ", residual)
    residual = _DATE_CJK.sub(" ", residual)
    for num in _NUMBER.findall(residual):
        value = _norm_number(num)
        if "." in num or "," in num or value >= 100:  # skip noisy small integers
            atoms.append(("number", num, value))
    return atoms


def ground_fact(normalized_fact: str, content_reference: str) -> GroundingVerdict:
    """Verify a single extracted fact against its source excerpt (deterministic)."""
    atoms = _checkable_atoms(normalized_fact)
    if not atoms:
        return GroundingVerdict(
            GroundingStatus.unverified,
            note="無可確定性查核的原子(純質性),待語意複核",
        )

    source_nums = _source_numbers(content_reference)
    source_dates = _iso_dates(content_reference)
    missing: list[str] = []
    for kind, display, value in atoms:
        if kind in ("percent", "money", "number"):
            assert value is not None
            if not _number_present(value, source_nums):
                missing.append(display)
        elif kind == "date":
            if display not in source_dates:
                missing.append(display)

    if missing:
        return GroundingVerdict(
            GroundingStatus.partial,
            unverified_atoms=tuple(missing),
            note="以下數值/日期未在原文出現,疑似模型自行補寫:" + "、".join(missing),
        )
    return GroundingVerdict(GroundingStatus.verified)


def ground_drafts(
    drafts: Iterable[PendingEvidence],
    *,
    verify_source_types: frozenset[str] = LLM_EXTRACTED_SOURCE_TYPES,
) -> tuple[list[tuple[PendingEvidence, GroundingVerdict]], list[str]]:
    """Audit every LLM-extracted draft; return (draft, verdict) pairs + notes.

    Non-mutating: frozen drafts are returned untouched. Market/official drafts
    are passed through as `verified` (deterministic tool output, not paraphrase).
    Disclosure notes are collected for `degradation_notes` / the execution log.
    """
    results: list[tuple[PendingEvidence, GroundingVerdict]] = []
    notes: list[str] = []
    for draft in drafts:
        source_type = str(getattr(draft.source_type, "value", draft.source_type))
        if source_type not in verify_source_types:
            results.append((draft, GroundingVerdict(GroundingStatus.verified)))
            continue
        verdict = ground_fact(draft.normalized_fact, draft.content_reference)
        results.append((draft, verdict))
        if verdict.status is GroundingStatus.partial:
            notes.append(f"{draft.draft.source_name}:{verdict.note}")
    return results, notes
