"""Deterministic claim-graph salvage — schema-agnostic, no contracts import.

The reasoning stages emit a lax claim bundle (facts, inferences, conclusions and
their evidence links). Occasionally one claim is structurally unusable: a
conclusion whose only link is `neutral`, an inference whose dependency was
dropped, a fact citing a `cl_` id as evidence. The strict `AnalysisResult` — and
the Arbiter's own structural gate — are all-or-nothing, so a single bad claim
would discard *every* inference and conclusion and force the fact-only fallback.

`salvage_claim_graph` repairs the bundle deterministically: it drops only the
claims that cannot meet the contract, cascading to their dependents and dangling
links, and keeps the rest. It never fabricates evidence — it can only remove — so
the report stays honest; callers disclose how many claims were removed.

Deliberately dependency-free (duck-typed over any object exposing the claim/link
fields) so both `mapping.py` and the injection-independent `arbiter.py` can share
it without pulling in the contracts package.
"""

from __future__ import annotations

import re
from typing import Any, TypeVar

# Mirror models._EV_ID_RE locally: an evidence link must cite an `ev_NNN` id,
# never a `cl_NNN` claim id.
_EV_ID_RE = re.compile(r"^ev_\d{3,}$")
_NEUTRAL = "neutral"
_SUPPORTS = "supports"

_Claim = TypeVar("_Claim")
_Link = TypeVar("_Link")


def usable_links(gen_links: list[_Link], valid_evidence_ids: set[str] | None) -> list[_Link]:
    """Drop links whose evidence_id is malformed (e.g. a `cl_` id) or absent from
    the ledger, so the coverage pass judges each claim on real evidence only."""
    out = []
    for lk in gen_links:
        if not _EV_ID_RE.match(lk.evidence_id):
            continue
        if valid_evidence_ids is not None and lk.evidence_id not in valid_evidence_ids:
            continue
        out.append(lk)
    return out


def _valid_deps(
    claim: Any,
    index: int,
    kept: set[str],
    pos: dict[str, int],
    ctype: dict[str, str],
) -> list[str]:
    """Deps that survive the graph rules: existing, non-self, not a conclusion,
    and (for an inference) listed earlier. Order-preserving and de-duplicated."""
    deps: list[str] = []
    for d in claim.based_on_claim_ids:
        if d == claim.claim_id or d not in kept or ctype.get(d) == "conclusion":
            continue
        if claim.claim_type == "inference" and pos.get(d, index) >= index:
            continue
        if d not in deps:
            deps.append(d)
    return deps


def salvage_claim_graph(
    gen_claims: list[_Claim],
    gen_links: list[_Link],
    *,
    insufficient_data: bool,
    valid_evidence_ids: set[str] | None,
) -> tuple[list[_Claim], list[_Link]]:
    """Repair the claim bundle by removal only; return ``(claims, links)``.

    A claim is kept only if it can meet the contract: a fact needs a non-neutral
    link, an inference needs a supporting link and at least one valid upstream
    dep, a conclusion needs a supporting link (unless `insufficient_data`) and a
    valid upstream dep. Removal cascades — dropping a claim can orphan a
    dependent or strip another claim's only support — so the pass iterates to a
    fixpoint. Fact deps are cleared (facts must not depend on other claims).
    """
    links = usable_links(gen_links, valid_evidence_ids)
    claims = list(gen_claims)

    while True:
        kept = {c.claim_id for c in claims}
        pos = {c.claim_id: i for i, c in enumerate(claims)}
        ctype = {c.claim_id: c.claim_type for c in claims}
        links_by: dict[str, list[Any]] = {}
        for lk in links:
            if lk.claim_id in kept:
                links_by.setdefault(lk.claim_id, []).append(lk)

        drop_id: str | None = None
        for i, c in enumerate(claims):
            cl = links_by.get(c.claim_id, [])
            has_non_neutral = any(lk.stance != _NEUTRAL for lk in cl)
            has_supports = any(lk.stance == _SUPPORTS for lk in cl)
            if c.claim_type == "fact":
                if not has_non_neutral:
                    drop_id = c.claim_id
                    break
            else:  # inference / conclusion
                if not _valid_deps(c, i, kept, pos, ctype):
                    drop_id = c.claim_id
                    break
                covered = has_supports or (c.claim_type == "conclusion" and insufficient_data)
                if not covered:
                    drop_id = c.claim_id
                    break
        if drop_id is None:
            break
        claims = [c for c in claims if c.claim_id != drop_id]

    kept = {c.claim_id for c in claims}
    pos = {c.claim_id: i for i, c in enumerate(claims)}
    ctype = {c.claim_id: c.claim_type for c in claims}
    repaired: list[Any] = []
    for i, c in enumerate(claims):
        deps = [] if c.claim_type == "fact" else _valid_deps(c, i, kept, pos, ctype)
        repaired.append(c.model_copy(update={"based_on_claim_ids": deps}))
    repaired_links = [lk for lk in links if lk.claim_id in kept]
    return repaired, repaired_links
