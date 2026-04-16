"""
domains/rag/document_chunk_service.py

DocumentSchema -> GroupDocumentChunk 리스트 변환 계층.

책임:
    - DocumentSchema → GroupDocument 매핑
    - build_chunks_from_group_document() 호출
    - chunk metadata 조립 (chunk_id, document_id, group_id, file_name, source_type, ...)
    - vector_store._GROUP_DOC_PAYLOAD_FIELDS 계약과 호환 유지

비책임:
    - 추출 / normalize
    - embed / store
    - retrieval / rerank
    - summary 생성

전략 override:
    strategy_override를 넘기면 env 설정(DOCUMENT_CHUNK_STRATEGY)보다 우선한다.
    None이면 env 설정을 따른다.
"""

from __future__ import annotations

from domains.document.document_schema import DocumentSchema
from domains.rag.group_document_chunk_builder import (
    ChunkStrategy,
    GroupDocument,
    GroupDocumentChunk,
    build_chunks_from_group_document,
)


class DocumentChunkService:
    def build_group_document_chunks(
        self,
        document: DocumentSchema,
        *,
        document_id: int,
        group_id: int,
        file_name: str,
        source_type: str = "pdf",
        strategy_override: ChunkStrategy | None = None,
    ) -> list[GroupDocumentChunk]:
        """
        DocumentSchema -> GroupDocumentChunk 리스트.

        strategy_override: "auto" | "section" | "page" | "text" | None
            None이면 env DOCUMENT_CHUNK_STRATEGY를 따른다.
        """
        doc = GroupDocument(
            document_id=document_id,
            group_id=group_id,
            file_name=file_name,
            body_text=document.body_text,
            table_blocks=[tb.text for tb in document.table_blocks],
            source_type=source_type,
            sections=document.sections,
            pages=document.pages,
        )
        return build_chunks_from_group_document(
            doc, strategy_override=strategy_override
        )
