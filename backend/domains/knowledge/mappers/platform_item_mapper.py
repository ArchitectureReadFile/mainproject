"""
domains/knowledge/mappers/platform_item_mapper.py

Platform 지식원 raw hit → RetrievedKnowledgeItem 변환.
"""

from __future__ import annotations

from domains.knowledge.schemas import RetrievedKnowledgeItem

_PLATFORM_HIT_META_FIELDS = (
    "source_url",
    "issued_at",
    "agency",
    "chunk_type",
    "section_title",
    "related_law_refs",
    "related_case_refs",
)


def platform_hit_to_item(hit: dict) -> RetrievedKnowledgeItem:
    source_type = hit.get("source_type") or "platform"
    platform_document_id = hit.get("platform_document_id") or ""
    chunk_id = hit.get("chunk_id")

    return RetrievedKnowledgeItem(
        knowledge_type="platform",
        source_type=source_type,
        source_id=platform_document_id,
        title=hit.get("title") or source_type,
        chunk_text=hit.get("text") or "",
        score=hit.get("score", 0.0),
        chunk_id=chunk_id,
        metadata={
            k: hit.get(k) for k in _PLATFORM_HIT_META_FIELDS if hit.get(k) is not None
        },
    )
