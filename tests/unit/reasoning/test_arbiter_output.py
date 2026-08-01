"""The Arbiter's LLM-output schema and its projection onto `AnalysisResult`.

`AnalysisResult` cannot be the Arbiter's `result_schema`: it requires `run_id`,
`question`, `assets` and `analysis_as_of`, none of which the model may restate,
and the frozen `Arbiter._fallback()` deliberately omits them (plus it leaves
`market_context.time_range` null and claims without a time range). So the model
fills a narrower schema and deterministic code stamps the frozen request context
back on.

Two traps are pinned here because both send a live run silently into the
deterministic fallback:
- the frozen `apply_confidence_caps()` compares confidence and stance as *plain
  strings*, so the boundary schema must not use enum members;
- the frozen `_fallback()` renders an evidence item's asset with `str()`, which
  for a `str`-mixin enum yields `"Asset.BTC"`, not `"BTC"`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hoya_agent.models import (
    Asset,
    ClaimType,
    Reliability,
    Stance,
)
from hoya_agent.reasoning.arbiter import Arbiter, _reliability_rank, apply_confidence_caps
from hoya_agent.reasoning.arbiter_output import (
    ArbiterOutput,
    ledger_view,
    project_to_analysis_result,
)

NOW = datetime(2026, 5, 31, tzinfo=UTC)
RUN_ID = "run_20260531_000000_ao01"


class _Request:
    run_id = RUN_ID
    question = "BTC 近期市場行為？"
    assets = ("BTC",)
    analysis_as_of = NOW


class _Item:
    """Canonical-shaped evidence item: `asset` is an enum, as in the real ledger."""

    def __init__(self, evidence_id: str, *, reliability: Reliability, group: str) -> None:
        self.evidence_id = evidence_id
        self.asset = Asset.BTC
        self.reliability = reliability
        self.independence_group = group
        self.normalized_fact = f"fact {evidence_id}"
        self.published_at = datetime(2026, 5, 20, tzinfo=UTC)
        self.fetched_at = NOW


def _items() -> list[_Item]:
    return [
        _Item("ev_001", reliability=Reliability.high, group="organizer-public-market-data"),
        _Item("ev_002", reliability=Reliability.medium, group="coindesk.com"),
    ]


def _output(**overrides) -> ArbiterOutput:
    payload = {
        "direct_answer": "近期回落與現貨賣壓一致。",
        "market_context": {"summary": "BTC 市場狀況。", "time_range": None},
        "claims": [
            {
                "claim_id": "cl_001",
                "claim_type": "fact",
                "assets": ["BTC"],
                "text": "BTC 的 14 日報酬為 -4.88%。",
                "based_on_claim_ids": [],
                "confidence": "high",
            }
        ],
        "claim_evidence_links": [
            {
                "claim_id": "cl_001",
                "evidence_id": "ev_001",
                "stance": "supports",
                "reason": "deterministic 報酬計算涵蓋該期間。",
            }
        ],
        "confidence": "high",
        "confidence_rationale": "兩個獨立來源支持主要觀察。",
    }
    payload.update(overrides)
    return ArbiterOutput.model_validate(payload)


# ── schema shape ────────────────────────────────────────────────────────────


def test_schema_accepts_a_result_without_the_frozen_request_context() -> None:
    output = _output()

    assert output.market_context is not None
    assert output.market_context.time_range is None
    assert output.claims[0].time_range is None


def test_schema_refuses_to_let_the_model_restate_the_frozen_context() -> None:
    for field, value in (
        ("run_id", RUN_ID),
        ("question", "something else"),
        ("assets", ["ETH"]),
        ("analysis_as_of", "2026-05-31T00:00:00Z"),
    ):
        with pytest.raises(ValueError):
            _output(**{field: value})


def test_schema_refuses_deterministic_only_fields() -> None:
    """Trust Scorecards and market regime are deterministic; the model may not emit them."""
    for field in ("trust_scorecards", "market_regime"):
        with pytest.raises(ValueError):
            _output(**{field: []})


def test_boundary_values_dump_as_plain_strings() -> None:
    """Enum members would break the frozen cap helper's string comparisons."""
    payload = _output().model_dump()

    assert payload["confidence"] == "high"
    assert payload["claims"][0]["confidence"] == "high"
    assert payload["claims"][0]["claim_type"] == "fact"
    assert payload["claim_evidence_links"][0]["stance"] == "supports"


def test_confidence_caps_round_trip_stays_schema_valid() -> None:
    """A cap adjustment must not push the Arbiter into its fallback."""
    payload = _output().model_dump()
    evidence_by_id = {item.evidence_id: item for item in _items()}

    capped, notes = apply_confidence_caps(payload, (), evidence_by_id)

    assert notes, "one supporting group must trigger the medium cap"
    revalidated = ArbiterOutput.model_validate(capped)
    assert revalidated.claims[0].confidence == "medium"


# ── projection ──────────────────────────────────────────────────────────────


def test_projection_stamps_the_frozen_request_context() -> None:
    result, _ = project_to_analysis_result(
        _output(), request=_Request(), evidence_items=_items()
    )

    assert result.run_id == RUN_ID
    assert result.question == _Request.question
    assert result.assets == [Asset.BTC]
    assert result.analysis_as_of == NOW


def test_projection_maps_boundary_strings_onto_canonical_enums() -> None:
    result, _ = project_to_analysis_result(
        _output(), request=_Request(), evidence_items=_items()
    )

    assert result.claims[0].claim_type is ClaimType.fact
    assert result.claims[0].confidence is Reliability.high
    assert result.claim_evidence_links[0].stance is Stance.supports
    assert result.claims[0].assets == [Asset.BTC]


def test_projection_fills_a_missing_time_range_from_the_evidence_window() -> None:
    result, _ = project_to_analysis_result(
        _output(), request=_Request(), evidence_items=_items()
    )

    assert result.claims[0].time_range.start == "2026-05-20"
    assert result.claims[0].time_range.end == "2026-05-31"
    assert result.market_context is not None
    assert result.market_context.time_range.end == "2026-05-31"


def test_projection_never_lets_a_claim_window_pass_the_frozen_cutoff() -> None:
    output = _output(
        claims=[
            {
                "claim_id": "cl_001",
                "claim_type": "fact",
                "assets": ["BTC"],
                "time_range": {"start": "2026-05-20", "end": "2026-06-30"},
                "text": "BTC 的 14 日報酬為 -4.88%。",
                "based_on_claim_ids": [],
                "confidence": "high",
            }
        ]
    )
    result, notes = project_to_analysis_result(
        output, request=_Request(), evidence_items=_items()
    )

    assert result.claims[0].time_range.end == "2026-05-31"
    assert any("cutoff" in note or "凍結" in note for note in notes)


def test_projection_tolerates_the_fallback_asset_formatting() -> None:
    """`str(Asset.BTC)` is `'Asset.BTC'`, which the frozen fallback emits verbatim."""
    output = _output(
        claims=[
            {
                "claim_id": "cl_001",
                "claim_type": "fact",
                "assets": ["Asset.BTC"],
                "text": "BTC 的 14 日報酬為 -4.88%。",
                "based_on_claim_ids": [],
                "confidence": "low",
            }
        ]
    )
    result, _ = project_to_analysis_result(
        output, request=_Request(), evidence_items=_items()
    )

    assert result.claims[0].assets == [Asset.BTC]


def test_projection_falls_back_to_request_assets_and_discloses_it() -> None:
    output = _output(
        claims=[
            {
                "claim_id": "cl_001",
                "claim_type": "fact",
                "assets": ["DOGE"],
                "text": "無法辨識資產的主張。",
                "based_on_claim_ids": [],
                "confidence": "low",
            }
        ]
    )
    result, notes = project_to_analysis_result(
        output, request=_Request(), evidence_items=_items()
    )

    assert result.claims[0].assets == [Asset.BTC]
    assert any("DOGE" in note for note in notes)


# ── compatibility with the frozen Arbiter ───────────────────────────────────


def test_ledger_view_renders_boundary_values_as_plain_strings() -> None:
    """Same pattern as `ReasoningRequest`: a string-valued view for the frozen layer."""
    view = ledger_view(_items())

    assert [item.evidence_id for item in view.items] == ["ev_001", "ev_002"]
    first = view.items[0]
    assert first.reliability == "high"
    assert first.asset == "BTC"
    assert first.independence_group == "organizer-public-market-data"
    assert first.normalized_fact == "fact ev_001"


def test_canonical_items_defeat_the_frozen_high_reliability_filter() -> None:
    """Regression: `_reliability_rank` uses `str()`, so enums rank as unknown.

    Left unfixed this is silent: `select_evidence` loses its "keep every high item"
    priority and the deterministic fallback emits no claims at all.
    """
    assert _reliability_rank(_items()[0]) != 0, "documents the frozen behaviour"
    assert _reliability_rank(ledger_view(_items()).items[0]) == 0


def test_only_low_reliability_cap_fires_through_the_view() -> None:
    low_items = [_Item("ev_001", reliability=Reliability.low, group="cryptopanic.com")]
    payload = _output().model_dump()

    _, notes = apply_confidence_caps(
        payload, (), {item.evidence_id: item for item in ledger_view(low_items).items}
    )

    assert any("low reliability" in note for note in notes)


def test_the_frozen_fallback_payload_validates_against_this_schema() -> None:
    arbiter = Arbiter(llm=None, result_schema=ArbiterOutput)

    output = arbiter._fallback(
        _Request(), ledger_view(_items()).items, ["injected failure"], "test reason"
    )

    assert isinstance(output, ArbiterOutput)
    assert output.insufficient_data is True
    assert output.confidence == "low"


def test_the_frozen_fallback_projects_to_a_valid_analysis_result() -> None:
    arbiter = Arbiter(llm=None, result_schema=ArbiterOutput)
    items = ledger_view(_items()).items
    output = arbiter._fallback(_Request(), items, ["injected failure"], "test reason")

    result, _ = project_to_analysis_result(output, request=_Request(), evidence_items=items)

    assert result.insufficient_data is True
    assert result.confidence is Reliability.low
    assert result.run_id == RUN_ID
    # Only the high-reliability fact is retained by the frozen fallback.
    assert [claim.claim_id for claim in result.claims] == ["cl_001"]
    assert result.claim_evidence_links[0].evidence_id == "ev_001"
