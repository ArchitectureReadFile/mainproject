"""
services/knowledge/session_document_retriever.py

Session 지식원 retriever.

━━━ 예외 경로 명시 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 retriever는 platform / workspace와 달리 벡터 검색을 수행하지 않는다.
ChatSession에 첨부된 문서 텍스트를 직접 RetrievedKnowledgeItem으로 wrapping하는
direct context injection 경로다.

따라서:
    - search service를 호출하지 않는다
    - score는 의미가 없으므로 1.0 고정
    - retrieve_from_text() 시그니처가 다른 retriever의 retrieve()와 다르다

향후 session 문서가 벡터 검색 대상이 되면 이 클래스는 재설계 대상이다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TODO:
    - reference_document_text가 매우 길 경우 분할 후 top chunk 반환으로 교체 가능.
    - session_document_id를 별도 엔티티로 관리하게 되면 source_id 교체.
"""

from __future__ import annotations

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from services.knowledge.mappers.session_item_mapper import session_text_to_item


class SessionDocumentRetriever:
    def retrieve_from_text(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        reference_document_text: str,
        session_title: str | None = None,
    ) -> list[RetrievedKnowledgeItem]:
        """
        reference_document_text를 RetrievedKnowledgeItem으로 감싸 반환한다.

        벡터 검색 없이 텍스트를 직접 context로 주입하는 예외 경로다.

        Args:
            reference_document_text: ChatSession.reference_document_text
            session_title: 표시용 제목 (없으면 "첨부 문서")
        """
        if not request.include_session or not reference_document_text.strip():
            return []

        return [
            session_text_to_item(
                session_id=request.session_id,
                reference_document_text=reference_document_text,
                session_title=session_title,
            )
        ]
