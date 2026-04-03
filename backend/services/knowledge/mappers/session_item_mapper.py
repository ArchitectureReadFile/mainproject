"""
services/knowledge/mappers/session_item_mapper.py

Session 지식원 텍스트 → RetrievedKnowledgeItem 변환.

NOTE: session은 현재 벡터 검색을 거치지 않는 direct context injection 경로다.
      raw text를 그대로 wrapping하므로 "hit dict → item" 형태가 아니다.
      이 비대칭성은 session의 예외적 성격을 반영한다.
      향후 session이 벡터 검색 대상이 되면 이 mapper도 재설계 대상이다.
"""

from __future__ import annotations

from schemas.knowledge import RetrievedKnowledgeItem


def session_text_to_item(
    *,
    session_id: int | None,
    reference_document_text: str,
    session_title: str | None = None,
) -> RetrievedKnowledgeItem:
    """
    session 첨부 텍스트 → RetrievedKnowledgeItem.

    score는 의미가 없으므로 1.0 고정.
    """
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
