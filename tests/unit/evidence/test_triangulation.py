"""Cross-source triangulation golden tests (deterministic, no LLM/network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from hoya_agent.data.price_analysis import AnomalyDay
from hoya_agent.evidence.triangulation import triangulate
from hoya_agent.models import EvidenceItem

UTC = timezone.utc


def _item(eid: str, published: date, *, asset: str | None, source_type: str, group: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=eid,
        content_hash=eid.encode().hex().ljust(64, "0"),
        asset=asset,
        source_type=source_type,
        source_name=f"src-{eid}",
        source_url=f"https://{group}/{eid}",
        published_at=datetime(published.year, published.month, published.day, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 31, tzinfo=UTC),
        query_or_parameters="q",
        content_reference="ref",
        normalized_fact="fact",
        reliability="medium",
        independence_group=group,
    )


def test_market_move_corroborated_by_news_is_strength_two():
    anomalies = [AnomalyDay(date(2026, 5, 20), -0.08, -3.4)]
    items = [_item("ev_001", date(2026, 5, 20), asset="BTC", source_type="news", group="coindesk.com")]
    events = triangulate(anomalies, items, asset="BTC")
    assert len(events) == 1
    e = events[0]
    assert e.strength == 2
    assert e.source_types == ("market", "news")
    assert e.corroborating_evidence_ids == ("ev_001",)


def test_three_independent_source_types_rank_highest():
    anomalies = [AnomalyDay(date(2026, 5, 20), -0.08, -3.4)]
    items = [
        _item("ev_001", date(2026, 5, 20), asset="BTC", source_type="news", group="coindesk.com"),
        _item("ev_002", date(2026, 5, 21), asset="BTC", source_type="social", group="reddit.com"),
        _item("ev_003", date(2026, 5, 19), asset=None, source_type="macro", group="alternative.me"),
    ]
    e = triangulate(anomalies, items, asset="BTC")[0]
    assert e.strength == 4  # market + news + social + macro
    assert set(e.corroborating_evidence_ids) == {"ev_001", "ev_002", "ev_003"}


def test_unexplained_move_is_strength_one():
    anomalies = [AnomalyDay(date(2026, 5, 20), 0.09, 3.6)]
    events = triangulate(anomalies, [], asset="BTC")
    assert events[0].strength == 1
    assert events[0].corroborating_evidence_ids == ()
    assert "無獨立研究來源佐證" in events[0].note


def test_window_boundary_excludes_far_news():
    anomalies = [AnomalyDay(date(2026, 5, 20), -0.08, -3.4)]
    items = [_item("ev_901", date(2026, 5, 23), asset="BTC", source_type="news", group="g")]  # 3 days off
    e = triangulate(anomalies, items, asset="BTC", window_days=1)[0]
    assert e.strength == 1  # outside ±1 day


def test_other_asset_news_is_not_counted():
    anomalies = [AnomalyDay(date(2026, 5, 20), -0.08, -3.4)]
    items = [_item("ev_902", date(2026, 5, 20), asset="ETH", source_type="news", group="g")]
    e = triangulate(anomalies, items, asset="BTC")[0]
    assert e.strength == 1  # ETH news does not corroborate a BTC move


def test_events_sorted_by_strength_then_extremity():
    anomalies = [
        AnomalyDay(date(2026, 5, 10), 0.09, 3.6),   # no corroboration
        AnomalyDay(date(2026, 5, 20), -0.08, -3.4),  # corroborated
    ]
    items = [_item("ev_001", date(2026, 5, 20), asset="BTC", source_type="news", group="g")]
    events = triangulate(anomalies, items, asset="BTC")
    assert events[0].day == date(2026, 5, 20)  # strength 2 first
    assert events[1].day == date(2026, 5, 10)  # strength 1 second
