"""
domains/rag/vector_store.py

벡터 DB 인터페이스 레이어.
현재 구현체: Qdrant
교체 시 이 파일만 수정하면 된다.

환경 변수:
    QDRANT_HOST          기본값 "qdrant"
    QDRANT_PORT          기본값 6333
    QDRANT_COLLECTION    기본값 "precedents"
    EMBEDDING_DIM        기본값 768  (KURE-v1 기준)
    HYBRID_ALPHA         기본값 0.8  (BM25 비중)

corpus isolation 보장:
    - search() / hybrid_search()는 query_filter를 항상 dense 검색에 적용한다.
    - hybrid_search()는 BM25 후보를 caller가 scope-aware하게 넘겨야 한다.
      (bm25_store.search vs bm25_store.search_documents 분리로 보장)
    - hybrid_search()는 최종 retrieve() 후 payload를 재필터링해 isolation을 이중 보장한다.
"""

import hashlib
import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "precedents")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
HYBRID_ALPHA = float(os.getenv("HYBRID_ALPHA", "0.8"))

_client: QdrantClient | None = None

_PRECEDENT_PAYLOAD_FIELDS = (
    "chunk_id",
    "precedent_id",
    "title",
    "source_url",
    "case_number",
    "case_name",
    "court_name",
    "judgment_date",
    "plaintiff",
    "defendant",
    "lower_court_case",
    "text",
    "section_title",
    "element_type",
    "order_index",
)

_GROUP_DOC_PAYLOAD_FIELDS = (
    "chunk_id",
    "document_id",
    "group_id",
    "file_name",
    "source_type",
    "chunk_type",
    "section_title",
    "order_index",
    "text",
)


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.info("Qdrant 연결: %s:%s", QDRANT_HOST, QDRANT_PORT)
    return _client


def _ensure_collection() -> None:
    client = _get_client()
    existing = {c.name: c for c in client.get_collections().collections}

    if QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=EMBEDDING_DIM,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info("Qdrant 컬렉션 생성: %s (dim=%s)", QDRANT_COLLECTION, EMBEDDING_DIM)
        return

    info = client.get_collection(QDRANT_COLLECTION)
    stored_dim = info.config.params.vectors.size
    if stored_dim != EMBEDDING_DIM:
        raise ValueError(
            f"Qdrant 컬렉션 '{QDRANT_COLLECTION}' 차원 불일치: "
            f"저장된 dim={stored_dim}, 현재 EMBEDDING_DIM={EMBEDDING_DIM}."
        )
    logger.debug("Qdrant 컬렉션 확인 완료: %s (dim=%s)", QDRANT_COLLECTION, stored_dim)


def _chunk_id_to_point_id(chunk_id: str) -> int:
    return int(hashlib.md5(chunk_id.encode()).hexdigest(), 16) % (2**63)


def _payload_fields(payload: dict) -> tuple:
    """payload의 source_type에 따라 적합한 필드 목록을 반환한다."""
    return (
        _GROUP_DOC_PAYLOAD_FIELDS
        if payload.get("source_type") == "pdf"
        else _PRECEDENT_PAYLOAD_FIELDS
    )


def _hit_to_dict(payload: dict, score: float, extra: dict | None = None) -> dict:
    fields = _payload_fields(payload)
    result = {field: payload.get(field) for field in fields}
    result["score"] = score
    if extra:
        result.update(extra)
    return result


def _passes_filter(payload: dict, query_filter: qmodels.Filter | None) -> bool:
    """
    payload가 query_filter 조건을 만족하는지 Python 레벨에서 재검증한다.
    retrieve()는 filter를 적용하지 않으므로 BM25-only hit를 걸러내기 위해 사용한다.

    지원하는 조건: FieldCondition + MatchValue (must 리스트)
    나머지 복잡한 filter는 통과로 처리한다 (Qdrant가 dense 단계에서 이미 적용).
    """
    if query_filter is None:
        return True
    for condition in query_filter.must or []:
        if not isinstance(condition, qmodels.FieldCondition):
            continue
        if not isinstance(condition.match, qmodels.MatchValue):
            continue
        if payload.get(condition.key) != condition.match.value:
            return False
    return True


def upsert(
    chunk_id: str,
    embedding: list[float],
    payload: dict | None = None,
) -> None:
    _ensure_collection()
    client = _get_client()
    point_id = _chunk_id_to_point_id(chunk_id)
    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            qmodels.PointStruct(
                id=point_id,
                vector=embedding,
                payload={"chunk_id": chunk_id, **(payload or {})},
            )
        ],
    )
    logger.debug("Qdrant upsert 완료: chunk_id=%s (point_id=%s)", chunk_id, point_id)


def search(
    query_embedding: list[float],
    top_k: int = 5,
    query_filter: qmodels.Filter | None = None,
) -> list[dict]:
    """Dense 검색. query_filter가 있으면 Qdrant 레벨에서 적용된다."""
    _ensure_collection()
    client = _get_client()
    hits = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
        query_filter=query_filter,
    )
    return [_hit_to_dict(hit.payload, hit.score) for hit in hits]


def hybrid_search(
    query_embedding: list[float],
    bm25_results: list[dict],
    top_k: int = 5,
    alpha: float | None = None,
    query_filter: qmodels.Filter | None = None,
) -> list[dict]:
    """
    BM25 + Dense 하이브리드 검색.

    isolation 보장 3단계:
    1. bm25_results는 caller가 scope-aware corpus에서 가져온 것이어야 한다.
       (bm25_store.search vs search_documents 분리로 보장)
    2. dense 검색에 query_filter를 적용한다.
    3. retrieve() 후 payload를 재검증해 filter 미통과 chunk를 제거한다.
    """
    a = alpha if alpha is not None else HYBRID_ALPHA
    fetch_k = max(top_k * 2, 20)

    dense_results = search(query_embedding, top_k=fetch_k, query_filter=query_filter)
    dense_map: dict[str, float] = {r["chunk_id"]: r["score"] for r in dense_results}
    bm25_map: dict[str, float] = {r["chunk_id"]: r["score"] for r in bm25_results}

    all_ids = set(dense_map.keys()) | set(bm25_map.keys())

    def _normalize(score_map: dict[str, float]) -> dict[str, float]:
        if not score_map:
            return {}
        min_s, max_s = min(score_map.values()), max(score_map.values())
        span = max_s - min_s
        if span == 0:
            return {k: 1.0 for k in score_map}
        return {k: (v - min_s) / span for k, v in score_map.items()}

    norm_dense = _normalize(dense_map)
    norm_bm25 = _normalize(bm25_map)

    hybrid_scores: dict[str, float] = {
        cid: a * norm_bm25.get(cid, 0.0) + (1 - a) * norm_dense.get(cid, 0.0)
        for cid in all_ids
    }

    top_chunk_ids = sorted(hybrid_scores, key=lambda x: hybrid_scores[x], reverse=True)[
        :top_k
    ]

    client = _get_client()
    points = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=[_chunk_id_to_point_id(cid) for cid in top_chunk_ids],
        with_payload=True,
    )
    payload_map = {p.payload.get("chunk_id"): p.payload for p in points}

    results = []
    for cid in top_chunk_ids:
        p = payload_map.get(cid)
        if not p:
            continue
        # 3단계: payload 재필터링 — BM25-only hit가 scope를 뚫는 것을 차단
        if not _passes_filter(p, query_filter):
            logger.debug("hybrid_search: scope 불일치로 제거된 chunk_id=%s", cid)
            continue
        results.append(
            _hit_to_dict(
                p,
                score=hybrid_scores[cid],
                extra={
                    "dense_score": dense_map.get(cid, 0.0),
                    "bm25_score": bm25_map.get(cid, 0.0),
                },
            )
        )
    return results


def delete(precedent_id: int) -> None:
    _delete_by_field("precedent_id", precedent_id)
    logger.info("Qdrant delete 완료: precedent_id=%s", precedent_id)


def delete_document(document_id: int) -> None:
    _delete_by_field("document_id", document_id)
    logger.info("Qdrant delete 완료: document_id=%s", document_id)


def _delete_by_field(field: str, value: int) -> None:
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        return
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key=field, match=qmodels.MatchValue(value=value)
                    )
                ]
            )
        ),
    )


def count() -> int:
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        return 0
    return client.count(collection_name=QDRANT_COLLECTION, exact=True).count


def clear() -> None:
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        return
    client.delete_collection(collection_name=QDRANT_COLLECTION)
    logger.info("Qdrant 컬렉션 삭제 완료: %s", QDRANT_COLLECTION)
