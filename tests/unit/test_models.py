"""Unit tests for the normative data contracts in hoya_agent.models.

Covers: enums, AnalysisRequest, EvidenceItem, EvidenceDraft, ClaimEvidenceLink,
Claim, EvidenceLedger, ConflictIndicator, DegradationEvent, TimeRange,
MarketContext, InvalidationCondition, MarketRegime, TrustScorecard and
AnalysisResult.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
    DegradationEvent,
    EvidenceDraft,
    EvidenceItem,
    EvidenceLedger,
    InvalidationCondition,
    InvalidationOperator,
    MarketContext,
    MarketRegime,
    RegimeLabel,
    Reliability,
    RunMode,
    SourceType,
    Stance,
    TimeRange,
    TrustLevel,
    TrustScorecard,
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc
NOW = datetime(2026, 7, 17, 6, 0, 0, tzinfo=UTC)
YESTERDAY = datetime(2026, 7, 16, 0, 0, 0, tzinfo=UTC)
VALID_HASH = "a" * 64


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
        expected = {
            "trending_up", "trending_down", "range_bound",
            "high_volatility", "mixed",
        }
        assert {r.value for r in RegimeLabel} == expected

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

    def test_run_mode_enum(self):
        for mode in ("official", "rehearsal", "demo"):
            req = AnalysisRequest(**_valid_request(run_mode=mode))
            assert req.run_mode.value == mode


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

    def test_rejects_empty_source_name(self):
        with pytest.raises(ValidationError, match="empty"):
            EvidenceItem(**_valid_evidence_item(source_name=""))

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
        """EvidenceItem must reject the deprecated 'fetched_time' field name."""
        data = _valid_evidence_item()
        data["fetched_time"] = NOW
        with pytest.raises(ValidationError):
            EvidenceItem(**data)

    def test_rejects_deprecated_fetched_space_time_field(self):
        """EvidenceItem must reject the deprecated 'fetched time' field name."""
        data = _valid_evidence_item()
        data["fetched time"] = NOW
        with pytest.raises(ValidationError):
            EvidenceItem(**data)

    def test_rejects_stance_field(self):
        """EvidenceItem must NOT have a stance field — stance belongs on Link."""
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
        """EvidenceDraft does not have evidence_id, reliability, independence_group, content_hash."""
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

    def test_evidence_list_projection_fields(self):
        """ClaimEvidenceLink exposes claim_id (related_claim), evidence_id, stance, reason."""
        link = ClaimEvidenceLink(**_valid_link())
        assert hasattr(link, "claim_id")
        assert hasattr(link, "evidence_id")
        assert hasattr(link, "stance")
        assert hasattr(link, "reason")


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
    def test_valid_empty_ledger(self):
        ledger = EvidenceLedger(
            run_id="run_20260717_060000_ab12",
            analysis_as_of=NOW,
            run_mode="official",
        )
        assert ledger.items == []
        assert ledger.schema_version == "1.0"

    def test_rejects_naive_analysis_as_of(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            EvidenceLedger(
                run_id="run_20260717_060000_ab12",
                analysis_as_of=naive,
                run_mode="official",
            )


class TestConflictIndicator:
    def test_valid(self):
        ci = ConflictIndicator(
            claim_id="cl_001",
            supporting_evidence_ids=["ev_001"],
            opposing_evidence_ids=["ev_002"],
            independence_groups=["binance.com", "coingecko.com"],
        )
        assert ci.rule_version == "1.0"


class TestDegradationEvent:
    def test_valid(self):
        de = DegradationEvent(
            stage="market_worker",
            event_type="timeout",
            source="binance",
            message="Binance API timed out",
            timestamp=NOW,
        )
        assert de.stage == "market_worker"

    def test_rejects_naive_timestamp(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            DegradationEvent(
                stage="x", event_type="y", source="z", message="m", timestamp=naive
            )


# ===========================================================================
# InvalidationCondition tests
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


# ===========================================================================
# MarketRegime tests
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

    def test_all_labels(self):
        for label in RegimeLabel:
            mr = MarketRegime(
                asset="BTC",
                label=label.value,
                as_of="2026-05-31",
                window_days=30,
                metrics={},
                thresholds={},
                evidence_id="ev_001",
            )
            assert mr.label == label

    def test_rejects_invalid_label(self):
        with pytest.raises(ValidationError):
            MarketRegime(
                asset="BTC",
                label="crash",
                as_of="2026-05-31",
                window_days=30,
                metrics={},
                thresholds={},
                evidence_id="ev_001",
            )


# ===========================================================================
# TrustScorecard tests
# ===========================================================================


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

    def test_strong_independence_requires_three_groups(self):
        """strong independence requires distinct_groups >= 3."""
        sc = TrustScorecard(
            **self._make_scorecard(
                source_independence={"level": "strong", "distinct_groups": 3}
            )
        )
        assert sc.source_independence.level == TrustLevel.strong

    def test_moderate_independence_for_two(self):
        sc = TrustScorecard(
            **self._make_scorecard(
                source_independence={"level": "moderate", "distinct_groups": 2}
            )
        )
        assert sc.source_independence.level == TrustLevel.moderate

    def test_weak_independence_for_one(self):
        sc = TrustScorecard(
            **self._make_scorecard(
                source_independence={"level": "weak", "distinct_groups": 1}
            )
        )
        assert sc.source_independence.level == TrustLevel.weak

    def test_unavailable_independence_for_zero(self):
        sc = TrustScorecard(
            **self._make_scorecard(
                source_independence={"level": "unavailable", "distinct_groups": 0}
            )
        )
        assert sc.source_independence.level == TrustLevel.unavailable

    def test_consistency_weak_on_conflict(self):
        sc = TrustScorecard(
            **self._make_scorecard(
                consistency={
                    "level": "weak",
                    "has_material_conflict": True,
                    "opposing_count": 2,
                }
            )
        )
        assert sc.consistency.level == TrustLevel.weak
        assert sc.consistency.has_material_conflict is True

    def test_rejects_blank_rationale(self):
        with pytest.raises(ValidationError, match="empty"):
            TrustScorecard(**self._make_scorecard(rationale=""))

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            TrustScorecard(**self._make_scorecard(extra="bad"))


# ===========================================================================
# AnalysisResult tests
# ===========================================================================


class TestAnalysisResult:
    def _valid_result(self, **overrides) -> dict:
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

    def test_valid_construction(self):
        result = AnalysisResult(**self._valid_result())
        assert result.confidence == Reliability.medium

    def test_rejects_naive_analysis_as_of(self):
        naive = datetime(2026, 7, 17, 6, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            AnalysisResult(**self._valid_result(analysis_as_of=naive))

    def test_rejects_blank_direct_answer(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalysisResult(**self._valid_result(direct_answer=""))

    def test_rejects_blank_question(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalysisResult(**self._valid_result(question="  "))

    def test_invalidation_conditions_are_structured(self):
        """AnalysisResult.invalidation_conditions is list[InvalidationCondition]."""
        result = AnalysisResult(
            **self._valid_result(
                invalidation_conditions=[
                    {"text": "Close drops below 68000", "metric": "close",
                     "operator": "lt", "threshold": 68000.0,
                     "basis_evidence_id": "ev_007"},
                ]
            )
        )
        assert isinstance(result.invalidation_conditions[0], InvalidationCondition)

    def test_market_regime_optional(self):
        result = AnalysisResult(**self._valid_result(market_regime=None))
        assert result.market_regime is None

    def test_trust_scorecards_default_empty(self):
        result = AnalysisResult(**self._valid_result())
        assert result.trust_scorecards == []

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**self._valid_result(unknown="x"))
