"""
domains/knowledge/mappers/session_item_mapper.py

Session 지식원 텍스트 → RetrievedKnowledgeItem 변환.
"""

from __future__ import annotations

from domains.knowledge.schemas import RetrievedKnowledgeItem


def session_text_to_item(
    *,
    session_id: int | None,
    reference_document_text: str,
    session_title: str | None = None,
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type="session",
        source_type="session_document",
        source_id=f"session:{session_id}",
        title=session_title or "첨부 문서",
        chunk_text=reference_document_text.strip(),
        score=1.0,
        metadata={
            "session_id": session_id,
            "session_title": session_title,
        },
    )
