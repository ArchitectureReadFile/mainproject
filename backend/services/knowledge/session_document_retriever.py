"""
services/knowledge/session_document_retriever.py

Session 지식원 retriever.

역할:
    - 챗봇 임시 업로드 문서를 retrieval 결과 계약으로 감싼다.
    - include_session=True이고 reference_document_text가 있을 때만 사용.
    - 현재: ChatSession.reference_document_text 단일 텍스트를
      RetrievedKnowledgeItem 1개로 반환 (직접 프롬프트 주입 대체).
    - score는 의미 없으므로 1.0 고정.

현재 매핑:
    ChatSession.reference_document_text (str)
    → RetrievedKnowledgeItem(
          knowledge_type="session",
          source_type="session_document",
          source_id=f"session:{session_id}",
          title=session_title or "첨부 문서",
          chunk_text=reference_document_text,
          score=1.0,
      )

TODO:
    - reference_document_text가 매우 길 경우 분할 후 top chunk 반환으로 교체 가능.
    - session_document_id를 별도 엔티티로 관리하게 되면 source_id 교체.
"""

from __future__ import annotations

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem


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

        Args:
            reference_document_text: ChatSession.reference_document_text
            session_title: 표시용 제목 (없으면 "첨부 문서")
        """
        if not request.include_session or not reference_document_text.strip():
            return []

        return [
            RetrievedKnowledgeItem(
                knowledge_type="session",
                source_type="session_document",
                source_id=f"session:{request.session_id}",
                title=session_title or "첨부 문서",
                chunk_text=reference_document_text.strip(),
                score=1.0,
                metadata={
                    "session_id": request.session_id,
                    "session_title": session_title,
                },
            )
        ]
