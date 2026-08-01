"""End-to-end provenance invariants for the deterministic dual-asset path."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import AnalysisResult, Asset, ClaimType, EvidenceLedger, RunMode
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline
from tests.fakes import FixedClock

pytestmark = pytest.mark.integration

NOW = datetime(2026, 5, 31, 6, tzinfo=UTC)


async def test_report_claims_and_thresholds_resolve_to_the_ledger(tmp_path) -> None:
    clock = FixedClock(NOW, monotonic_value=100.0)
    market = OrganizerCsvPipeline(analysis_date=date(2026, 5, 31))
    request = build_request(
        question="BTC 與 ETH 的近期表現差異？",
        assets=[Asset.BTC, Asset.ETH],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix="prov",
    )
    summary = await ApplicationService(
        artifact_root=tmp_path,
        clock=clock,
        pipeline=market,
        configured_sources=["organizer_csv"],
    ).run(request)

    run_dir = tmp_path / request.run_id
    ledger = EvidenceLedger.model_validate_json(
        (run_dir / "evidence.json").read_text(encoding="utf-8")
    )
    evidence_ids = {item.evidence_id for item in ledger.items}
    report = (run_dir / "final_report.md").read_text(encoding="utf-8")
    assert summary.missing_artifacts == []

    # The result is reconstructed from the report-driving deterministic path.
    outcome = await market.execute(
        clock_context(request, clock),
        lambda event: None,
    )
    result = AnalysisResult.model_validate(outcome.result)
    claims = {claim.claim_id: claim for claim in result.claims}

    assert result.claim_evidence_links
    for link in result.claim_evidence_links:
        assert link.evidence_id in evidence_ids
        assert link.claim_id in claims
        assert link.evidence_id in report

    for claim in result.claims:
        if claim.claim_type in {ClaimType.inference, ClaimType.conclusion}:
            assert claim.based_on_claim_ids
            assert _reaches_fact(claim.claim_id, claims)

    for condition in result.invalidation_conditions:
        if condition.basis_evidence_id is None:
            continue
        assert condition.basis_evidence_id in evidence_ids
        metric = market.last_metric_index[condition.basis_evidence_id]
        assert condition.metric == metric.metric_name
        assert condition.threshold == pytest.approx(metric.metric_value)

    artifact_ledger = json.loads((run_dir / "evidence.json").read_text(encoding="utf-8"))
    assert artifact_ledger["run_id"] == result.run_id == request.run_id


def clock_context(request, clock):
    from hoya_agent.clock import build_run_context

    return build_run_context(request, clock)


def _reaches_fact(claim_id, claims, visiting=None) -> bool:
    visiting = set() if visiting is None else set(visiting)
    if claim_id in visiting:
        return False
    visiting.add(claim_id)
    claim = claims[claim_id]
    if claim.claim_type is ClaimType.fact:
        return True
    return all(
        dependency in claims and _reaches_fact(dependency, claims, visiting)
        for dependency in claim.based_on_claim_ids
    )
