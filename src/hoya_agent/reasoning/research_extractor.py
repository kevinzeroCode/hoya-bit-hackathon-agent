"""Multi-fact research extraction: the schema the LLM fills, and the deterministic
completion that turns it into Evidence drafts.

Migrated from the P2 ETL prototype (`p2-etl-mvp/reasoning/research_extractor.py`)
and reconciled with the frozen `ResearchAgent`, which already owns the single
bounded LLM call per stage. This module supplies the two halves the agent takes
by injection and never invents itself:

1. `ResearchExtraction` — the structured-output schema. One record may yield
   several facts, so a single article becomes several Evidence drafts rather than
   one summary. The model also returns a relevance verdict, which is how
   off-topic feed noise is dropped without a second call.
2. `complete_extracted_drafts` — deterministic completion. Reliability comes from
   the static policy table, `independence_group` from the original publisher or
   registered domain, and every timestamp from the fetched record. The model
   supplies wording only.

Hard rules, independent of the model:
- The LLM never assigns or upgrades reliability (evidence-contracts §4).
- Drafts carry no stance; `supports`/`opposes` belongs to Claim-Evidence Links.
- A fact citing a record that was never fetched is discarded and disclosed.
- Retrieved text is untrusted data; instruction-like content is quoted, never
  obeyed (the agent flags it separately).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from hoya_agent.data.text_clean import clean_text
from hoya_agent.evidence.drafts import PendingEvidence, pending
from hoya_agent.evidence.policies import SourceClass, independence_group
from hoya_agent.models import Asset

#: Prompt whose version is persisted with every extracted draft.
PROMPT_ID = "research-extraction"

#: One article may support several facts, but not an unbounded list: a long feed
#: item would otherwise crowd the 30-item Arbiter payload on its own.
MAX_FACTS_PER_RECORD = 3

#: `content_reference` is a bounded quotation for traceability and grounding, not
#: a copy of the article.
MAX_CONTENT_REFERENCE_CHARS = 400

#: Which static source class a record belongs to. Feed/aggregator records stay
#: `low` because the original page was not fetched; see evidence-contracts §4.
_SOURCE_CLASS_BY_TYPE = {
    "official": SourceClass.OFFICIAL_ANNOUNCEMENT,
    "social": SourceClass.SOCIAL,
    "macro": SourceClass.SECONDARY_COMMENTARY,
    "onchain": SourceClass.SECONDARY_COMMENTARY,
}


class ExtractedFact(BaseModel):
    """One atomic, stanceless proposition the model grounded in one record."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    normalized_fact: str
    relevant: bool = True
    event_type: str = "other"
    asset: Asset | None = None

    @field_validator("record_id", "normalized_fact", "event_type")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("extracted text fields must not be blank")
        return text


class ResearchExtraction(BaseModel):
    """Structured output for one bounded research-extraction call."""

    model_config = ConfigDict(extra="forbid")

    drafts: list[ExtractedFact] = []


def _looks_complete(candidate: Any) -> bool:
    """True when a draft is already a `PendingEvidence` from a deterministic producer.

    The Market Worker and the source adapters build complete pending evidence
    themselves; only LLM-extracted facts need completion here.
    """
    return isinstance(candidate, PendingEvidence)


def _source_class_for_record(record: Any) -> SourceClass:
    """Static source class for a research record — never the model's opinion."""
    source_type = str(getattr(getattr(record, "source_type", ""), "value", getattr(record, "source_type", "")))
    mapped = _SOURCE_CLASS_BY_TYPE.get(source_type)
    if mapped is not None:
        return mapped
    # News: `medium` only when the original page was actually fetched. The flag is
    # provenance recorded by the adapter, not something the model can claim.
    original_page_fetched = bool(
        (getattr(record, "metadata", None) or {}).get("original_page_fetched", False)
    )
    return (
        SourceClass.ORIGINAL_NEWS_PAGE if original_page_fetched else SourceClass.NEWS_AGGREGATOR
    )


def _publisher_of(record: Any) -> str | None:
    metadata = getattr(record, "metadata", None) or {}
    publisher = metadata.get("original_publisher") or metadata.get("publisher_domain")
    return str(publisher) if publisher else None


def _group_for_record(record: Any) -> str | None:
    metadata = getattr(record, "metadata", None) or {}
    publisher = metadata.get("original_publisher") or metadata.get("publisher_domain")
    try:
        return independence_group(
            original_publisher=str(publisher) if publisher else None,
            source_url=getattr(record, "source_url", None),
            provider_id=str(getattr(record, "source_name", "")) or None,
        )
    except ValueError:
        return None


def _content_reference(record: Any, event_type: str) -> str:
    """A bounded quotation of the source: headline plus the opening of the body.

    Grounding compares the numbers and dates in an extracted fact against this
    string, so it has to hold the source's own wording rather than a paraphrase.
    """
    title = clean_text(str(getattr(record, "title", "") or ""))
    body = clean_text(str(getattr(record, "content", "") or ""))
    published = getattr(record, "published_at", None)
    stamp = published.date().isoformat() if isinstance(published, datetime) else "未提供來源時間"
    quote = body[:MAX_CONTENT_REFERENCE_CHARS]
    if len(body) > MAX_CONTENT_REFERENCE_CHARS:
        quote = quote.rstrip() + "…"
    return f"[{event_type}] {getattr(record, 'source_name', '')}（{stamp}）標題：{title}；引述：{quote}"


def complete_extracted_drafts(
    drafts: Sequence[Any],
    *,
    records: Sequence[Any],
    fetched_at: datetime | None = None,
) -> tuple[list[PendingEvidence], list[str]]:
    """Turn extracted facts into Evidence drafts, or disclose why they were dropped.

    Drafts that already satisfy the Evidence contract pass through unchanged, so a
    mixed batch (market drafts plus extracted facts) is safe to hand over in one
    call. Every rejection returns a note; nothing is silently discarded.
    """
    by_record = {str(getattr(record, "record_id", "")): record for record in records}
    completed: list[PendingEvidence] = []
    notes: list[str] = []
    used_per_record: dict[str, int] = {}
    capped: set[str] = set()

    for candidate in drafts:
        if _looks_complete(candidate):
            completed.append(candidate)
            continue

        record_id = str(getattr(candidate, "record_id", "") or "")
        record = by_record.get(record_id)
        if record is None:
            # Citing a record we never fetched is a fabricated fact, not a repairable one.
            notes.append(f"捨棄引用不存在來源紀錄 {record_id!r} 的抽取事實。")
            continue

        if not bool(getattr(candidate, "relevant", True)):
            notes.append(f"來源 {record_id} 經抽取判定未達相關性，未納入 Evidence。")
            continue

        fact = str(getattr(candidate, "normalized_fact", "") or "").strip()
        if not fact:
            notes.append(f"來源 {record_id} 的抽取事實為空，已捨棄。")
            continue

        if used_per_record.get(record_id, 0) >= MAX_FACTS_PER_RECORD:
            if record_id not in capped:
                notes.append(
                    f"來源 {record_id} 的抽取事實超過每篇 {MAX_FACTS_PER_RECORD} 筆上限，已截斷。"
                )
                capped.add(record_id)
            continue

        group = _group_for_record(record)
        if group is None:
            notes.append(f"來源 {record_id} 無法判定 independence_group，未納入 Evidence。")
            continue

        asset = getattr(candidate, "asset", None) or getattr(record, "asset", None)
        event_type = str(getattr(candidate, "event_type", "other") or "other")
        completed.append(
            pending(
                # The class decides reliability; the model never does.
                source_class=_source_class_for_record(record),
                original_publisher=_publisher_of(record),
                provider_id=str(getattr(record, "source_name", "")) or None,
                asset=str(getattr(asset, "value", asset)) if asset else None,
                source_type=str(getattr(record.source_type, "value", record.source_type)),
                source_name=str(getattr(record, "source_name", "")),
                source_url=getattr(record, "source_url", None),
                published_at=getattr(record, "published_at", None),
                fetched_at=getattr(record, "fetched_at", None)
                or fetched_at
                or datetime.now(timezone.utc),
                query_or_parameters=f"llm_extraction prompt={PROMPT_ID}; record={record_id}",
                content_reference=_content_reference(record, event_type),
                normalized_fact=fact,
                source_record_id=record_id,
            )
        )
        used_per_record[record_id] = used_per_record.get(record_id, 0) + 1

    return completed, notes
