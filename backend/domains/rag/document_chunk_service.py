"""
services/rag/document_chunk_service.py

DocumentSchema -> GroupDocumentChunk 리스트 변환 계층.

책임:
    - DocumentSchema.body_text -> body chunk 분할
    - DocumentSchema.table_blocks -> table chunk 분할
    - chunk metadata 조립 (chunk_id, document_id, group_id, file_name, source_type, ...)
    - 현재 vector_store._GROUP_DOC_PAYLOAD_FIELDS 계약과 호환 유지

비책임:
    - 추출 / normalize
    - embed / store
    - retrieval / rerank
    - summary 생성

내부 구현:
    선호안 A: DocumentSchema -> GroupDocument 매핑 후
    기존 build_chunks_from_group_document() 재사용.
    chunk 분할 정책 회귀 없이 저장 계약을 유지한다.
"""

from __future__ import annotations

from domains.document.document_schema import DocumentSchema
from domains.rag.group_document_chunk_builder import (
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
    ) -> list[GroupDocumentChunk]:
        """
        DocumentSchema -> GroupDocumentChunk 리스트.

        table_blocks는 DocumentTableBlock 객체 리스트이므로
        .text 필드만 꺼내 GroupDocument(table_blocks: list[str]) 계약에 맞춘다.
        """
        doc = GroupDocument(
            document_id=document_id,
            group_id=group_id,
            file_name=file_name,
            body_text=document.body_text,
            table_blocks=[tb.text for tb in document.table_blocks],
            source_type=source_type,
        )
        return build_chunks_from_group_document(doc)
