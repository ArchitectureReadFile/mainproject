"""
services/rag/group_document_retrieval_service.py

그룹 문서 RAG 검색 + document_id 기준 그룹핑.

반환 계약:
[
    {
        "document_id": int,
        "group_id":    int,
        "file_name":   str,
        "score":       float,
        "chunks": [
            {
                "chunk_id":      str,
                "text":          str,
                "chunk_type":    str,   # "body" | "table"
                "section_title": str | None,
                "order_index":   int,
                "score":         float,
            },
            ...
        ],
    },
    ...
]
"""

import logging

from qdrant_client.http import models as qmodels

from schemas.search import SearchMode
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_query

logger = logging.getLogger(__name__)

TOP_CHUNKS_PER_DOCUMENT = 2
MIN_SCORE_GAP = 0.05


def retrieve_group_documents(
    query: str,
    group_id: int,
    top_k: int,
    search_mode: SearchMode,
) -> list[dict]:
    """
    group_id 범위 내 그룹 문서 chunk를 검색하고 document_id 기준으로 그룹핑해 반환한다.
    """
    query_vector = embed_query(query)
    fetch_k = top_k * 4

    # group_id 필터: 해당 그룹 문서만 검색
    group_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="group_id",
                match=qmodels.MatchValue(value=group_id),
            ),
            qmodels.FieldCondition(
                key="source_type",
                match=qmodels.MatchValue(value="pdf"),
            ),
        ]
    )

    if search_mode == SearchMode.dense:
        chunk_hits = vector_store.search(
            query_embedding=query_vector,
            top_k=fetch_k,
            query_filter=group_filter,
        )
    else:
        bm25_hits = bm25_store.search_documents(
            query=query, group_id=group_id, top_k=fetch_k * 2
        )
        chunk_hits = vector_store.hybrid_search(
            query_embedding=query_vector,
            bm25_results=bm25_hits,
            top_k=fetch_k,
            query_filter=group_filter,
        )

    grouped = _group_by_document(chunk_hits)
    return grouped[:top_k]


def _group_by_document(chunk_hits: list[dict]) -> list[dict]:
    """
    chunk hit 리스트를 document_id 기준으로 그룹핑한다.
    각 document에서 상위 TOP_CHUNKS_PER_DOCUMENT개만 유지하고 중복 제거.
    """
    grouped: dict[int, dict] = {}

    for hit in chunk_hits:
        doc_id = hit.get("document_id")
        if doc_id is None:
            continue

        score = hit.get("score", 0.0)
        chunk_entry = {
            "chunk_id": hit.get("chunk_id"),
            "text": hit.get("text"),
            "chunk_type": hit.get("chunk_type"),
            "section_title": hit.get("section_title"),
            "order_index": hit.get("order_index"),
            "score": score,
        }

        if doc_id not in grouped:
            grouped[doc_id] = {
                "document_id": doc_id,
                "group_id": hit.get("group_id"),
                "file_name": hit.get("file_name"),
                "score": score,
                "chunks": [chunk_entry],
            }
        else:
            if score > grouped[doc_id]["score"]:
                grouped[doc_id]["score"] = score
            grouped[doc_id]["chunks"].append(chunk_entry)

    # 각 document에서 상위 chunk만 유지 + 유사 score 중복 제거
    for group in grouped.values():
        chunks = sorted(group["chunks"], key=lambda c: c["score"], reverse=True)
        deduped: list[dict] = []
        for chunk in chunks:
            if len(deduped) >= TOP_CHUNKS_PER_DOCUMENT:
                break
            if deduped and abs(chunk["score"] - deduped[-1]["score"]) < MIN_SCORE_GAP:
                continue
            deduped.append(chunk)
        group["chunks"] = deduped

    return sorted(grouped.values(), key=lambda g: g["score"], reverse=True)
