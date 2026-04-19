"""
domains/knowledge/mappers/session_item_mapper.py

Session 지식원 텍스트 → RetrievedKnowledgeItem 변환.
"""

from __future__ import annotations

from domains.knowledge.schemas import RetrievedKnowledgeItem


def session_text_to_item(
    *,
    session_id: int | None,
    chunk_text: str,
    session_title: str | None = None,
    chunk_id: str | None = None,
    chunk_order: int | None = None,
    score: float = 1.0,
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type="session",
        source_type="session_document",
        source_id=f"session:{session_id}",
        title=session_title or "첨부 문서",
        chunk_text=chunk_text.strip(),
        score=score,
        chunk_id=chunk_id,
        metadata={
            "session_id": session_id,
            "session_title": session_title,
            "chunk_order": chunk_order,
        },
    )
