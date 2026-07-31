"""Stand-in contracts and doubles for the reasoning unit tests.

These mirror ``.kiro/steering/evidence-contracts.md`` field-for-field. Once
Task 1 lands, swap them for the real models and delete this module -- the
reasoning code takes its schemas by injection precisely so this is a one-line
change per test.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from hoya_agent.adapters.bedrock import LLMError


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    asset: str | None = "BTC"
    source_type: str = "market"
    source_name: str = "Binance Spot"
    source_url: str | None = None
    published_at: str | None = "2026-07-16T00:00:00Z"
    fetched_at: str = "2026-07-17T06:00:00Z"
    query_or_parameters: str | None = None
    content_reference: str = "reference"
    normalized_fact: str = "fact"
    reliability: str = "high"
    independence_group: str = "binance.com"
    content_hash: str = "0" * 64
    is_cached: bool = False
    cache_time: str | None = None
    is_stale: bool = False


class Ledger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Evidence] = []


class Indicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    supporting_evidence_ids: list[str] = []
    opposing_evidence_ids: list[str] = []
    independence_groups: list[str] = []
    rule_version: str = "1.0"


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: str
    assets: list[str] = []
    text: str = ""
    based_on_claim_ids: list[str] = []
    confidence: str = "medium"
    limitations: list[str] = []
    invalidation_conditions: list[str] = []


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    evidence_id: str
    stance: str
    reason: str = "reason"


class Invalidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    metric: str | None = None
    operator: str | None = None
    threshold: float | None = None
    basis_evidence_id: str | None = None


class Result(BaseModel):
    """Stands in for ``AnalysisResult``."""

    model_config = ConfigDict(extra="forbid")

    direct_answer: str
    market_context: dict[str, Any] | None = None
    claims: list[Claim] = []
    claim_evidence_links: list[Link] = []
    confidence: str = "medium"
    confidence_rationale: str = ""
    limitations: list[str] = []
    invalidation_conditions: list[Invalidation] = []
    watch_items: list[str] = []
    insufficient_data: bool = False
    degradation_notes: list[str] = []


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    tool_operation: str
    rationale: str = ""


class Plan(BaseModel):
    """Stands in for ``ResearchPlan``."""

    model_config = ConfigDict(extra="forbid")

    plan_version: str = "planner-v1"
    assets: list[str] = []
    question_summary: str = ""
    lookback_days: int = 14
    required_evidence_types: list[str] = []
    planned_steps: list[Step] = []
    asset_question_mismatch_warning: str | None = None
    notes: list[str] = []


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    asset: str | None = "BTC"
    normalized_fact: str = ""
    content_reference: str = ""
    extraction_notes: list[str] = []


class Skipped(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    reason: str = ""


class DraftBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drafts: list[Draft] = []
    skipped: list[Skipped] = []


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = "分析目前市場狀況"
    assets: list[str] = ["BTC"]
    analysis_as_of: str = "2026-07-17T06:00:00Z"
    enable_conditional_debate: bool = False


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    source_name: str = "Example News"
    source_url: str = "https://example.com/a"
    source_type: str = "news"
    published_at: str = "2026-07-16T00:00:00Z"
    title: str = "title"
    content: str = "content"


class FakeLLM:
    """Returns queued models, or raises queued errors, recording each call."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def converse_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("FakeLLM ran out of scripted results")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class BoomError(LLMError):
    """A provider failure that must route to the deterministic fallback."""


class FakeRegistry:
    """Static allowlist plus a scripted record source."""

    def __init__(self, operations: tuple[str, ...], results: dict | None = None) -> None:
        self._operations = tuple(operations)
        self.results = results or {}
        self.invoked: list[str] = []

    def operations(self) -> tuple[str, ...]:
        return self._operations

    def is_allowed(self, operation: str) -> bool:
        return operation in self._operations

    async def invoke(self, operation: str, **params: Any) -> list[Record]:
        self.invoked.append(operation)
        outcome = self.results.get(operation, [])
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
