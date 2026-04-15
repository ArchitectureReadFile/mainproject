"""
domains/rag/group_document_indexing_service.py

그룹 문서 RAG 인덱싱 파이프라인.

흐름: DocumentSchema(cache) → chunk → embed → Qdrant + BM25

■ normalized document cache 재사용:
    DocumentSchemaResolver.get_or_create()를 통해 DocumentSchema를 얻는다.
    직접 DocumentExtractService / DocumentNormalizeService를 호출하지 않는다.
    summary_process.py와 동일한 cache를 사용하므로 두 경로 간 직렬화된다.

■ 인덱싱 시점 계약:
    승인(APPROVED) 후에만 인덱싱된다.
    index_approved_document task는 내부에서 APPROVED 여부를 다시 확인한다.
    인덱싱 시점에는 document.document_type / document.category가 DB에 저장된 이후여야 한다.
    (process_file 완료 후 enqueue하여 stale metadata 인덱싱을 방지한다.)

사용처:
    domains/document/index_task.py (Celery background task)
    또는 동기 호출 (테스트, 재인덱싱 스크립트)
"""

import logging

from domains.document.document_schema_resolver import DocumentSchemaResolver
from domains.rag import bm25_store, vector_store
from domains.rag.document_chunk_service import DocumentChunkService
from domains.rag.embedding_service import embed_passages
from domains.rag.group_document_chunk_builder import GroupDocumentChunk

logger = logging.getLogger(__name__)

_document_schema_resolver = DocumentSchemaResolver()
_chunk_service = DocumentChunkService()


def index_group_document(
    document_id: int,
    group_id: int,
    file_name: str,
    file_path: str,
    *,
    document_type: str | None = None,
    category: str | None = None,
) -> int:
    """
    PDF 파일을 추출 → normalize → chunk → Qdrant + BM25에 저장한다.

    document_type / category 는 각 chunk payload에 포함되어
    retrieval 단계의 boost에 사용된다.

    Returns:
        저장된 chunk 수
    """
    logger.info(
        "[그룹문서 인덱싱 시작] document_id=%s, group_id=%s, file=%s, "
        "document_type=%s, category=%s",
        document_id,
        group_id,
        file_name,
        document_type,
        category,
    )

    # 1. normalized document 로드 또는 생성
    document = _document_schema_resolver.get_or_create(
        document_id=document_id,
        file_path=file_path,
    )

    # 2. chunk 생성
    chunks: list[GroupDocumentChunk] = _chunk_service.build_group_document_chunks(
        document,
        document_id=document_id,
        group_id=group_id,
        file_name=file_name,
    )
    if not chunks:
        logger.warning("[그룹문서 인덱싱] chunk 없음: document_id=%s", document_id)
        return 0

    # 3. 배치 임베딩
    texts = [c["text"] for c in chunks]
    embeddings = embed_passages(texts)

    new_chunk_ids = {chunk["chunk_id"] for chunk in chunks}
    existing_chunk_ids = vector_store.get_document_chunk_ids(
        document_id
    ) | bm25_store.get_document_chunk_ids(document_id)

    # 4. Qdrant + BM25 저장
    # 기존 chunk_id와 겹치는 항목은 upsert로 덮어쓰고,
    # 전체 쓰기가 성공한 뒤 stale chunk만 정리한다.
    for chunk, embedding in zip(chunks, embeddings):
        payload = {k: v for k, v in chunk.items() if k != "text"}
        # 분류 metadata 추가 — retrieval boost 용도
        payload["document_type"] = document_type
        payload["category"] = category

        vector_store.upsert(
            chunk_id=chunk["chunk_id"],
            embedding=embedding,
            payload={**payload, "text": chunk["text"]},
        )
        bm25_store.upsert_document_chunk(
            chunk_id=chunk["chunk_id"],
            document_id=document_id,
            group_id=group_id,
            text=chunk["text"],
        )

    stale_chunk_ids = existing_chunk_ids - new_chunk_ids
    vector_store.delete_document_chunks(document_id, stale_chunk_ids)
    bm25_store.delete_document_chunks(document_id, group_id, stale_chunk_ids)

    logger.info(
        "[그룹문서 인덱싱 완료] document_id=%s, chunks=%d",
        document_id,
        len(chunks),
    )
    return len(chunks)


def deindex_group_document(document_id: int) -> None:
    """document_id 기준으로 벡터 + BM25 인덱스를 모두 삭제한다."""
    vector_store.delete_document(document_id)
    bm25_store.delete_document(document_id)
    logger.info("[그룹문서 디인덱싱] document_id=%s", document_id)
