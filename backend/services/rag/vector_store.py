"""
services/rag/vector_store.py

벡터 DB 인터페이스 레이어.
현재 구현체: Qdrant
교체 시 이 파일만 수정하면 된다.

환경 변수:
    QDRANT_HOST          기본값 "qdrant"
    QDRANT_PORT          기본값 6333
    QDRANT_COLLECTION    기본값 "precedents"
    EMBEDDING_DIM        기본값 768  (KURE-v1 기준)
    HYBRID_ALPHA         기본값 0.8  (BM25 비중)

retrieval 반환 계약:
    search() / hybrid_search() 모두 동일한 필드를 반환한다.
    chunk payload에 저장된 메타는 retrieval 결과에도 일관되게 포함된다.
    grouping_service가 소비하는 필드는 모두 이 계약에 포함되어야 한다.
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

# retrieval 결과 dict에 포함할 payload 필드 목록.
# chunk_builder.PrecedentChunk payload 계약과 일치해야 한다.
_RETRIEVAL_PAYLOAD_FIELDS = (
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
    """chunk_id 문자열을 Qdrant point id(uint64)로 변환한다."""
    return int(hashlib.md5(chunk_id.encode()).hexdigest(), 16) % (2**63)


def _hit_to_dict(payload: dict, score: float, extra: dict | None = None) -> dict:
    """
    Qdrant payload를 retrieval 결과 dict로 변환한다.
    _RETRIEVAL_PAYLOAD_FIELDS에 선언된 필드만 추출하므로
    payload에 필드가 없으면 None으로 채워진다.
    """
    result = {field: payload.get(field) for field in _RETRIEVAL_PAYLOAD_FIELDS}
    result["score"] = score
    if extra:
        result.update(extra)
    return result


def upsert(
    chunk_id: str,
    embedding: list[float],
    payload: dict | None = None,
) -> None:
    """chunk 벡터를 저장한다. payload에 precedent_id 필수."""
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
) -> list[dict]:
    """
    Dense 검색. chunk 단위 hit 반환.

    반환 필드: _RETRIEVAL_PAYLOAD_FIELDS + score
    grouping_service가 소비하는 모든 메타 필드가 포함된다.
    """
    _ensure_collection()
    client = _get_client()
    hits = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
    )
    return [_hit_to_dict(hit.payload, hit.score) for hit in hits]


def hybrid_search(
    query_embedding: list[float],
    bm25_results: list[dict],
    top_k: int = 5,
    alpha: float | None = None,
) -> list[dict]:
    """
    BM25 + Dense 하이브리드 검색. chunk 단위 hit 반환.
    bm25_results의 key는 chunk_id 기준이어야 한다.

    반환 필드: _RETRIEVAL_PAYLOAD_FIELDS + score + dense_score + bm25_score
    """
    a = alpha if alpha is not None else HYBRID_ALPHA

    fetch_k = max(top_k * 2, 20)
    dense_results = search(query_embedding, top_k=fetch_k)

    dense_map: dict[str, float] = {r["chunk_id"]: r["score"] for r in dense_results}
    bm25_map: dict[str, float] = {r["chunk_id"]: r["score"] for r in bm25_results}

    all_ids = set(dense_map.keys()) | set(bm25_map.keys())

    def _normalize(score_map: dict[str, float]) -> dict[str, float]:
        if not score_map:
            return {}
        min_s = min(score_map.values())
        max_s = max(score_map.values())
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
    point_ids = [_chunk_id_to_point_id(cid) for cid in top_chunk_ids]
    points = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=point_ids,
        with_payload=True,
    )
    payload_map = {p.payload.get("chunk_id"): p.payload for p in points}

    results = []
    for cid in top_chunk_ids:
        p = payload_map.get(cid)
        if not p:
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
    """precedent_id 기준으로 해당 판례의 모든 chunk를 삭제한다."""
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        logger.debug("delete 스킵: 컬렉션 없음 (%s)", QDRANT_COLLECTION)
        return
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="precedent_id",
                        match=qmodels.MatchValue(value=precedent_id),
                    )
                ]
            )
        ),
    )
    logger.info("Qdrant delete 완료: precedent_id=%s (chunk 전체)", precedent_id)


def count() -> int:
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        return 0
    result = client.count(collection_name=QDRANT_COLLECTION, exact=True)
    return result.count


def clear() -> None:
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        return
    client.delete_collection(collection_name=QDRANT_COLLECTION)
    logger.info("Qdrant 컬렉션 삭제 완료: %s", QDRANT_COLLECTION)
