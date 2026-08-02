"""MappingArbiter retry: never ship a degenerate prose-only (empty-claims) result."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from hoya_agent.composition import MappingArbiter
from hoya_agent.reasoning.schemas import ArbiterGeneration, GenClaim, GenLink

UTC = timezone.utc


def _request():
    return SimpleNamespace(
        run_id="run_20260801_120000_test",
        question="BTC 過去兩週表現?",
        assets=["BTC"],
        analysis_as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )


_EMPTY = ArbiterGeneration(direct_answer="只有散文,沒有 claims。", confidence="medium")
_FULL = ArbiterGeneration(
    direct_answer="BTC 近況分析。",
    claims=[GenClaim(claim_id="cl_001", claim_type="fact", assets=["BTC"], text="近14日報酬-1.6%")],
    claim_evidence_links=[GenLink(claim_id="cl_001", evidence_id="ev_001", stance="supports", reason="市場")],
    confidence="medium",
)


class _FakeInner:
    settings = SimpleNamespace(max_evidence=30)

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        return self._script.pop(0), []


async def test_retries_when_first_result_has_no_claims():
    inner = _FakeInner([_EMPTY, _FULL])
    arb = MappingArbiter(inner=inner)
    result, _notes = await arb.run(request=_request(), ledger=None, deadline=0.0)
    assert inner.calls == 2  # retried the degenerate first result
    assert result is not None and len(result.claims) == 1


async def test_no_retry_when_first_result_has_claims():
    inner = _FakeInner([_FULL])
    arb = MappingArbiter(inner=inner)
    result, _notes = await arb.run(request=_request(), ledger=None, deadline=0.0)
    assert inner.calls == 1
    assert result is not None and len(result.claims) == 1
