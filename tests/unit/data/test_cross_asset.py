from datetime import date, timedelta

from hoya_agent.data.price_analysis import build_comparison_evidence
from hoya_agent.data.types import MarketBar


def _bars(start: date, factor: float) -> list[MarketBar]:
    return [
        MarketBar(
            date=start + timedelta(days=index),
            open=100 + factor * index,
            high=102 + factor * index,
            low=98 + factor * index,
            close=100 + factor * index + ((index % 7) - 3) * 0.1,
            volume=1000 + index,
        )
        for index in range(300)
    ]


def test_cross_asset_evidence_is_aligned_and_never_compares_base_volume() -> None:
    start = date(2025, 1, 1)
    outcome = build_comparison_evidence(
        "BTC",
        "ETH",
        _bars(start, 1.0),
        _bars(start, 0.6),
        analysis_as_of=start + timedelta(days=299),
    )
    assert outcome.status == "completed"
    assert len(outcome.drafts) == 3
    assert all(draft.metric_value is not None for draft in outcome.drafts)
    assert "volume" not in " ".join(d.normalized_fact for d in outcome.drafts).lower()


def test_no_overlapping_utc_date_is_unavailable_without_forward_fill() -> None:
    outcome = build_comparison_evidence(
        "BTC",
        "ETH",
        _bars(date(2025, 1, 1), 1.0),
        _bars(date(2027, 1, 1), 0.6),
        analysis_as_of=date(2027, 12, 31),
    )
    assert outcome.status == "failed"
    assert outcome.drafts == []
    assert "no aligned UTC bars" in outcome.degradation[0]
