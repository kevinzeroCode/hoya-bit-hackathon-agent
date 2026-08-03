"""Evidence Ledger service: query, conflict detection, and Arbiter preparation.

Builds on `processor.build_ledger` (which handles ranking, dedup, ID assignment)
to add:
- Material conflict detection (evidence-contracts §9)
- Richer query API: filter by asset, source_type, independence_group
- Arbiter payload selection with per-asset awareness
- Source diversity and independence statistics

All logic is deterministic — no LLM, no network, no file I/O.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from hoya_agent.evidence.grounding import (
    LLM_EXTRACTED_SOURCE_TYPES,
    GroundingStatus,
    ground_fact,
)
from hoya_agent.evidence.policies import ConfidenceSignals, Reliability
from hoya_agent.evidence.processor import build_ledger  # noqa: F401
from hoya_agent.models import ConflictIndicator, EvidenceItem, EvidenceLedger

# Persisted with every indicator so a later rule change stays auditable.
CONFLICT_RULE_VERSION = "1.0"


def _plain(value: Any) -> str:
    """Enum member or plain string to its wire value."""
    return str(getattr(value, "value", value))


def filter_by_asset(ledger: EvidenceLedger, asset: str) -> list[EvidenceItem]:
    """Return items for a specific asset (case-insensitive)."""
    target = asset.upper()
    return [item for item in ledger.items if item.asset and item.asset.upper() == target]


def filter_by_source_type(ledger: EvidenceLedger, source_type: str) -> list[EvidenceItem]:
    """Return items matching a source_type."""
    return [item for item in ledger.items if item.source_type == source_type]


def distinct_source_types(ledger: EvidenceLedger) -> set[str]:
    """Set of distinct source_type values present in the ledger."""
    return {item.source_type for item in ledger.items}


def distinct_independence_groups(ledger: EvidenceLedger) -> set[str]:
    """Set of distinct independence_group values present in the ledger."""
    return {item.independence_group for item in ledger.items}


def has_first_hand_source(ledger: EvidenceLedger) -> bool:
    """True when at least one item has high reliability (first-hand / official)."""
    return any(item.reliability == "high" for item in ledger.items)


def source_coverage_gaps(ledger: EvidenceLedger) -> list[str]:
    """Check run coverage targets and return human-readable gap descriptions.

    Targets (per competition-rules.md):
    - At least 3 distinct source types
    - At least 3 distinct independence groups
    - At least 1 first-hand/official source (high reliability)
    """
    gaps: list[str] = []
    types = distinct_source_types(ledger)
    groups = distinct_independence_groups(ledger)
    if len(types) < 3:
        gaps.append(f"來源類型多樣性不足：僅有 {len(types)} 種（目標 ≥3）")
    if len(groups) < 3:
        gaps.append(f"獨立來源不足：僅有 {len(groups)} 個 independence group（目標 ≥3）")
    if not has_first_hand_source(ledger):
        gaps.append("缺少第一手來源（high reliability）")
    return gaps


# ---------------------------------------------------------------------------
# Material Conflict Detection (evidence-contracts §9)
# ---------------------------------------------------------------------------


class ConflictResult:
    """Deterministic material conflict check for a single claim."""

    __slots__ = (
        "claim_id",
        "supporting_ids",
        "opposing_ids",
        "supporting_groups",
        "opposing_groups",
        "is_material",
    )

    def __init__(
        self,
        *,
        claim_id: str,
        supporting_ids: list[str],
        opposing_ids: list[str],
        supporting_groups: list[str],
        opposing_groups: list[str],
        is_material: bool,
    ) -> None:
        self.claim_id = claim_id
        self.supporting_ids = supporting_ids
        self.opposing_ids = opposing_ids
        self.supporting_groups = supporting_groups
        self.opposing_groups = opposing_groups
        self.is_material = is_material


def detect_material_conflict(
    claim_id: str,
    *,
    supporting_evidence_ids: Sequence[str],
    opposing_evidence_ids: Sequence[str],
    ledger: EvidenceLedger,
) -> ConflictResult:
    """Determine if a claim has a material conflict per §9 rules.

    Material conflict requires ALL of:
    1. At least one supports link AND at least one opposes link
    2. Evidence on both sides has reliability high or medium
    3. At least one supporting/opposing pair from different independence_groups
    """
    evidence_map: dict[str, EvidenceItem] = {
        item.evidence_id: item for item in ledger.items
    }

    # Gather supporting evidence with reliability >= medium
    qualified_support: list[EvidenceItem] = []
    for eid in supporting_evidence_ids:
        item = evidence_map.get(eid)
        if item and item.reliability in ("high", "medium"):
            qualified_support.append(item)

    # Gather opposing evidence with reliability >= medium
    qualified_oppose: list[EvidenceItem] = []
    for eid in opposing_evidence_ids:
        item = evidence_map.get(eid)
        if item and item.reliability in ("high", "medium"):
            qualified_oppose.append(item)

    supporting_groups = list({item.independence_group for item in qualified_support})
    opposing_groups = list({item.independence_group for item in qualified_oppose})

    # Check all three conditions. A cross-group pair exists exactly when the
    # two sides span more than one group in total: identical group sets like
    # supports={A,B} / opposes={A,B} still pair A against B.
    has_both_sides = bool(qualified_support) and bool(qualified_oppose)
    has_independent_pair = (
        len(set(supporting_groups) | set(opposing_groups)) >= 2
        if has_both_sides
        else False
    )

    return ConflictResult(
        claim_id=claim_id,
        supporting_ids=[item.evidence_id for item in qualified_support],
        opposing_ids=[item.evidence_id for item in qualified_oppose],
        supporting_groups=supporting_groups,
        opposing_groups=opposing_groups,
        is_material=has_both_sides and has_independent_pair,
    )


def build_conflict_indicators(
    *,
    claim_evidence_links: Sequence[Any],
    ledger: Any,
    rule_version: str = CONFLICT_RULE_VERSION,
) -> list[ConflictIndicator]:
    """Derive every material-conflict indicator for a result's links (§9).

    Deterministic and claim-level: stance lives on the link, so the same evidence
    can support one claim and oppose another. Only claims carrying both stances
    are examined, and a claim that fails any of the three §9 conditions produces
    no indicator rather than a weakened one.

    Ordering is by `claim_id` and every id list is sorted, so two runs over the
    same ledger emit byte-identical indicators regardless of link order.
    """
    supporting: dict[str, list[str]] = defaultdict(list)
    opposing: dict[str, list[str]] = defaultdict(list)
    for link in claim_evidence_links:
        stance = _plain(getattr(link, "stance", None))
        claim_id = str(getattr(link, "claim_id", ""))
        evidence_id = str(getattr(link, "evidence_id", ""))
        if not claim_id or not evidence_id:
            continue
        if stance == "supports":
            supporting[claim_id].append(evidence_id)
        elif stance == "opposes":
            # `neutral` provides context only and can never create a conflict.
            opposing[claim_id].append(evidence_id)

    indicators: list[ConflictIndicator] = []
    for claim_id in sorted(set(supporting) & set(opposing)):
        conflict = detect_material_conflict(
            claim_id,
            supporting_evidence_ids=supporting[claim_id],
            opposing_evidence_ids=opposing[claim_id],
            ledger=ledger,
        )
        if not conflict.is_material:
            continue
        indicators.append(
            ConflictIndicator(
                claim_id=claim_id,
                supporting_evidence_ids=sorted(set(conflict.supporting_ids)),
                opposing_evidence_ids=sorted(set(conflict.opposing_ids)),
                independence_groups=sorted(
                    set(conflict.supporting_groups) | set(conflict.opposing_groups)
                ),
                rule_version=rule_version,
            )
        )
    return indicators


# ---------------------------------------------------------------------------
# Confidence signal computation
# ---------------------------------------------------------------------------


def _is_grounded(item: EvidenceItem, semantic_status: dict[str, str] | None = None) -> bool:
    """Deterministically re-check that an LLM-extracted fact traces to its source.

    Market/official facts are deterministic tool output and always count. For
    news/social, a fact whose hard atoms are not in `content_reference`
    (fabricated value) must not prop up a claim's corroboration — that verdict
    (`GroundingStatus.partial`) is never overridden, semantic or otherwise.

    A fact with no checkable hard atom at all (`GroundingStatus.unverified` —
    purely qualitative, nothing numeric to mechanically check) is not
    automatically penalized the same way: if the caller supplies a
    `semantic_status` lookup (evidence_id -> "verified"/"contradicted"/
    "unverified", the plain-string form of
    `reasoning.semantic_grounding.SemanticGroundingStatus` — kept as a string
    here so this module, which must stay LLM-free, never imports the
    reasoning layer), a `"verified"` semantic recheck counts as grounded.
    Omitting `semantic_status` (the default) reproduces the exact prior
    behavior: `unverified` never counts, same as `partial`.
    """
    if item.source_type not in LLM_EXTRACTED_SOURCE_TYPES:
        return True
    verdict = ground_fact(item.normalized_fact, item.content_reference)
    if verdict.status is GroundingStatus.verified:
        return True
    if verdict.status is GroundingStatus.unverified and semantic_status is not None:
        return semantic_status.get(item.evidence_id) == "verified"
    return False


def confidence_signals_for_claim(
    *,
    supporting_evidence_ids: Sequence[str],
    ledger: EvidenceLedger,
    has_material_conflict: bool = False,
    insufficient_data: bool = False,
    require_grounding: bool = False,
    semantic_status: dict[str, str] | None = None,
) -> ConfidenceSignals:
    """Build the deterministic ConfidenceSignals for a claim from its support.

    When ``require_grounding`` is set, an ungrounded LLM-extracted supporting item
    (a fact whose numbers/dates are absent from its source) does not count toward
    the independent-group corroboration or the reliability ceiling, so a fabricated
    value can never lift a claim to high confidence. Off by default so it never
    silently changes existing behavior; the pipeline opts in. Never mutates the
    static `reliability` field — it only decides what counts as support.

    ``semantic_status`` (Task 16 / G1) is an optional evidence_id -> "verified"/
    "contradicted"/"unverified" lookup from the reasoning layer's LLM-assisted
    recheck of purely-qualitative facts. Only consulted when the deterministic
    pass found no checkable hard atom at all (see `_is_grounded`); a numeric
    mismatch (`GroundingStatus.partial`) is never overridden by it. Omitting
    it reproduces the exact prior behavior.
    """
    evidence_map: dict[str, EvidenceItem] = {
        item.evidence_id: item for item in ledger.items
    }

    groups: set[str] = set()
    reliabilities: list[Reliability] = []
    only_stale = True

    for eid in supporting_evidence_ids:
        item = evidence_map.get(eid)
        if item is None:
            continue
        if require_grounding and not _is_grounded(item, semantic_status):
            continue
        groups.add(item.independence_group)
        reliabilities.append(item.reliability)
        if not item.is_stale:
            only_stale = False

    if not reliabilities:
        return ConfidenceSignals(
            supporting_groups=0,
            max_supporting_reliability="low",
            has_material_conflict=has_material_conflict,
            only_stale_cache=False,
            insufficient_data=True,
        )

    # Determine highest reliability
    rel_rank: dict[Reliability, int] = {"high": 2, "medium": 1, "low": 0}
    max_rel: Reliability = max(reliabilities, key=lambda r: rel_rank[r])

    return ConfidenceSignals(
        supporting_groups=len(groups),
        max_supporting_reliability=max_rel,
        has_material_conflict=has_material_conflict,
        only_stale_cache=only_stale and bool(reliabilities),
        insufficient_data=insufficient_data,
    )


# ---------------------------------------------------------------------------
# Arbiter payload selection
# ---------------------------------------------------------------------------


def select_for_arbiter(
    ledger: EvidenceLedger,
    *,
    max_items: int = 30,
) -> list[EvidenceItem]:
    """Select the best items for the Arbiter, respecting the cap.

    Selection priority (from arbiter.py / evidence-contracts):
    1. All high-reliability items
    2. Material-conflict pair items (preserved separately, but we don't know
       claims yet at this stage, so we keep all medium)
    3. Remaining slots filled by maximizing distinct independence_groups

    For single-asset runs this is straightforward. The existing top(n) already
    respects the ranked order. This function adds independence-group diversity
    for the final slots.
    """
    if len(ledger.items) <= max_items:
        return list(ledger.items)

    # Phase 1: unconditionally keep all high-reliability items
    high: list[EvidenceItem] = []
    rest: list[EvidenceItem] = []
    for item in ledger.items:
        if item.reliability == "high":
            high.append(item)
        else:
            rest.append(item)

    if len(high) >= max_items:
        return high[:max_items]

    # Phase 2: fill remaining slots from non-high items with diversity
    remaining_budget = max_items - len(high)
    selected_groups = {item.independence_group for item in high}

    # Prefer items from groups not yet represented
    new_group_items: list[EvidenceItem] = []
    same_group_items: list[EvidenceItem] = []
    for item in rest:
        if item.independence_group not in selected_groups:
            new_group_items.append(item)
            selected_groups.add(item.independence_group)
        else:
            same_group_items.append(item)

    # Fill: new groups first, then same groups (already ranked by processor)
    fill = (new_group_items + same_group_items)[:remaining_budget]
    return high + fill


# ---------------------------------------------------------------------------
# Per-asset selection (for dual-asset runs per S9B)
# ---------------------------------------------------------------------------


def select_for_arbiter_dual(
    ledger: EvidenceLedger,
    *,
    assets: Sequence[str],
    max_items: int = 30,
) -> list[EvidenceItem]:
    """Select items for Arbiter in a dual-asset run with per-asset fairness.

    Ensures both assets get representation. Items with asset=None (e.g., Fear &
    Greed) do not count against either asset's quota.
    """
    if len(assets) < 2:
        return select_for_arbiter(ledger, max_items=max_items)

    # Partition: per-asset and market-wide
    market_wide: list[EvidenceItem] = []
    per_asset: dict[str, list[EvidenceItem]] = defaultdict(list)

    for item in ledger.items:
        if item.asset is None:
            market_wide.append(item)
        else:
            per_asset[item.asset.upper()].append(item)

    # Market-wide items are always included first (typically few)
    selected = list(market_wide)
    budget = max_items - len(selected)
    if budget <= 0:
        return selected[:max_items]

    # Split remaining budget evenly between assets
    per_asset_budget = budget // len(assets)
    remainder = budget - per_asset_budget * len(assets)

    result: list[EvidenceItem] = list(selected)
    for i, asset in enumerate(assets):
        asset_items = per_asset.get(asset.upper(), [])
        cap = per_asset_budget + (1 if i < remainder else 0)
        result.extend(asset_items[:cap])

    return result
