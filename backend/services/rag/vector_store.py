"""
services/rag/vector_store.py

벡터 DB 인터페이스 레이어.
현재 구현체: Qdrant
교체 시 이 파일만 수정하면 된다.

환경 변수:
    QDRANT_HOST          기본값 "qdrant"
    QDRANT_PORT          기본값 6333
    QDRANT_COLLECTION    기본값 "precedents"
    EMBEDDING_DIM        기본값 768  (E5-base 기준)
    HYBRID_ALPHA         기본값 0.8  (BM25 비중, 논문 기준)
"""

import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "precedents")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
HYBRID_ALPHA = float(os.getenv("HYBRID_ALPHA", "0.8"))  # BM25 비중

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.info("Qdrant 연결: %s:%s", QDRANT_HOST, QDRANT_PORT)
    return _client


def _ensure_collection() -> None:
    """
    컬렉션이 없으면 생성한다.
    이미 존재하면 차원(dim)이 EMBEDDING_DIM과 일치하는지 확인한다.
    불일치 시 명시적 에러를 발생시켜 조용한 런타임 오류를 방지한다.
    """
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
            f"저장된 dim={stored_dim}, 현재 EMBEDDING_DIM={EMBEDDING_DIM}. "
            f"모델을 바꿨다면 컬렉션을 삭제하거나 QDRANT_COLLECTION 이름을 변경하세요."
        )
    logger.debug("Qdrant 컬렉션 확인 완료: %s (dim=%s)", QDRANT_COLLECTION, stored_dim)


def upsert(
    precedent_id: int,
    embedding: list[float],
    payload: dict | None = None,
) -> None:
    """판례 벡터를 저장한다 (없으면 추가, 있으면 덮어쓰기)."""
    _ensure_collection()
    client = _get_client()
    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            qmodels.PointStruct(
                id=precedent_id,
                vector=embedding,
                payload=payload or {},
            )
        ],
    )
    logger.info("Qdrant upsert 완료: precedent_id=%s", precedent_id)


def search(
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Dense 검색 (코사인 유사도 기준 top-k).

    Returns:
        [{"precedent_id", "score", "title", "source_url", "text"}, ...]
    """
    _ensure_collection()
    client = _get_client()
    hits = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "precedent_id": hit.id,
            "score": hit.score,
            "title": hit.payload.get("title"),
            "source_url": hit.payload.get("source_url"),
            "text": hit.payload.get("text"),
        }
        for hit in hits
    ]


def hybrid_search(
    query_embedding: list[float],
    bm25_results: list[dict],
    top_k: int = 5,
    alpha: float | None = None,
) -> list[dict]:
    """
    BM25 + Dense 하이브리드 검색.

    두 점수를 각각 Min-Max 정규화해서 [0, 1]로 맞춘 뒤 선형 결합한다:
        hybrid_score = α × norm(BM25) + (1-α) × norm(Dense)

    BM25 점수는 0 이상의 원시값이고, Dense(코사인) 점수는 [-1, 1] 범위이므로
    둘 다 동일하게 Min-Max 정규화만 적용해 [0, 1]로 맞춘다.
    추가 변환 없이 정규화만 하면 두 점수의 스케일이 공정하게 비교된다.

    Args:
        query_embedding: Dense 검색용 질문 벡터
        bm25_results:    bm25_store.search() 결과
        top_k:           반환할 최대 결과 수
        alpha:           BM25 비중 (None이면 HYBRID_ALPHA env 사용)

    Returns:
        [{"precedent_id", "score", "title", "source_url", "text",
          "dense_score", "bm25_score"}, ...]
    """
    a = alpha if alpha is not None else HYBRID_ALPHA

    # Dense 검색 (합산 후 재정렬 여유분)
    fetch_k = max(top_k * 2, 20)
    dense_results = search(query_embedding, top_k=fetch_k)

    dense_map: dict[int, float] = {r["precedent_id"]: r["score"] for r in dense_results}
    bm25_map: dict[int, float] = {r["precedent_id"]: r["score"] for r in bm25_results}

    all_ids = set(dense_map.keys()) | set(bm25_map.keys())

    def _normalize(score_map: dict[int, float]) -> dict[int, float]:
        """Min-Max 정규화 → [0, 1]. 값이 하나뿐이거나 모두 같으면 1.0으로 통일."""
        if not score_map:
            return {}
        min_s = min(score_map.values())
        max_s = max(score_map.values())
        span = max_s - min_s
        if span == 0:
            return {k: 1.0 for k in score_map}
        return {k: (v - min_s) / span for k, v in score_map.items()}

    # BM25와 Dense 모두 동일하게 Min-Max 정규화만 적용
    norm_dense = _normalize(dense_map)
    norm_bm25 = _normalize(bm25_map)

    # 하이브리드 점수 계산 (후보에 없는 쪽은 0으로 처리)
    hybrid_scores: dict[int, float] = {
        pid: a * norm_bm25.get(pid, 0.0) + (1 - a) * norm_dense.get(pid, 0.0)
        for pid in all_ids
    }

    top_ids = sorted(hybrid_scores, key=lambda x: hybrid_scores[x], reverse=True)[
        :top_k
    ]

    # payload 조회
    client = _get_client()
    points = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=top_ids,
        with_payload=True,
    )
    payload_map = {p.id: p.payload for p in points}

    return [
        {
            "precedent_id": pid,
            "score": hybrid_scores[pid],
            "dense_score": dense_map.get(pid, 0.0),
            "bm25_score": bm25_map.get(pid, 0.0),
            "title": payload_map.get(pid, {}).get("title"),
            "source_url": payload_map.get(pid, {}).get("source_url"),
            "text": payload_map.get(pid, {}).get("text"),
        }
        for pid in top_ids
        if pid in payload_map
    ]


def delete(precedent_id: int) -> None:
    """판례 벡터를 삭제한다. 컬렉션이 없으면 조용히 스킵."""
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        logger.debug("delete 스킵: 컬렉션 없음 (%s)", QDRANT_COLLECTION)
        return
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=qmodels.PointIdsList(points=[precedent_id]),
    )
    logger.info("Qdrant delete 완료: precedent_id=%s", precedent_id)


def count() -> int:
    """컬렉션에 저장된 벡터 수를 반환한다. 컬렉션이 없으면 0."""
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        return 0
    result = client.count(collection_name=QDRANT_COLLECTION, exact=True)
    return result.count


def clear() -> None:
    """컬렉션 전체를 비운다. 컬렉션이 없으면 조용히 스킵."""
    client = _get_client()
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        logger.debug("clear 스킵: 컬렉션 없음 (%s)", QDRANT_COLLECTION)
        return
    client.delete_collection(collection_name=QDRANT_COLLECTION)
    logger.info("Qdrant 컬렉션 삭제 완료: %s", QDRANT_COLLECTION)
