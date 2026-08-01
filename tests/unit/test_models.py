"""Unit tests for the normative data contracts in hoya_agent.models.

Covers: enums, AnalysisRequest, EvidenceItem, EvidenceDraft, ClaimEvidenceLink,
Claim, EvidenceLedger, ConflictIndicator, DegradationEvent, TimeRange,
MarketContext, InvalidationCondition, MarketRegime, TrustScorecard,
EvidenceListRow projection and AnalysisResult.

Includes the corrective-commit regression tests for the 14 accepted Codex
contract-review findings against Task 1a.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from hoya_agent.models import (
    AnalysisRequest,
    AnalysisResult,
    Asset,
    Claim,
    ClaimEvidenceLink,
    ClaimType,
    ConflictIndicator,
    ConsistencyDimension,
    DataMode,
    DegradationEvent,
    EvidenceDraft,
    EvidenceItem,
    EvidenceLedger,
    EvidenceListRow,
    FreshnessDimension,
    InvalidationCondition,
    InvalidationOperator,
    MarketContext,
    MarketRegime,
    RegimeLabel,
    Reliability,
    ReliabilityMix,
    RunConfigSnapshot,
    RunMode,
    RunSummary,
    SourceDiversityDimension,
    SourceIndependenceDimension,
    SourceType,
    Stance,
    TerminalState,
    TimeRange,
    TrustLevel,
    TrustScorecard,
    project_evidence_list,
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc
NOW = datetime(2026, 7, 17, 6, 0, 0, tzinfo=UTC)
YESTERDAY = datetime(2026, 7, 16, 0, 0, 0, tzinfo=UTC)
VALID_HASH = "a" * 64
PLUS8 = timezone(timedelta(hours=8))


def _valid_request(**overrides) -> dict:
    base = {
        "question": "What factors explain BTC's recent market behavior?",
        "assets": ["BTC"],
        "requested_at": NOW,
        "analysis_as_of": NOW,
        "deadline_seconds": 900,
        "run_mode": "official",
        "enable_conditional_debate": False,
        "run_id": "run_20260717_060000_ab12",
    }
    base.update(overrides)
    return base


def _valid_evidence_item(**overrides) -> dict:
    base = {
        "evidence_id": "ev_001",
        "asset": "BTC",
        "source_type": "market",
        "source_name": "Binance Spot",
        "source_url": "https://api.binance.com/api/v3/klines",
        "published_at": YESTERDAY,
        "fetched_at": NOW,
        "query_or_parameters": "symbol=BTCUSDT&interval=1d",
        "content_reference": "2026-07-16 UTC close",
        "normalized_fact": "BTC 14-day return was 5%.",
        "reliability": "high",
        "independence_group": "binance.com",
        "content_hash": VALID_HASH,
        "is_cached": False,
        "cache_time": None,
        "is_stale": False,
    }
    base.update(overrides)
    return base


def _valid_claim(**overrides) -> dict:
    base = {
        "claim_id": "cl_001",
        "claim_type": "fact",
        "assets": ["BTC"],
        "time_range": {"start": "2026-07-03", "end": "2026-07-17"},
        "text": "BTC's 14-day return was 5%.",
        "based_on_claim_ids": [],
        "confidence": "high",
        "limitations": [],
        "invalidation_conditions": [],
    }
    base.update(overrides)
    return base


def _valid_link(**overrides) -> dict:
    base = {
        "claim_id": "cl_001",
        "evidence_id": "ev_001",
        "stance": "supports",
        "reason": "The calculated return directly measures the claim.",
    }
    base.update(overrides)
    return base


def _valid_degradation(**overrides) -> dict:
    base = {
        "stage": "market_worker",
        "event_type": "timeout",
        "source": "binance",
        "message": "Binance API timed out",
        "timestamp": NOW,
    }
    base.update(overrides)
    return base


def _valid_result(**overrides) -> dict:
    base = {
        "run_id": "run_20260717_060000_ab12",
        "question": "What factors explain BTC?",
        "assets": ["BTC"],
        "analysis_as_of": NOW,
        "direct_answer": "Evidence supports a qualified explanation.",
        "confidence": "medium",
        "confidence_rationale": "Two sources.",
        "limitations": [],
        "invalidation_conditions": [],
        "watch_items": [],
        "insufficient_data": False,
        "degradation_notes": [],
    }
    base.update(overrides)
    return base


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    def test_asset_values(self):
        assert set(Asset) == {Asset.BTC, Asset.ETH, Asset.SOL, Asset.BNB, Asset.XRP}

    def test_asset_is_str(self):
        assert isinstance(Asset.BTC, str)
        assert Asset.BTC == "BTC"

    def test_invalid_asset_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(**_valid_request(assets=["DOGE"]))

    def test_run_mode_values(self):
        assert {m.value for m in RunMode} == {"official", "rehearsal", "demo"}

    def test_source_type_values(self):
        expected = {"official", "market", "news", "onchain", "social", "macro"}
        assert {s.value for s in SourceType} == expected

    def test_reliability_values(self):
        assert {r.value for r in Reliability} == {"high", "medium", "low"}

    def test_stance_values(self):
        assert {s.value for s in Stance} == {"supports", "opposes", "neutral"}

    def test_claim_type_values(self):
        assert {c.value for c in ClaimType} == {"fact", "inference", "conclusion"}

    def test_trust_level_values(self):
        assert {t.value for t in TrustLevel} == {
            "strong", "moderate", "weak", "unavailable"
        }

    def test_regime_label_values(self):
        """Finding 14: RegimeLabel includes `unavailable` per amended §16.3."""
        expected = {
            "trending_up", "trending_down", "range_bound",
            "high_volatility", "mixed", "unavailable",
        }
        assert {r.value for r in RegimeLabel} == expected

    def test_regime_label_includes_unavailable(self):
        assert RegimeLabel.unavailable.value == "unavailable"

    def test_invalidation_operator_values(self):
        assert {o.value for o in InvalidationOperator} == {"lt", "lte", "gt", "gte"}


# ===========================================================================
# AnalysisRequest tests
# ===========================================================================


class TestAnalysisRequest:
    def test_valid_construction(self):
        req = AnalysisRequest(**_valid_request())
        assert req.run_mode == RunMode.official
        assert req.assets == [Asset.BTC]
        assert req.enable_conditional_debate is False

    def test_two_assets(self):
        req = AnalysisRequest(**_valid_request(assets=["BTC", "ETH"]))
        assert req.assets == [Asset.BTC, Asset.ETH]

    def test_rejects_three_assets(self):
        with pytest.raises(ValidationError, match="1 or 2"):
            AnalysisRequest(**_valid_request(assets=["BTC", "ETH", "SOL"]))

    def test_rejects_empty_assets(self):
        with pytest.raises(ValidationError, match="1 or 2"):
            AnalysisRequest(**_valid_request(assets=[]))

    def test_rejects_duplicate_assets(self):
        with pytest.raises(ValidationError, match="unique"):
            AnalysisRequest(**_valid_request(assets=["BTC", "BTC"]))

    def test_rejects_unsupported_asset(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(**_valid_request(assets=["DOGE"]))

    def test_rejects_naive_datetime(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            AnalysisRequest(**_valid_request(analysis_as_of=naive))

    def test_rejects_naive_requested_at(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            AnalysisRequest(**_valid_request(requested_at=naive))

    def test_rejects_blank_question(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalysisRequest(**_valid_request(question="   "))

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(**_valid_request(unknown_field="x"))

    def test_run_id_format(self):
        with pytest.raises(ValidationError, match="run_YYYYMMDD"):
            AnalysisRequest(**_valid_request(run_id="bad_id"))

    def test_run_id_rejects_whitespace_suffix(self):
        with pytest.raises(ValidationError, match="run_YYYYMMDD"):
            AnalysisRequest(**_valid_request(run_id="run_20260717_060000_   "))

    def test_run_mode_enum(self):
        for mode in ("official", "rehearsal", "demo"):
            req = AnalysisRequest(**_valid_request(run_mode=mode))
            assert req.run_mode.value == mode

    # ------------------------------------------------------------------
    # Finding 1: deadline_seconds must be in (0, 900]
    # ------------------------------------------------------------------

    def test_deadline_zero_rejected(self):
        with pytest.raises(ValidationError, match=r"deadline_seconds"):
            AnalysisRequest(**_valid_request(deadline_seconds=0))

    def test_deadline_negative_rejected(self):
        with pytest.raises(ValidationError, match=r"deadline_seconds"):
            AnalysisRequest(**_valid_request(deadline_seconds=-1))

    def test_deadline_over_900_rejected(self):
        with pytest.raises(ValidationError, match=r"deadline_seconds"):
            AnalysisRequest(**_valid_request(deadline_seconds=901))

    def test_deadline_at_boundary_900_accepted(self):
        req = AnalysisRequest(**_valid_request(deadline_seconds=900))
        assert req.deadline_seconds == 900

    def test_deadline_at_boundary_1_accepted(self):
        req = AnalysisRequest(**_valid_request(deadline_seconds=1))
        assert req.deadline_seconds == 1

    # ------------------------------------------------------------------
    # Finding 2: model is frozen after construction
    # ------------------------------------------------------------------

    def test_analysis_request_frozen(self):
        req = AnalysisRequest(**_valid_request())
        with pytest.raises(ValidationError):
            req.analysis_as_of = datetime(2027, 1, 1, tzinfo=UTC)

    # ------------------------------------------------------------------
    # Finding 3: real UTC offset zero, not just tzinfo presence
    # ------------------------------------------------------------------

    def test_rejects_positive_utc_offset(self):
        cst = datetime(2026, 7, 17, 14, 0, 0, tzinfo=PLUS8)
        with pytest.raises(ValidationError, match="UTC"):
            AnalysisRequest(**_valid_request(analysis_as_of=cst))

    def test_rejects_negative_utc_offset(self):
        pst = timezone(timedelta(hours=-8))
        naive_us = datetime(2026, 7, 16, 22, 0, 0, tzinfo=pst)
        with pytest.raises(ValidationError, match="UTC"):
            AnalysisRequest(**_valid_request(requested_at=naive_us))


# ===========================================================================
# EvidenceItem tests
# ===========================================================================


class TestEvidenceItem:
    def test_valid_construction(self):
        item = EvidenceItem(**_valid_evidence_item())
        assert item.evidence_id == "ev_001"
        assert item.reliability == Reliability.high

    def test_rejects_naive_fetched_at(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            EvidenceItem(**_valid_evidence_item(fetched_at=naive))

    def test_rejects_naive_published_at(self):
        naive = datetime(2026, 7, 16, 0, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            EvidenceItem(**_valid_evidence_item(published_at=naive))

    def test_rejects_non_utc_offset(self):
        """Finding 3."""
        with pytest.raises(ValidationError, match="UTC"):
            EvidenceItem(
                **_valid_evidence_item(
                    fetched_at=datetime(2026, 7, 17, 14, 0, 0, tzinfo=PLUS8)
                )
            )

    def test_rejects_empty_source_name(self):
        with pytest.raises(ValidationError, match="empty"):
            EvidenceItem(**_valid_evidence_item(source_name=""))

    def test_rejects_blank_source_url(self):
        with pytest.raises(ValidationError, match="source_url"):
            EvidenceItem(**_valid_evidence_item(source_url="   "))

    def test_rejects_non_http_source_url(self):
        with pytest.raises(ValidationError, match=r"HTTP\(S\) URL"):
            EvidenceItem(**_valid_evidence_item(source_url="not a url"))

    @pytest.mark.parametrize(
        "source_url",
        [
            "https://exa mple.com/source",
            "https://example.com:notaport/source",
            "https://user:secret@example.com/source",
        ],
    )
    def test_rejects_malformed_or_credentialed_source_url(self, source_url):
        with pytest.raises(ValidationError, match=r"HTTP\(S\) URL"):
            EvidenceItem(**_valid_evidence_item(source_url=source_url))

    def test_source_url_is_stripped(self):
        item = EvidenceItem(
            **_valid_evidence_item(source_url="  https://example.com/source  ")
        )
        assert item.source_url == "https://example.com/source"

    def test_rejects_blank_content_reference(self):
        with pytest.raises(ValidationError, match="empty"):
            EvidenceItem(**_valid_evidence_item(content_reference="   "))

    def test_rejects_blank_normalized_fact(self):
        with pytest.raises(ValidationError, match="empty"):
            EvidenceItem(**_valid_evidence_item(normalized_fact=""))

    def test_rejects_blank_independence_group(self):
        with pytest.raises(ValidationError, match="empty"):
            EvidenceItem(**_valid_evidence_item(independence_group=" "))

    def test_rejects_invalid_content_hash(self):
        with pytest.raises(ValidationError, match="64 lowercase hex"):
            EvidenceItem(**_valid_evidence_item(content_hash="short"))

    def test_rejects_uppercase_hash(self):
        with pytest.raises(ValidationError, match="64 lowercase hex"):
            EvidenceItem(**_valid_evidence_item(content_hash="A" * 64))

    def test_evidence_id_format(self):
        with pytest.raises(ValidationError, match="ev_NNN"):
            EvidenceItem(**_valid_evidence_item(evidence_id="bad"))

    def test_rejects_deprecated_fetched_time_field(self):
        data = _valid_evidence_item()
        data["fetched_time"] = NOW
        with pytest.raises(ValidationError):
            EvidenceItem(**data)

    def test_rejects_deprecated_fetched_space_time_field(self):
        data = _valid_evidence_item()
        data["fetched time"] = NOW
        with pytest.raises(ValidationError):
            EvidenceItem(**data)

    def test_rejects_stance_field(self):
        data = _valid_evidence_item()
        data["stance"] = "supports"
        with pytest.raises(ValidationError):
            EvidenceItem(**data)

    def test_cache_consistency_true_requires_time(self):
        with pytest.raises(ValidationError, match="cache_time to be set"):
            EvidenceItem(**_valid_evidence_item(is_cached=True, cache_time=None))

    def test_cache_consistency_false_requires_none(self):
        with pytest.raises(ValidationError, match="cache_time=None"):
            EvidenceItem(
                **_valid_evidence_item(is_cached=False, cache_time=NOW)
            )

    def test_cache_consistent_true(self):
        item = EvidenceItem(
            **_valid_evidence_item(is_cached=True, cache_time=NOW)
        )
        assert item.is_cached is True
        assert item.cache_time == NOW

    def test_null_asset_for_market_wide(self):
        item = EvidenceItem(**_valid_evidence_item(asset=None))
        assert item.asset is None

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            EvidenceItem(**_valid_evidence_item(unknown="x"))

    # ------------------------------------------------------------------
    # Second-review Finding 3: fetched_at vs published_at ordering deferred
    #
    # evidence-contracts.md §3 permits `fetched_at` to precede `published_at`
    # by up to the configured clock tolerance (Task 1b Settings). A zero-
    # tolerance rule is stricter than the contract, not a valid subset, so
    # the whole comparison is deferred. Task 5 (Evidence Processor) will
    # combine the tolerance with a ledger-cutoff check.
    # ------------------------------------------------------------------

    def test_fetched_before_published_currently_accepted(self):
        item = EvidenceItem(
            **_valid_evidence_item(
                fetched_at=datetime(2026, 7, 15, 0, 0, 0, tzinfo=UTC),
                published_at=datetime(2026, 7, 16, 0, 0, 0, tzinfo=UTC),
            )
        )
        assert item.fetched_at < item.published_at

    def test_fetched_after_published_accepted(self):
        item = EvidenceItem(
            **_valid_evidence_item(
                fetched_at=datetime(2026, 7, 16, 12, 0, 0, tzinfo=UTC),
                published_at=datetime(2026, 7, 16, 0, 0, 0, tzinfo=UTC),
            )
        )
        assert item.fetched_at > item.published_at

    def test_missing_published_at_ok(self):
        item = EvidenceItem(**_valid_evidence_item(published_at=None))
        assert item.published_at is None

    # ------------------------------------------------------------------
    # Second-review Finding 4: EvidenceItem.query_or_parameters non-blank
    # ------------------------------------------------------------------

    def test_query_or_parameters_nonblank(self):
        with pytest.raises(ValidationError, match="query_or_parameters"):
            EvidenceItem(**_valid_evidence_item(query_or_parameters=""))

    def test_query_or_parameters_stripped(self):
        item = EvidenceItem(
            **_valid_evidence_item(query_or_parameters="  symbol=BTCUSDT  ")
        )
        assert item.query_or_parameters == "symbol=BTCUSDT"


# ===========================================================================
# EvidenceDraft tests
# ===========================================================================


class TestEvidenceDraft:
    def test_valid_construction(self):
        draft = EvidenceDraft(
            asset="BTC",
            source_type="market",
            source_name="Binance Spot",
            fetched_at=NOW,
            query_or_parameters="symbol=BTCUSDT",
            content_reference="close price",
            normalized_fact="BTC close was 100000.",
            source_record_id="rec_001",
        )
        assert draft.source_record_id == "rec_001"

    def test_has_no_evidence_id(self):
        with pytest.raises(ValidationError):
            EvidenceDraft(
                asset="BTC",
                source_type="market",
                source_name="Binance",
                fetched_at=NOW,
                query_or_parameters="x",
                content_reference="ref",
                normalized_fact="fact",
                evidence_id="ev_001",
            )

    def test_cache_consistency(self):
        with pytest.raises(ValidationError, match="cache_time to be set"):
            EvidenceDraft(
                asset="BTC",
                source_type="market",
                source_name="Binance",
                fetched_at=NOW,
                query_or_parameters="x",
                content_reference="ref",
                normalized_fact="fact",
                is_cached=True,
                cache_time=None,
            )

    def test_draft_query_or_parameters_nonblank(self):
        """Second-review Finding 4."""
        with pytest.raises(ValidationError, match="query_or_parameters"):
            EvidenceDraft(
                asset="BTC",
                source_type="market",
                source_name="Binance",
                fetched_at=NOW,
                query_or_parameters="   ",
                content_reference="ref",
                normalized_fact="fact",
            )

    def test_draft_rejects_blank_source_url(self):
        with pytest.raises(ValidationError, match="source_url"):
            EvidenceDraft(
                asset="BTC",
                source_type="market",
                source_name="Binance",
                source_url="   ",
                fetched_at=NOW,
                query_or_parameters="x",
                content_reference="ref",
                normalized_fact="fact",
            )

    def test_draft_rejects_non_http_source_url(self):
        with pytest.raises(ValidationError, match=r"HTTP\(S\) URL"):
            EvidenceDraft(
                asset="BTC",
                source_type="market",
                source_name="Binance",
                source_url="ftp://example.com/source",
                fetched_at=NOW,
                query_or_parameters="x",
                content_reference="ref",
                normalized_fact="fact",
            )

    def test_draft_source_record_id_rejects_blank(self):
        with pytest.raises(ValidationError, match="source_record_id"):
            EvidenceDraft(
                asset="BTC",
                source_type="market",
                source_name="Binance",
                fetched_at=NOW,
                query_or_parameters="x",
                content_reference="ref",
                normalized_fact="fact",
                source_record_id="   ",
            )

    def test_draft_optional_text_is_stripped(self):
        draft = EvidenceDraft(
            asset="BTC",
            source_type="market",
            source_name="Binance",
            source_url="  https://example.com/source  ",
            fetched_at=NOW,
            query_or_parameters="x",
            content_reference="ref",
            normalized_fact="fact",
            source_record_id="  rec_001  ",
        )
        assert draft.source_url == "https://example.com/source"
        assert draft.source_record_id == "rec_001"


# ===========================================================================
# ClaimEvidenceLink tests
# ===========================================================================


class TestClaimEvidenceLink:
    def test_valid_construction(self):
        link = ClaimEvidenceLink(**_valid_link())
        assert link.stance == Stance.supports

    def test_accepts_supports(self):
        link = ClaimEvidenceLink(**_valid_link(stance="supports"))
        assert link.stance == Stance.supports

    def test_accepts_opposes(self):
        link = ClaimEvidenceLink(**_valid_link(stance="opposes"))
        assert link.stance == Stance.opposes

    def test_accepts_neutral(self):
        link = ClaimEvidenceLink(**_valid_link(stance="neutral"))
        assert link.stance == Stance.neutral

    def test_rejects_invalid_stance(self):
        with pytest.raises(ValidationError):
            ClaimEvidenceLink(**_valid_link(stance="strong"))

    def test_rejects_extra_stance_values(self):
        with pytest.raises(ValidationError):
            ClaimEvidenceLink(**_valid_link(stance="agree"))

    def test_claim_id_format(self):
        with pytest.raises(ValidationError, match="cl_NNN"):
            ClaimEvidenceLink(**_valid_link(claim_id="bad"))

    def test_evidence_id_format(self):
        with pytest.raises(ValidationError, match="ev_NNN"):
            ClaimEvidenceLink(**_valid_link(evidence_id="bad"))

    def test_rejects_blank_reason(self):
        with pytest.raises(ValidationError, match="empty"):
            ClaimEvidenceLink(**_valid_link(reason=""))

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ClaimEvidenceLink(**_valid_link(source="x"))

    def test_link_has_all_required_fields(self):
        """Sanity check that a link exposes the four required fields."""
        link = ClaimEvidenceLink(**_valid_link())
        assert hasattr(link, "claim_id")
        assert hasattr(link, "evidence_id")
        assert hasattr(link, "stance")
        assert hasattr(link, "reason")


# ===========================================================================
# Finding 5: Evidence List projection
# ===========================================================================


class TestEvidenceListProjection:
    """EvidenceListRow + project_evidence_list per requirements.md 5.7 and
    design.md §5.1.

    Cardinality decision: `related_claim` is `list[str]` because
    evidence-contracts.md §8 states an EvidenceItem may support one Claim and
    oppose another. The Evidence List projects one row per EvidenceItem, so
    per-row related_claim is the collection of Claim IDs pointing to that item.
    """

    def test_evidence_list_row_shape(self):
        row = EvidenceListRow(
            source="Binance Spot",
            fetched_at=NOW,
            content_reference="2026-07-16 UTC close",
            related_claim=["cl_001"],
        )
        assert row.source == "Binance Spot"
        assert row.fetched_at == NOW
        assert row.related_claim == ["cl_001"]

    def test_evidence_list_row_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            EvidenceListRow(
                source="x",
                fetched_at=NOW,
                content_reference="y",
                related_claim=[],
                bogus="z",
            )

    def test_projection_row_frozen(self):
        row = EvidenceListRow(
            source="s", fetched_at=NOW, content_reference="c", related_claim=[]
        )
        with pytest.raises(ValidationError):
            row.source = "other"

    def test_projection_mapping_deterministic(self):
        item = EvidenceItem(**_valid_evidence_item())
        link = ClaimEvidenceLink(**_valid_link())
        rows = project_evidence_list([item], [link])
        assert len(rows) == 1
        row = rows[0]
        assert row.source == item.source_name
        assert row.fetched_at == item.fetched_at
        assert row.content_reference == item.content_reference
        assert row.related_claim == ["cl_001"]

    def test_projection_multi_claim_evidence(self):
        """§8: one Evidence may support one Claim and oppose another."""
        item = EvidenceItem(**_valid_evidence_item())
        link_a = ClaimEvidenceLink(**_valid_link(claim_id="cl_001", stance="supports"))
        link_b = ClaimEvidenceLink(**_valid_link(claim_id="cl_002", stance="opposes"))
        rows = project_evidence_list([item], [link_a, link_b])
        assert rows[0].related_claim == ["cl_001", "cl_002"]

    def test_projection_evidence_with_no_links(self):
        item = EvidenceItem(**_valid_evidence_item())
        rows = project_evidence_list([item], [])
        assert rows[0].related_claim == []

    def test_projection_dedupes_repeated_claim_ids(self):
        item = EvidenceItem(**_valid_evidence_item())
        link_a = ClaimEvidenceLink(**_valid_link(claim_id="cl_001", stance="supports"))
        link_b = ClaimEvidenceLink(**_valid_link(claim_id="cl_001", stance="opposes"))
        rows = project_evidence_list([item], [link_a, link_b])
        assert rows[0].related_claim == ["cl_001"]

    def test_projection_uses_source_name_not_source_field(self):
        """We must NOT rename EvidenceItem.source_name to source; the projection
        maps source_name into the projection's source field."""
        item = EvidenceItem(**_valid_evidence_item())
        rows = project_evidence_list([item], [])
        assert item.source_name == "Binance Spot"
        assert rows[0].source == "Binance Spot"

    # ------------------------------------------------------------------
    # Second-review Finding 4 + 5: EvidenceListRow public validation
    # ------------------------------------------------------------------

    def test_row_source_nonblank(self):
        with pytest.raises(ValidationError, match="source"):
            EvidenceListRow(
                source="   ",
                fetched_at=NOW,
                content_reference="ref",
                related_claim=[],
            )

    def test_row_content_reference_nonblank(self):
        with pytest.raises(ValidationError, match="content_reference"):
            EvidenceListRow(
                source="s",
                fetched_at=NOW,
                content_reference="",
                related_claim=[],
            )

    def test_row_fetched_at_utc(self):
        with pytest.raises(ValidationError, match="UTC"):
            EvidenceListRow(
                source="s",
                fetched_at=datetime(2026, 7, 17, 14, 0, 0, tzinfo=PLUS8),
                content_reference="r",
                related_claim=[],
            )

    def test_row_related_claim_malformed_rejected(self):
        with pytest.raises(ValidationError, match="cl_NNN"):
            EvidenceListRow(
                source="s",
                fetched_at=NOW,
                content_reference="r",
                related_claim=["not-valid"],
            )

    def test_row_related_claim_duplicate_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            EvidenceListRow(
                source="s",
                fetched_at=NOW,
                content_reference="r",
                related_claim=["cl_001", "cl_001"],
            )

    def test_row_related_claim_unsorted_rejected(self):
        with pytest.raises(ValidationError, match="sorted"):
            EvidenceListRow(
                source="s",
                fetched_at=NOW,
                content_reference="r",
                related_claim=["cl_002", "cl_001"],
            )

    def test_row_related_claim_sorted_accepted(self):
        row = EvidenceListRow(
            source="s",
            fetched_at=NOW,
            content_reference="r",
            related_claim=["cl_001", "cl_002"],
        )
        assert row.related_claim == ["cl_001", "cl_002"]


# ===========================================================================
# Claim tests
# ===========================================================================


class TestClaim:
    def test_valid_fact(self):
        claim = Claim(**_valid_claim())
        assert claim.claim_type == ClaimType.fact
        assert claim.based_on_claim_ids == []

    def test_fact_rejects_dependencies(self):
        with pytest.raises(ValidationError, match="fact.*empty"):
            Claim(**_valid_claim(based_on_claim_ids=["cl_002"]))

    def test_inference_requires_dependencies(self):
        with pytest.raises(ValidationError, match="inference.*non-empty"):
            Claim(
                **_valid_claim(
                    claim_id="cl_002",
                    claim_type="inference",
                    based_on_claim_ids=[],
                )
            )

    def test_inference_valid(self):
        claim = Claim(
            **_valid_claim(
                claim_id="cl_002",
                claim_type="inference",
                based_on_claim_ids=["cl_001"],
            )
        )
        assert claim.claim_type == ClaimType.inference

    def test_conclusion_requires_dependencies(self):
        with pytest.raises(ValidationError, match="conclusion.*non-empty"):
            Claim(
                **_valid_claim(
                    claim_id="cl_003",
                    claim_type="conclusion",
                    based_on_claim_ids=[],
                )
            )

    def test_conclusion_valid(self):
        claim = Claim(
            **_valid_claim(
                claim_id="cl_003",
                claim_type="conclusion",
                based_on_claim_ids=["cl_001"],
            )
        )
        assert claim.claim_type == ClaimType.conclusion

    def test_claim_id_format(self):
        with pytest.raises(ValidationError, match="cl_NNN"):
            Claim(**_valid_claim(claim_id="ev_001"))

    def test_rejects_blank_text(self):
        with pytest.raises(ValidationError, match="empty"):
            Claim(**_valid_claim(text=""))

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Claim(**_valid_claim(extra_field="x"))

    # ------------------------------------------------------------------
    # Finding 6 (MODEL_LOCAL half): claim assets shape
    # ------------------------------------------------------------------

    def test_claim_assets_empty_rejected(self):
        with pytest.raises(ValidationError, match="1 or 2"):
            Claim(**_valid_claim(assets=[]))

    def test_claim_assets_three_rejected(self):
        with pytest.raises(ValidationError, match="1 or 2"):
            Claim(**_valid_claim(assets=["BTC", "ETH", "SOL"]))

    def test_claim_assets_duplicate_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            Claim(**_valid_claim(assets=["BTC", "BTC"]))

    # ------------------------------------------------------------------
    # Finding 7 (MODEL_LOCAL half): based_on_claim_ids format + uniqueness
    # ------------------------------------------------------------------

    def test_based_on_claim_ids_format(self):
        with pytest.raises(ValidationError, match="cl_"):
            Claim(
                **_valid_claim(
                    claim_id="cl_002",
                    claim_type="inference",
                    based_on_claim_ids=["not-a-valid-id"],
                )
            )

    def test_based_on_claim_ids_unique(self):
        with pytest.raises(ValidationError, match="unique"):
            Claim(
                **_valid_claim(
                    claim_id="cl_002",
                    claim_type="inference",
                    based_on_claim_ids=["cl_001", "cl_001"],
                )
            )

    # ------------------------------------------------------------------
    # Finding 10 (MODEL_LOCAL half): nonblank list entries
    # ------------------------------------------------------------------

    def test_claim_limitations_nonblank(self):
        with pytest.raises(ValidationError, match="blank"):
            Claim(**_valid_claim(limitations=["  "]))

    def test_claim_invalidation_conditions_nonblank(self):
        with pytest.raises(ValidationError, match="blank"):
            Claim(**_valid_claim(invalidation_conditions=[""]))


# ===========================================================================
# TimeRange and MarketContext tests
# ===========================================================================


class TestTimeRange:
    def test_valid(self):
        tr = TimeRange(start="2026-07-03", end="2026-07-17")
        assert tr.start == "2026-07-03"

    def test_rejects_invalid_format(self):
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            TimeRange(start="07-03-2026", end="2026-07-17")

    def test_rejects_start_after_end(self):
        with pytest.raises(ValidationError, match="start must be <= end"):
            TimeRange(start="2026-07-18", end="2026-07-17")

    def test_same_start_end_valid(self):
        tr = TimeRange(start="2026-07-17", end="2026-07-17")
        assert tr.start == tr.end

    # Finding 10: real calendar dates only
    def test_time_range_rejects_month_out_of_range(self):
        with pytest.raises(ValidationError, match="calendar"):
            TimeRange(start="2026-99-98", end="2026-99-99")

    def test_time_range_rejects_feb_30(self):
        with pytest.raises(ValidationError, match="calendar"):
            TimeRange(start="2026-02-30", end="2026-03-01")


class TestMarketContext:
    def test_valid(self):
        ctx = MarketContext(
            summary="BTC market context",
            time_range={"start": "2026-07-03", "end": "2026-07-17"},
        )
        assert ctx.summary == "BTC market context"

    def test_rejects_blank_summary(self):
        with pytest.raises(ValidationError, match="empty"):
            MarketContext(
                summary="   ",
                time_range={"start": "2026-07-03", "end": "2026-07-17"},
            )


# ===========================================================================
# EvidenceLedger / ConflictIndicator / DegradationEvent tests
# ===========================================================================


class TestEvidenceLedger:
    def test_ledger_valid_with_items(self):
        item = EvidenceItem(**_valid_evidence_item())
        ledger = EvidenceLedger(
            run_id="run_20260717_060000_ab12",
            analysis_as_of=NOW,
            run_mode="official",
            items=[item],
        )
        assert ledger.items == [item]
        assert ledger.schema_version == "1.0"

    def test_rejects_naive_analysis_as_of(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            EvidenceLedger(
                run_id="run_20260717_060000_ab12",
                analysis_as_of=naive,
                run_mode="official",
            )

    # ------------------------------------------------------------------
    # Finding 10: run_id format
    # ------------------------------------------------------------------

    def test_ledger_run_id_format(self):
        with pytest.raises(ValidationError, match="run_YYYYMMDD"):
            EvidenceLedger(run_id="bad", analysis_as_of=NOW, run_mode="official")

    def test_ledger_schema_version_rejects_blank(self):
        with pytest.raises(ValidationError, match="schema_version"):
            EvidenceLedger(
                schema_version="   ",
                run_id="run_20260717_060000_ab12",
                analysis_as_of=NOW,
                run_mode="official",
                degradation_events=[DegradationEvent(**_valid_degradation())],
            )

    def test_ledger_schema_version_is_stripped(self):
        ledger = EvidenceLedger(
            schema_version="  1.0  ",
            run_id="run_20260717_060000_ab12",
            analysis_as_of=NOW,
            run_mode="official",
            degradation_events=[DegradationEvent(**_valid_degradation())],
        )
        assert ledger.schema_version == "1.0"

    # ------------------------------------------------------------------
    # Finding 11: sorting, empty-requires-degradation, duplicate IDs
    # ------------------------------------------------------------------

    def test_ledger_empty_requires_degradation(self):
        with pytest.raises(ValidationError, match="degradation"):
            EvidenceLedger(
                run_id="run_20260717_060000_ab12",
                analysis_as_of=NOW,
                run_mode="official",
            )

    def test_ledger_empty_valid_with_degradation(self):
        ledger = EvidenceLedger(
            run_id="run_20260717_060000_ab12",
            analysis_as_of=NOW,
            run_mode="official",
            degradation_events=[DegradationEvent(**_valid_degradation())],
        )
        assert ledger.items == []

    def test_ledger_items_sorted_by_evidence_id(self):
        item_a = EvidenceItem(**_valid_evidence_item(evidence_id="ev_002"))
        item_b = EvidenceItem(**_valid_evidence_item(evidence_id="ev_001"))
        with pytest.raises(ValidationError, match="sorted"):
            EvidenceLedger(
                run_id="run_20260717_060000_ab12",
                analysis_as_of=NOW,
                run_mode="official",
                items=[item_a, item_b],
            )

    def test_ledger_rejects_duplicate_evidence_id(self):
        item_a = EvidenceItem(**_valid_evidence_item(evidence_id="ev_001"))
        item_b = EvidenceItem(**_valid_evidence_item(evidence_id="ev_001"))
        with pytest.raises(ValidationError, match="duplicate"):
            EvidenceLedger(
                run_id="run_20260717_060000_ab12",
                analysis_as_of=NOW,
                run_mode="official",
                items=[item_a, item_b],
            )

    # Finding 2: frozen
    def test_evidence_ledger_frozen(self):
        ledger = EvidenceLedger(
            run_id="run_20260717_060000_ab12",
            analysis_as_of=NOW,
            run_mode="official",
            degradation_events=[DegradationEvent(**_valid_degradation())],
        )
        with pytest.raises(ValidationError):
            ledger.analysis_as_of = datetime(2027, 1, 1, tzinfo=UTC)


class TestConflictIndicator:
    def test_valid(self):
        ci = ConflictIndicator(
            claim_id="cl_001",
            supporting_evidence_ids=["ev_001"],
            opposing_evidence_ids=["ev_002"],
            independence_groups=["binance.com", "coingecko.com"],
        )
        assert ci.rule_version == "1.0"

    # Finding 10: ID formats
    def test_conflict_indicator_claim_id_format(self):
        with pytest.raises(ValidationError, match="cl_NNN"):
            ConflictIndicator(claim_id="bad")

    def test_conflict_indicator_supporting_ids_format(self):
        with pytest.raises(ValidationError, match="ev_NNN"):
            ConflictIndicator(claim_id="cl_001", supporting_evidence_ids=["nope"])

    def test_conflict_indicator_opposing_ids_format(self):
        with pytest.raises(ValidationError, match="ev_NNN"):
            ConflictIndicator(claim_id="cl_001", opposing_evidence_ids=["nope"])

    def test_conflict_indicator_rejects_blank_independence_group(self):
        with pytest.raises(ValidationError, match="independence_groups"):
            ConflictIndicator(claim_id="cl_001", independence_groups=["   "])

    def test_conflict_indicator_independence_groups_are_stripped(self):
        indicator = ConflictIndicator(
            claim_id="cl_001", independence_groups=["  binance.com  "]
        )
        assert indicator.independence_groups == ["binance.com"]

    def test_conflict_indicator_rejects_blank_rule_version(self):
        with pytest.raises(ValidationError, match="rule_version"):
            ConflictIndicator(claim_id="cl_001", rule_version="   ")

    def test_conflict_indicator_rule_version_is_stripped(self):
        indicator = ConflictIndicator(claim_id="cl_001", rule_version="  1.0  ")
        assert indicator.rule_version == "1.0"


class TestDegradationEvent:
    def test_valid(self):
        de = DegradationEvent(**_valid_degradation())
        assert de.stage == "market_worker"

    def test_rejects_naive_timestamp(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            DegradationEvent(**_valid_degradation(timestamp=datetime(2026, 7, 17, 6)))

    # Finding 10: nonblank text fields
    def test_degradation_event_stage_nonblank(self):
        with pytest.raises(ValidationError, match="empty"):
            DegradationEvent(**_valid_degradation(stage=""))

    def test_degradation_event_event_type_nonblank(self):
        with pytest.raises(ValidationError, match="empty"):
            DegradationEvent(**_valid_degradation(event_type=" "))

    def test_degradation_event_source_nonblank(self):
        with pytest.raises(ValidationError, match="empty"):
            DegradationEvent(**_valid_degradation(source=""))

    def test_degradation_event_message_nonblank(self):
        with pytest.raises(ValidationError, match="empty"):
            DegradationEvent(**_valid_degradation(message="  "))


# ===========================================================================
# InvalidationCondition tests (Finding 12)
# ===========================================================================


class TestInvalidationCondition:
    def test_qualitative_only(self):
        ic = InvalidationCondition(text="Market sentiment reverses")
        assert ic.metric is None
        assert ic.threshold is None

    def test_quantitative(self):
        ic = InvalidationCondition(
            text="Close drops below 68000",
            metric="close",
            operator="lt",
            threshold=68000.0,
            basis_evidence_id="ev_007",
        )
        assert ic.operator == InvalidationOperator.lt

    def test_rejects_blank_text(self):
        with pytest.raises(ValidationError, match="empty"):
            InvalidationCondition(text="")

    def test_rejects_blank_metric(self):
        with pytest.raises(ValidationError, match="empty or blank"):
            InvalidationCondition(
                text="x",
                metric="   ",
                operator="lt",
                threshold=1.0,
                basis_evidence_id="ev_001",
            )

    def test_metric_is_stripped(self):
        condition = InvalidationCondition(
            text="x",
            metric="  close  ",
            operator="lt",
            threshold=1.0,
            basis_evidence_id="ev_001",
        )
        assert condition.metric == "close"

    def test_invalidation_partial_structured_rejected_only_metric(self):
        with pytest.raises(ValidationError, match="all of"):
            InvalidationCondition(text="x", metric="close")

    def test_invalidation_partial_structured_rejected_missing_basis(self):
        with pytest.raises(ValidationError, match="all of"):
            InvalidationCondition(
                text="x", metric="close", operator="lt", threshold=1.0
            )

    def test_invalidation_partial_structured_rejected_missing_operator(self):
        with pytest.raises(ValidationError, match="all of"):
            InvalidationCondition(
                text="x", metric="close", threshold=1.0, basis_evidence_id="ev_001"
            )

    def test_invalidation_basis_id_format(self):
        with pytest.raises(ValidationError, match="ev_NNN"):
            InvalidationCondition(
                text="x",
                metric="close",
                operator="lt",
                threshold=1.0,
                basis_evidence_id="bad",
            )


# ===========================================================================
# MarketRegime tests (Finding 14)
# ===========================================================================


class TestMarketRegime:
    def test_valid(self):
        mr = MarketRegime(
            asset="BTC",
            label="range_bound",
            as_of="2026-05-31",
            window_days=30,
            metrics={"return_window": -0.0488, "realized_vol_pctile": 0.35},
            thresholds={"trend_return_abs_min": 0.10, "range_return_abs_max": 0.05},
            evidence_id="ev_012",
        )
        assert mr.label == RegimeLabel.range_bound

    def test_all_classified_labels(self):
        for label in [
            "trending_up", "trending_down", "range_bound",
            "high_volatility", "mixed",
        ]:
            mr = MarketRegime(
                asset="BTC",
                label=label,
                as_of="2026-05-31",
                window_days=30,
                metrics={"x": 1.0},
                thresholds={"y": 2.0},
                evidence_id="ev_001",
            )
            assert mr.label.value == label

    def test_rejects_invalid_label(self):
        with pytest.raises(ValidationError):
            MarketRegime(
                asset="BTC",
                label="crash",
                as_of="2026-05-31",
                window_days=30,
                metrics={"x": 1.0},
                thresholds={"y": 2.0},
                evidence_id="ev_001",
            )

    def test_regime_unavailable_allows_empty_payload(self):
        """Finding 14: label=unavailable permits empty metrics/thresholds and
        null evidence_id."""
        mr = MarketRegime(
            asset="BTC",
            label="unavailable",
            as_of="2026-05-31",
            window_days=30,
            metrics={},
            thresholds={},
            evidence_id=None,
        )
        assert mr.label == RegimeLabel.unavailable
        assert mr.evidence_id is None

    def test_regime_non_unavailable_requires_metrics(self):
        with pytest.raises(ValidationError, match="metrics"):
            MarketRegime(
                asset="BTC",
                label="range_bound",
                as_of="2026-05-31",
                window_days=30,
                metrics={},
                thresholds={"y": 2.0},
                evidence_id="ev_001",
            )

    def test_regime_non_unavailable_requires_thresholds(self):
        with pytest.raises(ValidationError, match="thresholds"):
            MarketRegime(
                asset="BTC",
                label="range_bound",
                as_of="2026-05-31",
                window_days=30,
                metrics={"x": 1.0},
                thresholds={},
                evidence_id="ev_001",
            )

    def test_regime_non_unavailable_requires_evidence_id(self):
        with pytest.raises(ValidationError, match="evidence_id"):
            MarketRegime(
                asset="BTC",
                label="range_bound",
                as_of="2026-05-31",
                window_days=30,
                metrics={"x": 1.0},
                thresholds={"y": 2.0},
                evidence_id=None,
            )

    def test_regime_evidence_id_format(self):
        """Finding 10: MarketRegime.evidence_id must match ev_NNN."""
        with pytest.raises(ValidationError, match="ev_NNN"):
            MarketRegime(
                asset="BTC",
                label="range_bound",
                as_of="2026-05-31",
                window_days=30,
                metrics={"x": 1.0},
                thresholds={"y": 2.0},
                evidence_id="bad",
            )

    def test_regime_as_of_real_date(self):
        with pytest.raises(ValidationError, match="calendar"):
            MarketRegime(
                asset="BTC",
                label="range_bound",
                as_of="2026-13-40",
                window_days=30,
                metrics={"x": 1.0},
                thresholds={"y": 2.0},
                evidence_id="ev_001",
            )


# ===========================================================================
# TrustScorecard tests (Finding 13)
# ===========================================================================


class TestTrustScorecardDimensions:
    def test_strong_independence_needs_3(self):
        SourceIndependenceDimension(level="strong", distinct_groups=3)
        with pytest.raises(ValidationError, match=">= 3"):
            SourceIndependenceDimension(level="strong", distinct_groups=2)
        with pytest.raises(ValidationError, match=">= 3"):
            SourceIndependenceDimension(level="strong", distinct_groups=0)

    def test_moderate_independence_needs_2(self):
        SourceIndependenceDimension(level="moderate", distinct_groups=2)
        with pytest.raises(ValidationError, match=r"== 2"):
            SourceIndependenceDimension(level="moderate", distinct_groups=1)
        with pytest.raises(ValidationError, match=r"== 2"):
            SourceIndependenceDimension(level="moderate", distinct_groups=3)

    def test_weak_independence_needs_1(self):
        SourceIndependenceDimension(level="weak", distinct_groups=1)
        with pytest.raises(ValidationError, match=r"== 1"):
            SourceIndependenceDimension(level="weak", distinct_groups=0)
        with pytest.raises(ValidationError, match=r"== 1"):
            SourceIndependenceDimension(level="weak", distinct_groups=2)

    def test_unavailable_independence_needs_0(self):
        SourceIndependenceDimension(level="unavailable", distinct_groups=0)
        with pytest.raises(ValidationError, match=r"== 0"):
            SourceIndependenceDimension(level="unavailable", distinct_groups=1)

    def test_independence_rejects_negative(self):
        with pytest.raises(ValidationError, match=">= 0"):
            SourceIndependenceDimension(level="unavailable", distinct_groups=-1)

    def test_strong_diversity_needs_3_types(self):
        SourceDiversityDimension(level="strong", distinct_source_types=3)
        with pytest.raises(ValidationError, match=">= 3"):
            SourceDiversityDimension(level="strong", distinct_source_types=2)

    def test_diversity_rejects_negative(self):
        with pytest.raises(ValidationError, match=">= 0"):
            SourceDiversityDimension(level="unavailable", distinct_source_types=-1)

    def test_reliability_mix_rejects_negative(self):
        with pytest.raises(ValidationError, match=">= 0"):
            ReliabilityMix(high=-1, medium=0, low=0)
        with pytest.raises(ValidationError, match=">= 0"):
            ReliabilityMix(high=0, medium=-1, low=0)
        with pytest.raises(ValidationError, match=">= 0"):
            ReliabilityMix(high=0, medium=0, low=-1)

    def test_consistency_conflict_forces_weak(self):
        ConsistencyDimension(
            level="weak", has_material_conflict=True, opposing_count=1
        )
        with pytest.raises(ValidationError, match="weak"):
            ConsistencyDimension(
                level="strong", has_material_conflict=True, opposing_count=1
            )
        with pytest.raises(ValidationError, match="weak"):
            ConsistencyDimension(
                level="moderate", has_material_conflict=True, opposing_count=1
            )

    def test_consistency_conflict_requires_opposing_count(self):
        """Second-review Finding 5: a material conflict implies at least one
        opposing evidence; opposing_count=0 with has_material_conflict=true
        is logically impossible."""
        with pytest.raises(ValidationError, match="opposing_count"):
            ConsistencyDimension(
                level="weak", has_material_conflict=True, opposing_count=0
            )

    def test_consistency_no_conflict_no_opposing_forces_strong(self):
        ConsistencyDimension(
            level="strong", has_material_conflict=False, opposing_count=0
        )
        with pytest.raises(ValidationError, match="strong"):
            ConsistencyDimension(
                level="moderate", has_material_conflict=False, opposing_count=0
            )

    def test_consistency_no_conflict_with_opposing_forces_moderate(self):
        ConsistencyDimension(
            level="moderate", has_material_conflict=False, opposing_count=1
        )
        with pytest.raises(ValidationError, match="moderate"):
            ConsistencyDimension(
                level="strong", has_material_conflict=False, opposing_count=1
            )

    def test_consistency_rejects_negative_opposing_count(self):
        with pytest.raises(ValidationError, match=">= 0"):
            ConsistencyDimension(
                level="strong", has_material_conflict=False, opposing_count=-1
            )

    def test_freshness_stale_cannot_be_strong(self):
        with pytest.raises(ValidationError, match="stale"):
            FreshnessDimension(
                level="strong",
                newest_evidence_age_hours=1.0,
                has_stale=True,
            )

    def test_freshness_no_age_requires_unavailable(self):
        FreshnessDimension(
            level="unavailable", newest_evidence_age_hours=None, has_stale=False
        )
        with pytest.raises(ValidationError, match="unavailable"):
            FreshnessDimension(
                level="strong", newest_evidence_age_hours=None, has_stale=False
            )

    def test_freshness_unavailable_rejects_usable_age(self):
        """Second-review finding: the rule is biconditional. `unavailable`
        applies only when no supporting Evidence carries a usable time
        (§16.2), so a usable age with level=unavailable is invalid."""
        with pytest.raises(ValidationError, match="unavailable"):
            FreshnessDimension(
                level="unavailable",
                newest_evidence_age_hours=1.0,
                has_stale=False,
            )

    def test_freshness_rejects_negative_age(self):
        with pytest.raises(ValidationError, match=">= 0"):
            FreshnessDimension(
                level="strong", newest_evidence_age_hours=-1.0, has_stale=False
            )


class TestTrustScorecard:
    def _make_scorecard(self, **overrides) -> dict:
        base = {
            "claim_id": "cl_003",
            "source_independence": {"level": "strong", "distinct_groups": 3},
            "source_diversity": {"level": "moderate", "distinct_source_types": 2},
            "reliability_mix": {"high": 2, "medium": 1, "low": 0},
            "consistency": {
                "level": "strong",
                "has_material_conflict": False,
                "opposing_count": 0,
            },
            "freshness": {
                "level": "strong",
                "newest_evidence_age_hours": 12.0,
                "has_stale": False,
            },
            "rationale": "三個獨立上游支持，無衝突。",
        }
        base.update(overrides)
        return base

    def test_valid_construction(self):
        sc = TrustScorecard(**self._make_scorecard())
        assert sc.source_independence.level == TrustLevel.strong
        assert sc.source_independence.distinct_groups == 3

    def test_rejects_blank_rationale(self):
        with pytest.raises(ValidationError, match="empty"):
            TrustScorecard(**self._make_scorecard(rationale=""))

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            TrustScorecard(**self._make_scorecard(extra="bad"))

    # Finding 10: claim_id format
    def test_scorecard_claim_id_format(self):
        with pytest.raises(ValidationError, match="cl_NNN"):
            TrustScorecard(**self._make_scorecard(claim_id="bad"))


# ===========================================================================
# AnalysisResult tests
# ===========================================================================


class TestAnalysisResult:
    def test_valid_construction(self):
        result = AnalysisResult(**_valid_result())
        assert result.confidence == Reliability.medium

    def test_rejects_naive_analysis_as_of(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            AnalysisResult(**_valid_result(analysis_as_of=naive))

    def test_rejects_blank_direct_answer(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalysisResult(**_valid_result(direct_answer=""))

    def test_rejects_blank_question(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalysisResult(**_valid_result(question="  "))

    def test_invalidation_conditions_are_structured(self):
        result = AnalysisResult(
            **_valid_result(
                invalidation_conditions=[
                    {
                        "text": "Close drops below 68000",
                        "metric": "close",
                        "operator": "lt",
                        "threshold": 68000.0,
                        "basis_evidence_id": "ev_007",
                    },
                ]
            )
        )
        assert isinstance(result.invalidation_conditions[0], InvalidationCondition)

    def test_market_regime_optional(self):
        result = AnalysisResult(**_valid_result(market_regime=None))
        assert result.market_regime is None

    def test_trust_scorecards_default_empty(self):
        result = AnalysisResult(**_valid_result())
        assert result.trust_scorecards == []

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**_valid_result(unknown="x"))

    # ------------------------------------------------------------------
    # Finding 10: result-level text/ID validation
    # ------------------------------------------------------------------

    def test_result_run_id_format(self):
        with pytest.raises(ValidationError, match="run_YYYYMMDD"):
            AnalysisResult(**_valid_result(run_id="bad"))

    def test_result_confidence_rationale_nonblank(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalysisResult(**_valid_result(confidence_rationale=" "))

    def test_result_limitations_nonblank(self):
        with pytest.raises(ValidationError, match="blank"):
            AnalysisResult(**_valid_result(limitations=[""]))

    def test_result_watch_items_nonblank(self):
        with pytest.raises(ValidationError, match="blank"):
            AnalysisResult(**_valid_result(watch_items=["  "]))

    def test_result_degradation_notes_nonblank(self):
        with pytest.raises(ValidationError, match="blank"):
            AnalysisResult(**_valid_result(degradation_notes=[""]))

    # ------------------------------------------------------------------
    # Finding 2: frozen
    # ------------------------------------------------------------------

    def test_analysis_result_frozen(self):
        result = AnalysisResult(**_valid_result())
        with pytest.raises(ValidationError):
            result.analysis_as_of = datetime(2027, 1, 1, tzinfo=UTC)

    # ------------------------------------------------------------------
    # Finding 9 (MODEL_LOCAL half): insufficient_data ⇒ confidence=low
    # ------------------------------------------------------------------

    def test_insufficient_data_forces_confidence_low(self):
        with pytest.raises(ValidationError, match="insufficient_data"):
            AnalysisResult(
                **_valid_result(
                    insufficient_data=True, confidence="high"
                )
            )

    def test_insufficient_data_true_low_ok(self):
        result = AnalysisResult(
            **_valid_result(insufficient_data=True, confidence="low")
        )
        assert result.insufficient_data is True

    # ------------------------------------------------------------------
    # Finding 6 (MODEL_AGGREGATE half): claim assets ⊆ result.assets,
    # time_range.end ≤ analysis_as_of
    # ------------------------------------------------------------------

    def test_result_claim_assets_subset(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact", assets=["ETH"])
        link = _valid_link(claim_id="cl_001", evidence_id="ev_001")
        with pytest.raises(ValidationError, match="assets"):
            AnalysisResult(
                **_valid_result(
                    assets=["BTC"],
                    claims=[fact],
                    claim_evidence_links=[link],
                )
            )

    def test_result_claim_time_range_within_cutoff(self):
        fact = _valid_claim(
            claim_id="cl_001",
            claim_type="fact",
            time_range={"start": "2027-01-01", "end": "2027-01-02"},
        )
        link = _valid_link(claim_id="cl_001", evidence_id="ev_001")
        with pytest.raises(ValidationError, match="time_range"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact], claim_evidence_links=[link]
                )
            )

    # ------------------------------------------------------------------
    # Finding 7: claim graph invariants
    # ------------------------------------------------------------------

    def test_duplicate_claim_id_rejected(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        dup = _valid_claim(claim_id="cl_001", claim_type="fact")
        link = _valid_link(claim_id="cl_001", evidence_id="ev_001")
        with pytest.raises(ValidationError, match="duplicate"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact, dup], claim_evidence_links=[link]
                )
            )

    def test_claim_self_dependency_rejected(self):
        """Handled at Claim layering (fact->empty) or AnalysisResult DAG.
        For an inference that lists itself, AnalysisResult must reject."""
        # Bypass Claim.layering by using an inference that lists itself.
        # Claim allows non-empty deps for inference, but self-dep is a
        # graph invariant caught in AnalysisResult.
        inf = _valid_claim(
            claim_id="cl_002",
            claim_type="inference",
            based_on_claim_ids=["cl_002"],
        )
        link = _valid_link(claim_id="cl_002", evidence_id="ev_001")
        with pytest.raises(ValidationError, match="self"):
            AnalysisResult(
                **_valid_result(
                    claims=[inf], claim_evidence_links=[link]
                )
            )

    def test_claim_cycle_rejected(self):
        """Any circular construction is rejected. Under the layering + ordering
        rules the ordering check will typically fire first (deps must be
        earlier); the cycle detector remains as defense-in-depth."""
        inf_a = _valid_claim(
            claim_id="cl_002",
            claim_type="inference",
            based_on_claim_ids=["cl_003"],
        )
        inf_b = _valid_claim(
            claim_id="cl_003",
            claim_type="inference",
            based_on_claim_ids=["cl_002"],
        )
        link_a = _valid_link(claim_id="cl_002", evidence_id="ev_001")
        link_b = _valid_link(claim_id="cl_003", evidence_id="ev_001")
        with pytest.raises(ValidationError):
            AnalysisResult(
                **_valid_result(
                    claims=[inf_a, inf_b],
                    claim_evidence_links=[link_a, link_b],
                )
            )

    def test_claim_missing_target_rejected(self):
        inf = _valid_claim(
            claim_id="cl_002",
            claim_type="inference",
            based_on_claim_ids=["cl_999"],
        )
        link = _valid_link(claim_id="cl_002", evidence_id="ev_001")
        with pytest.raises(ValidationError, match="missing"):
            AnalysisResult(
                **_valid_result(
                    claims=[inf], claim_evidence_links=[link]
                )
            )

    def test_inference_cannot_depend_on_conclusion(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        conclusion = _valid_claim(
            claim_id="cl_002",
            claim_type="conclusion",
            based_on_claim_ids=["cl_001"],
        )
        # An inference cannot depend on a conclusion.
        inf = _valid_claim(
            claim_id="cl_003",
            claim_type="inference",
            based_on_claim_ids=["cl_002"],
        )
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001"),
            _valid_link(claim_id="cl_002", evidence_id="ev_001"),
            _valid_link(claim_id="cl_003", evidence_id="ev_001"),
        ]
        with pytest.raises(ValidationError, match="inference"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact, conclusion, inf],
                    claim_evidence_links=links,
                )
            )

    # ------------------------------------------------------------------
    # Second-review Finding 1: inference ordering + conclusion type rules
    # ------------------------------------------------------------------

    def test_inference_forward_dependency_rejected(self):
        """An inference cannot depend on a later-listed claim."""
        # Inference cl_001 (position 0) depends on fact cl_002 (position 1).
        inf = _valid_claim(
            claim_id="cl_001",
            claim_type="inference",
            based_on_claim_ids=["cl_002"],
        )
        fact = _valid_claim(claim_id="cl_002", claim_type="fact")
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001"),
            _valid_link(claim_id="cl_002", evidence_id="ev_001"),
        ]
        with pytest.raises(ValidationError, match="earlier"):
            AnalysisResult(
                **_valid_result(claims=[inf, fact], claim_evidence_links=links)
            )

    def test_conclusion_cannot_depend_on_conclusion(self):
        """A conclusion can depend on a fact or inference only, never on
        another conclusion (evidence-contracts.md §7)."""
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        conc_a = _valid_claim(
            claim_id="cl_002",
            claim_type="conclusion",
            based_on_claim_ids=["cl_001"],
        )
        conc_b = _valid_claim(
            claim_id="cl_003",
            claim_type="conclusion",
            based_on_claim_ids=["cl_002"],
        )
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001"),
            _valid_link(claim_id="cl_002", evidence_id="ev_001"),
            _valid_link(claim_id="cl_003", evidence_id="ev_001"),
        ]
        with pytest.raises(
            ValidationError,
            match=r"conclusion cl_003 cannot depend on conclusion cl_002",
        ):
            AnalysisResult(
                **_valid_result(
                    claims=[fact, conc_a, conc_b],
                    claim_evidence_links=links,
                )
            )

    def test_ordered_fact_inference_conclusion_accepted(self):
        """Valid ordered chain: fact -> inference -> conclusion."""
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        inf = _valid_claim(
            claim_id="cl_002",
            claim_type="inference",
            based_on_claim_ids=["cl_001"],
        )
        conc = _valid_claim(
            claim_id="cl_003",
            claim_type="conclusion",
            based_on_claim_ids=["cl_002"],
        )
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001"),
            _valid_link(claim_id="cl_002", evidence_id="ev_001"),
            _valid_link(claim_id="cl_003", evidence_id="ev_001"),
        ]
        result = AnalysisResult(
            **_valid_result(
                claims=[fact, inf, conc], claim_evidence_links=links
            )
        )
        assert [c.claim_type for c in result.claims] == [
            ClaimType.fact,
            ClaimType.inference,
            ClaimType.conclusion,
        ]

    # ------------------------------------------------------------------
    # Second-review Finding 2: AnalysisResult.assets local shape
    # ------------------------------------------------------------------

    def test_result_assets_empty_rejected(self):
        with pytest.raises(ValidationError, match="1 or 2"):
            AnalysisResult(**_valid_result(assets=[]))

    def test_result_assets_three_rejected(self):
        with pytest.raises(ValidationError, match="1 or 2"):
            AnalysisResult(**_valid_result(assets=["BTC", "ETH", "SOL"]))

    def test_result_assets_duplicate_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            AnalysisResult(**_valid_result(assets=["BTC", "BTC"]))

    # ------------------------------------------------------------------
    # Second-review Finding 4: list entries are trimmed on the way in
    # ------------------------------------------------------------------

    def test_result_limitations_stripped(self):
        result = AnalysisResult(
            **_valid_result(limitations=["  Note.  ", "\tOther."])
        )
        assert result.limitations == ["Note.", "Other."]

    def test_result_watch_items_stripped(self):
        result = AnalysisResult(**_valid_result(watch_items=[" item "]))
        assert result.watch_items == ["item"]

    def test_result_degradation_notes_stripped(self):
        result = AnalysisResult(
            **_valid_result(degradation_notes=["  degraded  "])
        )
        assert result.degradation_notes == ["degraded"]

    # ------------------------------------------------------------------
    # Finding 8: link resolution + coverage
    # ------------------------------------------------------------------

    def test_link_claim_must_resolve(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        # Link references a claim_id that is not in claims.
        link = _valid_link(claim_id="cl_999", evidence_id="ev_001")
        with pytest.raises(ValidationError, match="link"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact], claim_evidence_links=[link]
                )
            )

    def test_fact_requires_non_neutral_link(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        # Only neutral link → invalid.
        link = _valid_link(
            claim_id="cl_001", evidence_id="ev_001", stance="neutral"
        )
        with pytest.raises(ValidationError, match="non-neutral"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact], claim_evidence_links=[link]
                )
            )

    def test_fact_no_link_rejected(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        with pytest.raises(ValidationError, match="non-neutral"):
            AnalysisResult(
                **_valid_result(claims=[fact], claim_evidence_links=[])
            )

    def test_inference_requires_supports_link(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        inf = _valid_claim(
            claim_id="cl_002",
            claim_type="inference",
            based_on_claim_ids=["cl_001"],
        )
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001", stance="supports"),
            # inference has only an opposes link
            _valid_link(claim_id="cl_002", evidence_id="ev_001", stance="opposes"),
        ]
        with pytest.raises(ValidationError, match="supporting"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact, inf], claim_evidence_links=links
                )
            )

    def test_conclusion_requires_supports_link(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        conclusion = _valid_claim(
            claim_id="cl_002",
            claim_type="conclusion",
            based_on_claim_ids=["cl_001"],
        )
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001", stance="supports"),
            _valid_link(claim_id="cl_002", evidence_id="ev_001", stance="neutral"),
        ]
        with pytest.raises(ValidationError, match="supporting"):
            AnalysisResult(
                **_valid_result(
                    insufficient_data=False,
                    claims=[fact, conclusion],
                    claim_evidence_links=links,
                )
            )

    def test_conclusion_insufficient_data_relaxes_coverage(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        conclusion = _valid_claim(
            claim_id="cl_002",
            claim_type="conclusion",
            based_on_claim_ids=["cl_001"],
        )
        links = [
            _valid_link(claim_id="cl_001", evidence_id="ev_001", stance="supports"),
            # no supports on conclusion, but insufficient_data=true relaxes it
        ]
        result = AnalysisResult(
            **_valid_result(
                insufficient_data=True,
                confidence="low",
                claims=[fact, conclusion],
                claim_evidence_links=links,
            )
        )
        assert result.insufficient_data is True

    # ------------------------------------------------------------------
    # Finding 13 (MODEL_AGGREGATE half): scorecards only reference conclusions
    # ------------------------------------------------------------------

    def test_scorecard_only_for_conclusion_claims(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        link = _valid_link(claim_id="cl_001", evidence_id="ev_001")
        sc = {
            "claim_id": "cl_001",  # references a fact, not a conclusion
            "source_independence": {"level": "strong", "distinct_groups": 3},
            "source_diversity": {"level": "strong", "distinct_source_types": 3},
            "reliability_mix": {"high": 2, "medium": 1, "low": 0},
            "consistency": {
                "level": "strong",
                "has_material_conflict": False,
                "opposing_count": 0,
            },
            "freshness": {
                "level": "strong",
                "newest_evidence_age_hours": 1.0,
                "has_stale": False,
            },
            "rationale": "x",
        }
        with pytest.raises(ValidationError, match="conclusion"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact],
                    claim_evidence_links=[link],
                    trust_scorecards=[sc],
                )
            )

    def test_scorecard_missing_claim_id_rejected(self):
        fact = _valid_claim(claim_id="cl_001", claim_type="fact")
        link = _valid_link(claim_id="cl_001", evidence_id="ev_001")
        sc = {
            "claim_id": "cl_999",  # not in claims
            "source_independence": {"level": "strong", "distinct_groups": 3},
            "source_diversity": {"level": "strong", "distinct_source_types": 3},
            "reliability_mix": {"high": 2, "medium": 1, "low": 0},
            "consistency": {
                "level": "strong",
                "has_material_conflict": False,
                "opposing_count": 0,
            },
            "freshness": {
                "level": "strong",
                "newest_evidence_age_hours": 1.0,
                "has_stale": False,
            },
            "rationale": "x",
        }
        with pytest.raises(ValidationError, match="scorecard"):
            AnalysisResult(
                **_valid_result(
                    claims=[fact],
                    claim_evidence_links=[link],
                    trust_scorecards=[sc],
                )
            )


# ---------------------------------------------------------------------------
# Data mode — evidence-contracts.md §14 requires run_config.json to record
# "requested and effective run/data modes". The run half landed with Task 1b;
# the data half did not, so a run could not state where its evidence came from.
# design.md §3 step 11 also names effective data mode and stage statuses as
# RunSummary content.
# ---------------------------------------------------------------------------


def _run_config_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "prompt_version": "planner-v1",
        "policy_version": "1.0",
        "run_id": "run_20260801_120000_abcd",
        "requested_run_mode": RunMode.official,
        "effective_run_mode": RunMode.official,
        "requested_data_mode": DataMode.live,
        "effective_data_mode": DataMode.live,
        "sanitized_request": {"question": "測試", "assets": ["BTC"]},
        "analysis_as_of": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "deadline_seconds": 900,
    }
    base.update(overrides)
    return base


def test_data_mode_has_the_three_contract_values() -> None:
    assert {mode.value for mode in DataMode} == {"live", "fixture", "recorded_fallback"}


@pytest.mark.parametrize(
    ("run_mode", "expected"),
    [
        (RunMode.official, DataMode.live),
        (RunMode.demo, DataMode.live),
        (RunMode.rehearsal, DataMode.fixture),
    ],
)
def test_requested_data_mode_follows_the_run_mode_policy(
    run_mode: RunMode, expected: DataMode
) -> None:
    """`demo` starts live and may degrade later; only `rehearsal` starts on fixtures."""
    assert DataMode.requested_for(run_mode) is expected


def test_run_config_snapshot_requires_both_data_modes() -> None:
    kwargs = _run_config_kwargs()
    kwargs.pop("effective_data_mode")
    with pytest.raises(ValidationError):
        RunConfigSnapshot(**kwargs)


def test_official_run_may_not_report_fixture_data() -> None:
    """Rule 7: `official` never loads fixtures or recorded responses."""
    with pytest.raises(ValidationError):
        RunConfigSnapshot(**_run_config_kwargs(effective_data_mode=DataMode.fixture))


def test_official_run_may_not_report_recorded_fallback() -> None:
    with pytest.raises(ValidationError):
        RunConfigSnapshot(
            **_run_config_kwargs(effective_data_mode=DataMode.recorded_fallback)
        )


def test_demo_run_may_degrade_to_recorded_fallback() -> None:
    snapshot = RunConfigSnapshot(
        **_run_config_kwargs(
            requested_run_mode=RunMode.demo,
            effective_run_mode=RunMode.demo,
            effective_data_mode=DataMode.recorded_fallback,
        )
    )
    assert snapshot.requested_data_mode is DataMode.live
    assert snapshot.effective_data_mode is DataMode.recorded_fallback


def test_run_summary_carries_effective_data_mode_and_stage_statuses() -> None:
    summary = RunSummary(
        run_id="run_20260801_120000_abcd",
        run_mode=RunMode.rehearsal,
        effective_data_mode=DataMode.fixture,
        terminal_state=TerminalState.completed,
        artifact_dir="artifacts/run_20260801_120000_abcd",
        confidence=Reliability.medium,
        insufficient_data=False,
        stage_statuses={"planner": "completed", "arbiter": "completed"},
    )
    assert summary.effective_data_mode is DataMode.fixture
    assert summary.stage_statuses["planner"] == "completed"
