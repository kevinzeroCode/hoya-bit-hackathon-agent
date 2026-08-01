"""Unit tests for the deterministic Traditional Chinese report renderer (S2 / Task 2).

Contract sources:
- `docs/Features.md` §3 — the 11 fixed report sections.
- `.kiro/steering/tech.md` §9 — deterministic rendering, no LLM rewrite, prohibited-advice lint.
- `.kiro/steering/evidence-contracts.md` §11 — the renderer adds no facts beyond validated claims.
"""

from __future__ import annotations

import re

import pytest

from hoya_agent.models import Asset, EvidenceLedger, Reliability, RunMode
from hoya_agent.reporting.renderer import (
    REPORT_SECTION_TITLES,
    build_insufficient_data_result,
    render,
)

# Prohibited prescriptive investment language (competition-rules.md "Report Safety Rules").
# The reusable string lint lives in `reporting/lint.py`, which is owned by Task 7 / S3.
# Until it lands the renderer accepts an injected lint hook and this table guards the
# rendered fixture output.
PROHIBITED_TERMS = (
    "建議買入",
    "建議賣出",
    "買入",
    "賣出",
    "加倉",
    "減倉",
    "做多",
    "做空",
    "資產配置",
    "下單",
)

# Numbers of three or more characters must be traceable to the fixtures. Section
# numbering (1-11) is intentionally shorter than the threshold.
NUMBER_TOKEN_RE = re.compile(r"\d[\d,.]{2,}")


def test_eleven_fixed_sections_appear_in_contract_order(result, ledger) -> None:
    report = render(result, ledger)
    assert len(REPORT_SECTION_TITLES) == 11
    positions = []
    for index, title in enumerate(REPORT_SECTION_TITLES, start=1):
        heading = f"## {index}. {title}"
        assert heading in report, f"missing section heading: {heading}"
        positions.append(report.index(heading))
    assert positions == sorted(positions), "sections must render in contract order"
    assert report.count("\n## ") == 11, "no section beyond the 11 fixed ones may render"


def test_single_asset_run_has_no_cross_asset_section(result, ledger) -> None:
    # Requirement 17 / S9B: the 跨幣比較 section exists only for two-asset runs.
    assert "跨幣比較" not in render(result, ledger)


def test_every_ledger_evidence_id_is_cited(result, ledger) -> None:
    report = render(result, ledger)
    for item in ledger.items:
        assert item.evidence_id in report, f"{item.evidence_id} is not traceable in the report"


def test_claims_render_under_their_layer_with_evidence_ids(result, ledger) -> None:
    report = render(result, ledger)
    facts_block = _section_body(report, 3, "已確認事實")
    inference_block = _section_body(report, 6, "推論")
    conclusion_block = _section_body(report, 7, "結論")

    assert "cl_001" in facts_block and "cl_002" in facts_block
    assert "cl_003" not in facts_block
    assert "cl_003" in inference_block
    assert "cl_004" in conclusion_block
    # Each rendered claim carries the Evidence IDs that support it.
    assert "ev_001" in facts_block
    assert "ev_002" in inference_block


def test_opposing_evidence_and_material_conflict_are_shown(result, ledger) -> None:
    counter_block = _section_body(report := render(result, ledger), 5, "主要反方或矛盾證據")
    assert "ev_003" in counter_block, "the opposing Evidence ID must appear"
    assert "cl_004" in counter_block, "the conflicted claim must be named"
    assert "material conflict" in counter_block.lower() or "矛盾" in counter_block
    assert "news.example.com" in report


def test_missing_counter_signal_discloses_searched_sources(result, ledger) -> None:
    no_opposition = result.model_copy(
        update={
            "claim_evidence_links": [
                link for link in result.claim_evidence_links if link.stance.value != "opposes"
            ]
        }
    )
    stripped_ledger = EvidenceLedger.model_validate(
        ledger.model_dump(mode="python") | {"conflict_indicators": []}
    )
    counter_block = _section_body(
        render(no_opposition, stripped_ledger), 5, "主要反方或矛盾證據"
    )
    assert "未找到" in counter_block
    # The searched sources must be listed instead of a fabricated counter-signal.
    assert "public_market_data" in counter_block


def test_confidence_renders_only_ordinal_labels(result, ledger) -> None:
    report = render(result, ledger)
    confidence_block = _section_body(report, 8, "信心與原因")
    assert result.confidence.value in confidence_block
    assert result.confidence_rationale in confidence_block
    for forbidden in ("機率", "%信心", "probability"):
        assert forbidden not in confidence_block
    for label in confidence_block.split():
        assert label not in {"0.7", "70%"}


def test_limitations_and_degradation_are_disclosed(result, ledger) -> None:
    block = _section_body(render(result, ledger), 9, "限制與資料缺口")
    for limitation in result.limitations:
        assert limitation in block
    for note in result.degradation_notes:
        assert note in block
    for event in ledger.degradation_events:
        assert event.message in block


def test_quantified_and_qualitative_invalidation_conditions_render(result, ledger) -> None:
    block = _section_body(render(result, ledger), 10, "失效條件")
    quantified, qualitative = result.invalidation_conditions
    assert quantified.text in block
    assert quantified.basis_evidence_id in block
    assert "lt" in block or "<" in block
    assert qualitative.text in block


def test_watch_items_render(result, ledger) -> None:
    block = _section_body(render(result, ledger), 11, "後續觀察重點")
    for item in result.watch_items:
        assert item in block


def test_run_mode_and_run_id_are_visible(result, ledger) -> None:
    report = render(result, ledger)
    assert result.run_id in report
    assert "rehearsal" in report
    assert "fixture" in report or "非 live" in report


def test_rehearsal_label_does_not_assert_fixture_or_live_data(result, ledger) -> None:
    # rehearsal covers deterministic fixtures and replayable real data alike, so
    # the label must not claim either one.
    report = render(result, ledger)
    assert "rehearsal" in report
    assert "非 live official 結果" in report
    assert "fixture 資料" not in report


def test_fallback_reason_is_not_double_punctuated(ledger) -> None:
    fallback = build_insufficient_data_result(
        run_id=ledger.run_id,
        question="BTC 近期市場行為可以由哪些因素解釋？",
        assets=[Asset.BTC],
        analysis_as_of=ledger.analysis_as_of,
        reason="Arbiter 尚未接線，本次僅產出 deterministic 市場證據。",
    )
    assert "。。" not in render(fallback, ledger)


def test_report_contains_no_prohibited_advice_language(result, ledger) -> None:
    report = render(result, ledger)
    for term in PROHIBITED_TERMS:
        assert term not in report, f"prohibited prescriptive term rendered: {term}"


def test_injected_lint_hook_runs_last_and_can_reject(result, ledger) -> None:
    seen: list[str] = []

    def lint(text: str) -> list[str]:
        seen.append(text)
        return []

    render(result, ledger, lint=lint)
    assert len(seen) == 1
    assert seen[0].rstrip().endswith(render(result, ledger).rstrip())

    def rejecting_lint(text: str) -> list[str]:
        return ["prohibited term: 加倉"]

    with pytest.raises(ValueError, match="加倉"):
        render(result, ledger, lint=rejecting_lint)


def test_renderer_invents_no_numbers_absent_from_fixtures(result, ledger, fixture_source_text) -> None:
    report = render(result, ledger)
    # Section headings carry their own ordinal numbering, which is renderer
    # structure rather than a sourced fact.
    body = "\n".join(line for line in report.splitlines() if not line.startswith("## "))
    for token in NUMBER_TOKEN_RE.findall(body):
        assert token in fixture_source_text, f"report introduced an unsourced number: {token}"


def test_rendering_is_deterministic(result, ledger) -> None:
    assert render(result, ledger) == render(result, ledger)


def test_insufficient_data_fallback_is_deterministic_and_honest(ledger) -> None:
    fallback = build_insufficient_data_result(
        run_id=ledger.run_id,
        question="BTC 近期市場行為可以由哪些因素解釋？",
        assets=[Asset.BTC],
        analysis_as_of=ledger.analysis_as_of,
        reason="Arbiter 未產出可驗證結果",
    )
    assert fallback.insufficient_data is True
    assert fallback.confidence is Reliability.low
    assert fallback.claims == []

    report = render(fallback, ledger)
    assert report == render(fallback, ledger)
    assert "目前無法可靠判定" in report
    assert "Arbiter 未產出可驗證結果" in report
    assert report.count("\n## ") == 11
    # Traceability survives the fallback: the ledger is still disclosed.
    for item in ledger.items:
        assert item.evidence_id in report
    for term in PROHIBITED_TERMS:
        assert term not in report


def test_empty_ledger_fallback_still_renders_all_sections(ledger) -> None:
    empty_ledger = EvidenceLedger(
        run_id=ledger.run_id,
        analysis_as_of=ledger.analysis_as_of,
        run_mode=RunMode.rehearsal,
        items=[],
        degradation_events=list(ledger.degradation_events),
    )
    fallback = build_insufficient_data_result(
        run_id=ledger.run_id,
        question="BTC 近期市場行為可以由哪些因素解釋？",
        assets=[Asset.BTC],
        analysis_as_of=ledger.analysis_as_of,
        reason="所有外部來源不可用",
    )
    report = render(fallback, empty_ledger)
    assert report.count("\n## ") == 11
    assert "目前無法可靠判定" in report
    assert empty_ledger.degradation_events[0].message in report


def _section_body(report: str, index: int, title_fragment: str) -> str:
    """Return the text of one numbered section, excluding later sections."""
    headings = [line for line in report.splitlines() if line.startswith("## ")]
    heading = next(h for h in headings if h.startswith(f"## {index}. "))
    assert title_fragment in heading
    start = report.index(heading)
    rest = report[start + len(heading) :]
    next_heading = rest.find("\n## ")
    return rest if next_heading == -1 else rest[:next_heading]
