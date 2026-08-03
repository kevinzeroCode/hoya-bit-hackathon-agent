"""Unit tests for the S3 Bronze presenter (pure, no Streamlit)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from hoya_agent.data.types import MarketBar
from hoya_agent.models import Reliability, RunMode
from hoya_agent.ui.presenter import (
    run_mode_badge,
    summary_view,
    terminal_badge,
    triangulation_view,
    trust_funnel,
)


def test_three_run_modes_are_visually_distinct():
    labels = {run_mode_badge(m)[0] for m in (RunMode.official, RunMode.rehearsal, RunMode.demo)}
    icons = {run_mode_badge(m)[1] for m in (RunMode.official, RunMode.rehearsal, RunMode.demo)}
    assert labels == {"OFFICIAL", "REHEARSAL", "DEMO"}
    assert len(icons) == 3  # each mode a distinct icon


def test_terminal_badge_maps_states():
    assert terminal_badge(SimpleNamespace(value="completed"))[0] == "完成"
    assert terminal_badge(SimpleNamespace(value="degraded"))[0].startswith("完成")
    assert terminal_badge(SimpleNamespace(value="failed"))[1] == "❌"


def test_summary_view_maps_all_fields():
    summary = SimpleNamespace(
        run_id="run_20260531_000000_ui",
        run_mode=RunMode.rehearsal,
        terminal_state=SimpleNamespace(value="degraded"),
        evidence_item_count=6,
        confidence=Reliability.low,
        insufficient_data=True,
        degradation_notes=["no arbiter in this increment"],
        report_markdown="# report",
        artifact_paths={"evidence.json": "/tmp/x/evidence.json"},
        missing_artifacts=[],
        artifact_dir="/tmp/x",
    )
    view = summary_view(summary)
    assert view["run_mode_label"] == "REHEARSAL"
    assert view["evidence_count"] == 6
    assert view["confidence"] == "low"
    assert view["insufficient"] is True
    assert view["report_markdown"] == "# report"
    assert "evidence.json" in view["artifacts"]
    assert view["degradation_notes"] == ["no arbiter in this increment"]


def test_trust_funnel_distils_ledger():
    ledger = {
        "items": [
            {"source_type": "news", "reliability": "medium", "independence_group": "coindesk.com"},
            {"source_type": "news", "reliability": "medium", "independence_group": "coindesk.com"},  # repost
            {"source_type": "market", "reliability": "high", "independence_group": "organizer"},
            {"source_type": "social", "reliability": "low", "independence_group": "reddit.com"},
        ],
        "conflict_indicators": [{"claim": "x"}],
    }
    f = trust_funnel(ledger)
    assert f["evidence_count"] == 4
    assert f["source_type_count"] == 3            # news, market, social
    assert f["independence_group_count"] == 3     # two coindesk items collapse to one group
    assert f["reliability_mix"] == {"high": 1, "medium": 2, "low": 1}
    assert f["conflict_count"] == 1


def test_trust_funnel_handles_empty_ledger():
    f = trust_funnel({})
    assert f["evidence_count"] == 0
    assert f["reliability_mix"] == {"high": 0, "medium": 0, "low": 0}


def _bars(prices: list[float]) -> list[MarketBar]:
    start = date(2024, 1, 1)
    return [
        MarketBar(date=start + timedelta(days=i), open=p, high=p, low=p, close=p, volume=100.0)
        for i, p in enumerate(prices)
    ]


def _evidence_item(day: date, *, asset: str, source_type: str, group: str) -> dict:
    return {
        "evidence_id": "ev_001",
        "asset": asset,
        "source_type": source_type,
        "source_name": "coindesk",
        "source_url": f"https://{group}/x",
        "published_at": f"{day.isoformat()}T00:00:00Z",
        "fetched_at": f"{day.isoformat()}T01:00:00Z",
        "query_or_parameters": "q",
        "content_reference": "ref",
        "normalized_fact": "BTC 大漲",
        "reliability": "medium",
        "independence_group": group,
        "content_hash": "a" * 64,
        "is_cached": False,
        "cache_time": None,
        "is_stale": False,
    }


def test_triangulation_view_matches_a_market_anomaly_to_corroborating_news():
    prices = [100.0] * 20 + [150.0]  # one +50% jump on the last (index-20) bar
    anomaly_day = date(2024, 1, 1) + timedelta(days=20)
    ledger = {
        "items": [_evidence_item(anomaly_day, asset="BTC", source_type="news", group="coindesk.com")]
    }

    view = triangulation_view(ledger, {"BTC": _bars(prices)}, sigma=2.0, min_history=10)

    assert view["BTC"]["available"] is True
    events = view["BTC"]["events"]
    assert len(events) == 1
    assert events[0]["strength"] == 2  # market + the corroborating news item
    assert events[0]["corroborating_evidence_ids"] == ["ev_001"]
    assert events[0]["day"] == anomaly_day.isoformat()


def test_triangulation_view_degrades_explicitly_when_history_is_too_short():
    view = triangulation_view({"items": []}, {"BTC": _bars([100.0] * 5)})

    assert view["BTC"]["available"] is False
    assert view["BTC"]["events"] == []
    assert view["BTC"]["reason"]  # some human-readable reason, not silently empty


def test_triangulation_view_reports_unexplained_moves_without_fabricating_a_source():
    prices = [100.0] * 20 + [150.0]
    view = triangulation_view({"items": []}, {"BTC": _bars(prices)}, sigma=2.0, min_history=10)

    events = view["BTC"]["events"]
    assert len(events) == 1
    assert events[0]["strength"] == 1
    assert events[0]["corroborating_evidence_ids"] == []
