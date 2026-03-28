"""
services/knowledge/platform_knowledge_retriever.py

Platform 지식원 retriever.

역할:
    - 플랫폼 기본 지식(판례 RAG)을 검색한다.
    - 항상 사용 (include_platform=True 기본).
    - 현재 retrieve_precedents() → group_chunks_by_precedent() 결과를
      RetrievedKnowledgeItem 리스트로 변환한다.

현재 매핑:
    retrieve_precedents() → grouped precedent dict
    → RetrievedKnowledgeItem(
           knowledge_type="platform",
           source_type="precedent",
           source_id=precedent_id,
           title=title,
           chunk_text=chunks[].text 합산,
           metadata={source_url, case_number, court_name, ...},
           score=score,
       )
"""

from __future__ import annotations

from schemas.knowledge import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from schemas.search import SearchMode
from services.rag.retrieval_service import retrieve_precedents

_PLATFORM_META_FIELDS = (
    "source_url",
    "case_number",
    "case_name",
    "court_name",
    "judgment_date",
    "plaintiff",
    "defendant",
    "lower_court_case",
)


class PlatformKnowledgeRetriever:
    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        search_mode: SearchMode = SearchMode.dense,
    ) -> list[RetrievedKnowledgeItem]:
        if not request.include_platform:
            return []

        grouped = retrieve_precedents(
            query=request.query,
            top_k=request.top_k,
            search_mode=search_mode,
        )
        return [self._to_item(g) for g in grouped]

    def _to_item(self, grouped: dict) -> RetrievedKnowledgeItem:
        chunks = grouped.get("chunks") or []
        chunk_text = "\n".join(c.get("text", "") for c in chunks).strip()
        chunk_id = chunks[0].get("chunk_id") if chunks else None

        return RetrievedKnowledgeItem(
            knowledge_type="platform",
            source_type="precedent",
            source_id=grouped.get("precedent_id", ""),
            title=grouped.get("title") or "제목 없음",
            chunk_text=chunk_text,
            score=grouped.get("score", 0.0),
            chunk_id=chunk_id,
            metadata={
                field: grouped.get(field)
                for field in _PLATFORM_META_FIELDS
                if grouped.get(field) is not None
            },
        )
