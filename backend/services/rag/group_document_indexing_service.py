"""
services/rag/group_document_indexing_service.py

그룹 문서 PDF → extract → chunk → Qdrant + BM25 인덱싱 파이프라인.

사용처:
    tasks/group_document_task.py (Celery background task)
    또는 동기 호출 (테스트, 재인덱싱 스크립트)
"""

import logging

from services.document_extract_service import DocumentExtractService
from services.document_input_builder import build_rag_source
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_passages
from services.rag.group_document_chunk_builder import (
    GroupDocument,
    GroupDocumentChunk,
    build_chunks_from_group_document,
)

logger = logging.getLogger(__name__)

_extract_service = DocumentExtractService()


def index_group_document(
    document_id: int,
    group_id: int,
    file_name: str,
    file_path: str,
) -> int:
    """
    PDF 파일을 추출 → chunk → Qdrant + BM25에 저장한다.

    Returns:
        저장된 chunk 수
    """
    logger.info(
        "[그룹문서 인덱싱 시작] document_id=%s, group_id=%s, file=%s",
        document_id,
        group_id,
        file_name,
    )

    # 1. 기존 인덱스 삭제 (재인덱싱 안전)
    vector_store.delete_document(document_id)
    bm25_store.delete_document(document_id)

    # 2. PDF 추출
    extracted = _extract_service.extract(file_path)

    # 3. RAG source 조립
    rag_source = build_rag_source(extracted)
    doc = GroupDocument(
        document_id=document_id,
        group_id=group_id,
        file_name=file_name,
        body_text=rag_source["body_text"],
        table_blocks=rag_source["table_blocks"],
    )

    # 4. chunk 생성
    chunks: list[GroupDocumentChunk] = build_chunks_from_group_document(doc)
    if not chunks:
        logger.warning("[그룹문서 인덱싱] chunk 없음: document_id=%s", document_id)
        return 0

    # 5. 배치 임베딩
    texts = [c["text"] for c in chunks]
    embeddings = embed_passages(texts)

    # 6. Qdrant + BM25 저장
    for chunk, embedding in zip(chunks, embeddings):
        payload = {k: v for k, v in chunk.items() if k != "text"}
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
