"""Arbiter: turn a validated Evidence Ledger into one layered AnalysisResult.

This is the only stage that forms a market judgement, and it is bounded on
every side:

- it sees evidence IDs and normalized facts, never raw pages;
- the ledger is truncated to a configured maximum before the call;
- exactly one generation happens (the client owns the single schema repair);
- structural violations reject the output and fall back deterministically;
- deterministic confidence caps are applied afterwards, never loosened.

The result schema is injected rather than imported so this module stays
independent of the shared contracts package. Wire it with the real
``AnalysisResult`` once Task 1 lands.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ValidationError

from hoya_agent.adapters.bedrock import LLMError
from hoya_agent.reasoning.claim_graph import salvage_claim_graph
from hoya_agent.reasoning.prompt_library import load_prompt

#: Hard maximum from design.md 9; configuration may lower it, never raise it.
MAX_EVIDENCE_FOR_ARBITER = 30

#: Ordering used whenever evidence competes for a slot.
RELIABILITY_RANK = {"high": 0, "medium": 1, "low": 2}

CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}


class ArbiterValidationError(Exception):
    """The generated result was structurally unusable and must be discarded."""


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from an object or a mapping."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _reliability_rank(item: Any) -> int:
    return RELIABILITY_RANK.get(str(_attr(item, "reliability", "low")), 3)


def _sort_key(item: Any) -> tuple:
    """Deterministic ordering: reliability, then freshness, then ID."""
    published = _attr(item, "published_at") or _attr(item, "fetched_at")
    return (
        _reliability_rank(item),
        # Newest first; missing timestamps sort last but stay deterministic.
        (published is None, _negated_timestamp(published)),
        str(_attr(item, "evidence_id", "")),
    )


def _negated_timestamp(value: Any) -> str:
    """Invert a lexicographic ISO timestamp so newer sorts first."""
    if value is None:
        return ""
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    # Complement each digit so a plain ascending sort yields newest-first.
    return "".join(str(9 - int(ch)) if ch.isdigit() else ch for ch in text)


def conflict_evidence_ids(indicators: Iterable[Any]) -> set[str]:
    """Every evidence ID named by a deterministic conflict indicator."""
    ids: set[str] = set()
    for indicator in indicators or ():
        for key in ("supporting_evidence_ids", "opposing_evidence_ids"):
            ids.update(str(value) for value in (_attr(indicator, key) or ()))
    return ids


def select_evidence(
    items: Sequence[Any],
    indicators: Iterable[Any] = (),
    limit: int = MAX_EVIDENCE_FOR_ARBITER,
) -> list[Any]:
    """Truncate the ledger to the slots the Arbiter prompt can carry.

    Priority, per design.md 9: keep every ``high``-reliability item, then both
    sides of any material conflict, then fill the remainder while maximizing
    distinct ``independence_group`` values so the prompt stays diverse rather
    than stacking one talkative source.
    """
    effective_limit = max(0, min(limit, MAX_EVIDENCE_FOR_ARBITER))
    ordered = sorted(items, key=_sort_key)
    if len(ordered) <= effective_limit:
        return ordered

    conflicted = conflict_evidence_ids(indicators)
    selected: list[Any] = []
    taken: set[int] = set()

    def take(candidates: Iterable[Any]) -> None:
        for candidate in candidates:
            if len(selected) >= effective_limit:
                return
            if id(candidate) in taken:
                continue
            taken.add(id(candidate))
            selected.append(candidate)

    take(item for item in ordered if _reliability_rank(item) == 0)
    take(item for item in ordered if str(_attr(item, "evidence_id")) in conflicted)

    # Round-robin across independence groups so the tail is diverse.
    by_group: dict[str, deque] = defaultdict(deque)
    for item in ordered:
        if id(item) not in taken:
            by_group[str(_attr(item, "independence_group", ""))].append(item)
    while len(selected) < effective_limit and by_group:
        for group in sorted(by_group):
            queue = by_group[group]
            if queue:
                take([queue.popleft()])
            if len(selected) >= effective_limit:
                break
        by_group = {group: q for group, q in by_group.items() if q}

    return sorted(selected, key=_sort_key)


def build_evidence_payload(items: Sequence[Any]) -> list[dict[str, Any]]:
    """Project evidence down to the fields the prompt is allowed to see."""
    payload = []
    for item in items:
        published = _attr(item, "published_at")
        payload.append(
            {
                "evidence_id": _attr(item, "evidence_id"),
                "asset": _attr(item, "asset"),
                "source_type": _attr(item, "source_type"),
                "source_name": _attr(item, "source_name"),
                "reliability": _attr(item, "reliability"),
                "independence_group": _attr(item, "independence_group"),
                "published_at": (
                    published.isoformat() if hasattr(published, "isoformat") else published
                ),
                "is_stale": bool(_attr(item, "is_stale", False)),
                "normalized_fact": _attr(item, "normalized_fact"),
                "content_reference": _attr(item, "content_reference"),
            }
        )
    return payload


def detect_cycle(claims: Sequence[Any]) -> bool:
    """True when ``based_on_claim_ids`` forms a cycle."""
    graph = {
        str(_attr(claim, "claim_id")): [
            str(dep) for dep in (_attr(claim, "based_on_claim_ids") or ())
        ]
        for claim in claims
    }
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for dep in graph.get(node, ()):
            if dep in graph and visit(dep):
                return True
        state[node] = 2
        return False

    return any(visit(node) for node in graph)


#: Numeric tokens: digits with optional decimal/thousand-separator groups.
_NUMBER_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*")

#: Run-local identifiers whose digits are references, not market values.
_INTERNAL_ID_RE = re.compile(r"\b(?:ev|cl|run)_[0-9A-Za-z_]+")


def _number_tokens(text: Any) -> set[Decimal]:
    """Every numeric value mentioned in ``text``, NFKC-normalized.

    Thousand separators collapse ("68,000" == "68000") and signs are dropped on
    both the claim and the evidence side, so comparison is by magnitude of the
    written token, never by any computation.
    """
    if text is None:
        return set()
    cleaned = _INTERNAL_ID_RE.sub(" ", unicodedata.normalize("NFKC", str(text)))
    tokens: set[Decimal] = set()
    for match in _NUMBER_TOKEN_RE.finditer(cleaned):
        try:
            tokens.add(Decimal(match.group().replace(",", "")))
        except InvalidOperation:  # pragma: no cover - regex admits only digits
            continue
    return tokens


def _evidence_number_pool(item: Any) -> set[Decimal]:
    pool = _number_tokens(_attr(item, "normalized_fact"))
    pool |= _number_tokens(_attr(item, "content_reference"))
    metric_value = _attr(item, "metric_value")
    if metric_value is not None:
        pool |= _number_tokens(str(metric_value))
    return pool


def _time_range_tokens(claim: Any) -> set[Decimal]:
    time_range = _attr(claim, "time_range")
    if time_range is None:
        return set()
    return _number_tokens(_attr(time_range, "start")) | _number_tokens(
        _attr(time_range, "end")
    )


def _number_gaps(
    result: Any, evidence_by_id: Mapping[str, Any]
) -> tuple[dict[str, list[Decimal]], list[Decimal]]:
    """(claim_id -> ungrounded numbers, ungrounded direct-answer numbers).

    A number is grounded when it appears in evidence linked to the claim or to
    one of its transitive upstream claims; the claim's own ``time_range`` dates
    are exempt because the window comes from the plan, not from evidence. The
    direct answer is checked against the whole ledger.
    """
    claims = list(_attr(result, "claims") or ())
    links = list(_attr(result, "claim_evidence_links") or ())

    direct: dict[str, set[str]] = defaultdict(set)
    for link in links:
        direct[str(_attr(link, "claim_id"))].add(str(_attr(link, "evidence_id")))
    deps = {
        str(_attr(claim, "claim_id")): [
            str(dep) for dep in (_attr(claim, "based_on_claim_ids") or ())
        ]
        for claim in claims
    }

    def reachable_pool(claim_id: str) -> set[Decimal]:
        pool: set[Decimal] = set()
        seen: set[str] = set()
        stack = [claim_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for evidence_id in direct.get(current, ()):
                item = evidence_by_id.get(evidence_id)
                if item is not None:
                    pool |= _evidence_number_pool(item)
            stack.extend(deps.get(current, ()))
        return pool

    claim_gaps: dict[str, list[Decimal]] = {}
    all_time_range_tokens: set[Decimal] = set()
    for claim in claims:
        claim_id = str(_attr(claim, "claim_id"))
        exempt = _time_range_tokens(claim)
        all_time_range_tokens |= exempt
        tokens = _number_tokens(_attr(claim, "text")) - exempt
        if not tokens:
            continue
        missing = tokens - reachable_pool(claim_id)
        if missing:
            claim_gaps[claim_id] = sorted(missing)

    answer_tokens = _number_tokens(_attr(result, "direct_answer"))
    answer_tokens -= all_time_range_tokens
    answer_tokens -= _number_tokens(_attr(result, "analysis_as_of"))
    answer_missing: list[Decimal] = []
    if answer_tokens:
        ledger_pool: set[Decimal] = set()
        for item in evidence_by_id.values():
            ledger_pool |= _evidence_number_pool(item)
        answer_missing = sorted(answer_tokens - ledger_pool)
    return claim_gaps, answer_missing


def _asset_gaps(result: Any, evidence_by_id: Mapping[str, Any]) -> dict[str, list[str]]:
    """claim_id -> claim assets for claims whose linked evidence shares no asset.

    Market-wide evidence (``asset=None``, e.g. Fear & Greed) grounds any asset.
    Claims whose links all fail to resolve are left to the unknown-reference
    check rather than double-reported here.
    """
    links = list(_attr(result, "claim_evidence_links") or ())
    linked: dict[str, list[str]] = defaultdict(list)
    for link in links:
        if str(_attr(link, "stance")) in {"supports", "opposes"}:
            linked[str(_attr(link, "claim_id"))].append(
                str(_attr(link, "evidence_id"))
            )

    def plain(value: Any) -> str:
        return str(getattr(value, "value", value))

    gaps: dict[str, list[str]] = {}
    for claim in _attr(result, "claims") or ():
        claim_id = str(_attr(claim, "claim_id"))
        claim_assets = {plain(asset) for asset in (_attr(claim, "assets") or ())}
        if not claim_assets:
            continue
        resolved = [
            evidence_by_id[evidence_id]
            for evidence_id in linked.get(claim_id, ())
            if evidence_id in evidence_by_id
        ]
        if not resolved:
            continue
        matched = any(
            _attr(item, "asset") is None or plain(_attr(item, "asset")) in claim_assets
            for item in resolved
        )
        if not matched:
            gaps[claim_id] = sorted(claim_assets)
    return gaps


def number_provenance_violations(
    result: Any, evidence_by_id: Mapping[str, Any]
) -> list[str]:
    """Numbers in claim texts and the direct answer must be quoted from evidence.

    The Arbiter prompt's first hard rule ("不得自創任何市場數值") becomes a
    deterministic check over `_number_gaps`.
    """
    claim_gaps, answer_missing = _number_gaps(result, evidence_by_id)
    violations = [
        f"claim {claim_id} cites numbers not present in linked evidence: "
        + ", ".join(str(value) for value in missing)
        for claim_id, missing in claim_gaps.items()
    ]
    if answer_missing:
        violations.append(
            "direct_answer cites numbers not present in the evidence ledger: "
            + ", ".join(str(value) for value in answer_missing)
        )
    return violations


def asset_consistency_violations(
    result: Any, evidence_by_id: Mapping[str, Any]
) -> list[str]:
    """Each claim's non-neutral links must include evidence about its assets."""
    return [
        f"claim {claim_id} evidence links share no asset with claim assets {assets}"
        for claim_id, assets in _asset_gaps(result, evidence_by_id).items()
    ]


def semantically_flagged_claim_ids(
    result: Any, evidence_by_id: Mapping[str, Any]
) -> set[str]:
    """Claims the semantic checks reject: repair drops these before salvage."""
    claim_gaps, _ = _number_gaps(result, evidence_by_id)
    return set(claim_gaps) | set(_asset_gaps(result, evidence_by_id))


def structural_violations(
    result: Any,
    ledger_ids: set[str],
    indicators: Iterable[Any] = (),
    *,
    evidence_by_id: Mapping[str, Any] | None = None,
) -> list[str]:
    """List every structural reason the result cannot be trusted.

    An empty list means the result is admissible. These are the failures that
    cannot be repaired deterministically, so they route to the fallback.
    """
    violations: list[str] = []
    claims = list(_attr(result, "claims") or ())
    links = list(_attr(result, "claim_evidence_links") or ())
    claim_ids = {str(_attr(claim, "claim_id")) for claim in claims}

    for link in links:
        evidence_id = str(_attr(link, "evidence_id"))
        claim_id = str(_attr(link, "claim_id"))
        if evidence_id not in ledger_ids:
            violations.append(f"link references unknown evidence {evidence_id}")
        if claim_id not in claim_ids:
            violations.append(f"link references unknown claim {claim_id}")

    for claim in claims:
        claim_id = str(_attr(claim, "claim_id"))
        claim_type = str(_attr(claim, "claim_type"))
        deps = [str(dep) for dep in (_attr(claim, "based_on_claim_ids") or ())]
        unknown = [dep for dep in deps if dep not in claim_ids]
        if unknown:
            violations.append(f"claim {claim_id} depends on unknown {unknown}")
        if claim_type == "fact" and deps:
            violations.append(f"fact {claim_id} must not depend on other claims")
        if claim_type in {"inference", "conclusion"} and not deps:
            violations.append(f"{claim_type} {claim_id} has no upstream claim")

    if detect_cycle(claims):
        violations.append("claim dependency graph contains a cycle")

    if not _attr(result, "insufficient_data", False):
        supported = {
            str(_attr(link, "claim_id"))
            for link in links
            if str(_attr(link, "stance")) in {"supports", "opposes"}
        }
        for claim in claims:
            if str(_attr(claim, "claim_type")) == "conclusion":
                claim_id = str(_attr(claim, "claim_id"))
                if claim_id not in supported:
                    violations.append(
                        f"conclusion {claim_id} has no non-neutral evidence link"
                    )

    # Quantified invalidation thresholds must point at real ledger evidence.
    for condition in _attr(result, "invalidation_conditions") or ():
        basis = _attr(condition, "basis_evidence_id")
        if basis and str(basis) not in ledger_ids:
            violations.append(f"invalidation condition cites unknown evidence {basis}")

    # Semantic grounding needs evidence content, so it only runs when the
    # caller supplies the ledger items; ID-only callers keep the old contract.
    if evidence_by_id is not None:
        violations.extend(number_provenance_violations(result, evidence_by_id))
        violations.extend(asset_consistency_violations(result, evidence_by_id))

    return violations


def _repair_generation(
    generated: Any,
    ledger_ids: set[str],
    evidence_by_id: Mapping[str, Any] | None = None,
) -> Any | None:
    """Deterministically drop the un-supportable claims/links, keeping the rest.

    Returns a repaired copy of the generation, or ``None`` if nothing usable
    survives (in which case the caller falls back). Also drops invalidation
    conditions whose quantified basis cites evidence not in the ledger. When
    ledger items are supplied, claims rejected by the semantic checks (numbers
    without provenance, no shared asset) are removed first so salvage cascades
    over their dependents like any other unusable claim.
    """
    claims_in = list(_attr(generated, "claims") or ())
    links_in = list(_attr(generated, "claim_evidence_links") or ())
    if evidence_by_id is not None:
        flagged = semantically_flagged_claim_ids(generated, evidence_by_id)
        if flagged:
            claims_in = [
                claim
                for claim in claims_in
                if str(_attr(claim, "claim_id")) not in flagged
            ]
            links_in = [
                link
                for link in links_in
                if str(_attr(link, "claim_id")) not in flagged
            ]
    claims, links = salvage_claim_graph(
        claims_in,
        links_in,
        insufficient_data=bool(_attr(generated, "insufficient_data", False)),
        valid_evidence_ids=set(ledger_ids),
    )
    if not claims:
        return None
    invalidations = [
        inv
        for inv in (_attr(generated, "invalidation_conditions") or ())
        if not (
            (basis := _attr(inv, "basis_evidence_id"))
            and str(basis) not in ledger_ids
        )
    ]
    return generated.model_copy(
        update={
            "claims": claims,
            "claim_evidence_links": links,
            "invalidation_conditions": invalidations,
        }
    )


def apply_confidence_caps(
    payload: dict[str, Any],
    indicators: Iterable[Any] = (),
    evidence_by_id: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Lower confidence wherever evidence-contracts.md 10 requires it.

    Caps only ever move confidence down, so applying them cannot manufacture
    certainty. Every adjustment is reported so the report can disclose it.
    """
    notes: list[str] = []
    conflicted_claims = {
        str(_attr(indicator, "claim_id")) for indicator in (indicators or ())
    }
    links = payload.get("claim_evidence_links") or []
    claims = payload.get("claims") or []
    ledger = evidence_by_id or {}

    supporting_groups: dict[str, set[str]] = defaultdict(set)
    supporting_reliabilities: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if str(_attr(link, "stance")) != "supports":
            continue
        claim_id = str(_attr(link, "claim_id"))
        item = ledger.get(str(_attr(link, "evidence_id")))
        if item is None:
            continue
        supporting_groups[claim_id].add(str(_attr(item, "independence_group", "")))
        supporting_reliabilities[claim_id].add(str(_attr(item, "reliability", "low")))

    def lower(current: Any, ceiling: str) -> str:
        current_text = str(current or "low")
        if CONFIDENCE_RANK.get(current_text, 2) < CONFIDENCE_RANK[ceiling]:
            return ceiling
        return current_text

    def adjust(claim: Any, ceiling: str, why: str) -> None:
        claim_id = str(_attr(claim, "claim_id"))
        before = _attr(claim, "confidence")
        after = lower(before, ceiling)
        if after != before:
            claim["confidence"] = after
            notes.append(f"claim {claim_id} {why}，信心依規則下修為 {after}")

    for claim in claims:
        claim_id = str(_attr(claim, "claim_id"))
        if claim_id in conflicted_claims:
            adjust(claim, "low", "因存在實質矛盾")
        if ledger:
            reliabilities = supporting_reliabilities.get(claim_id, set())
            if reliabilities and reliabilities <= {"low"}:
                adjust(claim, "low", "僅有 low reliability 支持證據")
            elif len(supporting_groups.get(claim_id, set())) < 2:
                adjust(claim, "medium", "支持證據少於兩個獨立來源群")

    overall = payload.get("confidence")
    if payload.get("insufficient_data"):
        after = lower(overall, "low")
        if after != overall:
            payload["confidence"] = after
            notes.append("insufficient_data=true，整體信心依規則下修為 low")
    elif conflicted_claims:
        after = lower(overall, "medium")
        if after != overall:
            payload["confidence"] = after
            notes.append("存在實質矛盾，整體信心依規則上限為 medium")

    if notes:
        payload["degradation_notes"] = list(payload.get("degradation_notes") or []) + notes
    return payload, notes


@dataclass
class ArbiterSettings:
    max_evidence: int = MAX_EVIDENCE_FOR_ARBITER
    max_tokens: int = 8000


@dataclass
class Arbiter:
    """Bounded judgement stage with a deterministic fallback."""

    llm: Any
    result_schema: type[BaseModel]
    settings: ArbiterSettings = field(default_factory=ArbiterSettings)

    @property
    def prompt_version(self) -> str:
        return load_prompt("arbiter").version_label

    async def run(
        self,
        *,
        request: Any,
        ledger: Any,
        indicators: Sequence[Any] = (),
        deadline: float,
        degradation_notes: Sequence[str] = (),
    ) -> tuple[BaseModel, list[str]]:
        """Return ``(result, notes)``; never raises for a provider failure."""
        items = list(_attr(ledger, "items") or ())
        ledger_ids = {str(_attr(item, "evidence_id")) for item in items}
        evidence_by_id = {str(_attr(item, "evidence_id")): item for item in items}
        selected = select_evidence(items, indicators, self.settings.max_evidence)
        notes: list[str] = list(degradation_notes)

        if len(selected) < len(items):
            notes.append(
                f"Arbiter 輸入自 {len(items)} 條證據截斷為 {len(selected)} 條"
                "（優先保留 high reliability、矛盾雙方與獨立來源）"
            )

        if not items:
            notes.append("Evidence Ledger 為空，直接產生資料不足結果")
            return self._fallback(request, [], notes, "ledger 無任何證據"), notes

        try:
            generated = await self.llm.converse_structured(
                operation="arbiter",
                messages=[{"role": "user", "content": [{"text": self._user_text(request, selected, indicators)}]}],
                schema=self.result_schema,
                max_tokens=self.settings.max_tokens,
                deadline=deadline,
                system_prompt=load_prompt("arbiter").body,
            )
        except LLMError as exc:
            notes.append(f"Arbiter 生成失敗（{type(exc).__name__}），改用決定論後備結果")
            return self._fallback(request, selected, notes, str(exc)), notes

        violations = structural_violations(
            generated, ledger_ids, indicators, evidence_by_id=evidence_by_id
        )
        if violations:
            # Repair before discarding: drop only the claims that cannot be
            # supported (e.g. a conclusion whose only link is neutral) plus their
            # dependents and dangling links, and keep the rest. A single bad
            # claim must not sink every inference and conclusion into the
            # fact-only fallback. Deterministic — no extra model call.
            repaired = _repair_generation(generated, ledger_ids, evidence_by_id)
            if repaired is not None and not structural_violations(
                repaired, ledger_ids, indicators, evidence_by_id=evidence_by_id
            ):
                dropped = len(_attr(generated, "claims") or ()) - len(
                    _attr(repaired, "claims") or ()
                )
                notes.append(
                    f"Arbiter 輸出部分不合規，已移除 {dropped} 個無法佐證的 claim"
                    "（缺少支持證據、數值或資產無法溯源，或依賴已失效），"
                    "保留其餘可驗證的推論與結論"
                )
                generated = repaired
            else:
                notes.append(
                    "Arbiter 輸出未通過結構驗證，改用決定論後備結果："
                    + "；".join(violations[:3])
                )
                return self._fallback(request, selected, notes, violations[0]), notes

        payload = generated.model_dump()
        payload, cap_notes = apply_confidence_caps(payload, indicators, evidence_by_id)
        notes.extend(cap_notes)
        payload.setdefault("degradation_notes", [])
        payload["degradation_notes"] = list(
            dict.fromkeys(list(payload["degradation_notes"]) + list(notes))
        )
        try:
            return self.result_schema.model_validate(payload), notes
        except ValidationError as exc:  # pragma: no cover - caps never break schema
            notes.append(f"信心上限套用後驗證失敗，改用決定論後備結果：{exc}")
            return self._fallback(request, selected, notes, str(exc)), notes

    def _user_text(
        self, request: Any, selected: Sequence[Any], indicators: Sequence[Any]
    ) -> str:
        import json

        return json.dumps(
            {
                "question": _attr(request, "question"),
                "assets": [str(asset) for asset in (_attr(request, "assets") or ())],
                "analysis_as_of": str(_attr(request, "analysis_as_of")),
                "evidence": build_evidence_payload(selected),
                "conflict_indicators": [
                    {
                        "claim_id": _attr(indicator, "claim_id"),
                        "supporting_evidence_ids": list(
                            _attr(indicator, "supporting_evidence_ids") or ()
                        ),
                        "opposing_evidence_ids": list(
                            _attr(indicator, "opposing_evidence_ids") or ()
                        ),
                    }
                    for indicator in indicators or ()
                ],
            },
            ensure_ascii=False,
        )

    def _fallback(
        self, request: Any, selected: Sequence[Any], notes: Sequence[str], reason: str
    ) -> BaseModel:
        """Build a low-confidence result from validated ledger facts only.

        No inference is attempted: each retained high-reliability fact becomes
        one ``fact`` claim, and the answer states plainly that the reasoning
        stage did not complete.
        """
        facts = [item for item in selected if _reliability_rank(item) == 0][:5]
        claims = []
        links = []
        for index, item in enumerate(facts, start=1):
            claim_id = f"cl_{index:03d}"
            claims.append(
                {
                    "claim_id": claim_id,
                    "claim_type": "fact",
                    "assets": [str(_attr(item, "asset"))]
                    if _attr(item, "asset")
                    else [str(asset) for asset in (_attr(request, "assets") or ())],
                    "text": str(_attr(item, "normalized_fact", "")),
                    "based_on_claim_ids": [],
                    "confidence": "low",
                    "limitations": [],
                    "invalidation_conditions": [],
                }
            )
            links.append(
                {
                    "claim_id": claim_id,
                    "evidence_id": str(_attr(item, "evidence_id")),
                    "stance": "supports",
                    "reason": "決定論後備結果直接引用該筆已驗證證據。",
                }
            )

        payload = {
            "direct_answer": (
                "本次無法產生可靠的市場判斷。推理階段未能完成，"
                "以下僅列出已驗證的事實，不構成對題目的結論。"
            ),
            "market_context": {
                "summary": "推理階段未完成，未產生市場狀況綜述。",
                "time_range": None,
            },
            "claims": claims,
            "claim_evidence_links": links,
            "confidence": "low",
            "confidence_rationale": (
                "推理階段未完成，僅保留決定論證據，依規則信心為 low。"
            ),
            "limitations": [
                f"Arbiter 未能產生有效結果：{reason}",
                "本結果不含推論與結論層，僅有事實層。",
            ],
            "invalidation_conditions": [],
            "watch_items": [],
            "insufficient_data": True,
            "degradation_notes": list(dict.fromkeys(notes)),
        }
        return self.result_schema.model_validate(payload)
