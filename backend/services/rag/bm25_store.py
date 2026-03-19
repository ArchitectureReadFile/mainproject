"""
services/rag/bm25_store.py

BM25 키워드 검색 레이어.

저장 방식:
    판례 원문 텍스트를 Redis에 저장한다.
    BM25Okapi 인덱스는 직렬화하지 않고, 검색 시마다 Redis에서 텍스트를 읽어 재구축한다.
    따라서 컨테이너 재시작 후에도 텍스트는 Redis에 남아 있으며,
    첫 검색 호출 시 인덱스가 메모리 위에 다시 만들어진다.

Redis 키 구조:
    "bm25:docs"  → Hash  {str(precedent_id): text}
    "bm25:ids"   → List  [str(precedent_id), ...]

토크나이저:
    soynlp 기반 토크나이저를 사용한다.
    저장된 문서들로 단어 점수를 학습한 뒤 한국어 단어 경계를 추정해
    BM25 키워드 매칭 품질을 높인다.

환경 변수:
    REDIS_HOST   기본값 "redis"
    REDIS_PORT   기본값 6379
    BM25_K1      기본값 1.5
    BM25_B       기본값 0.75
"""

import logging
import os

import redis
from rank_bm25 import BM25Okapi
from soynlp.tokenizer import LTokenizer
from soynlp.word import WordExtractor

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
BM25_K1 = float(os.getenv("BM25_K1", "1.5"))
BM25_B = float(os.getenv("BM25_B", "0.75"))

_DOCS_KEY = "bm25:docs"
_IDS_KEY = "bm25:ids"

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        logger.info("BM25 Redis 연결: %s:%s", REDIS_HOST, REDIS_PORT)
    return _redis


# ── 토크나이저 ────────────────────────────────────────────────────────────────


def _build_tokenizer(texts: list[str]) -> LTokenizer:
    """
    문서 집합으로부터 단어 점수를 학습해 soynlp LTokenizer를 생성한다.
    """
    extractor = WordExtractor(
        min_frequency=1,
        min_cohesion_forward=0.0,
        min_right_branching_entropy=0.0,
    )
    extractor.train(texts)
    words = extractor.extract()
    scores = {
        word: max(score.cohesion_forward, 0.0)
        for word, score in words.items()
        if len(word) >= 2
    }
    return LTokenizer(scores=scores)


def _tokenize(text: str, tokenizer: LTokenizer) -> list[str]:
    """soynlp 토크나이저로 한국어 텍스트를 토큰화한다."""
    tokens = tokenizer.tokenize(text)
    return [token for token in tokens if len(token) >= 2]


# ── Redis 문서 관리 ───────────────────────────────────────────────────────────


def _load_docs() -> tuple[list[int], list[str]]:
    r = _get_redis()
    raw_ids = r.lrange(_IDS_KEY, 0, -1)
    if not raw_ids:
        return [], []
    ids = [int(i) for i in raw_ids]
    texts = [r.hget(_DOCS_KEY, pid) or "" for pid in raw_ids]
    return ids, texts


def _save_doc(precedent_id: int, text: str) -> None:
    r = _get_redis()
    pid = str(precedent_id)
    if not r.hexists(_DOCS_KEY, pid):
        r.rpush(_IDS_KEY, pid)
    r.hset(_DOCS_KEY, pid, text)


def _delete_doc(precedent_id: int) -> None:
    r = _get_redis()
    pid = str(precedent_id)
    r.hdel(_DOCS_KEY, pid)
    r.lrem(_IDS_KEY, 1, pid)


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────


def upsert(precedent_id: int, text: str) -> None:
    """판례 원문을 Redis에 저장한다."""
    _save_doc(precedent_id, text)
    logger.info("BM25 upsert 완료: precedent_id=%s", precedent_id)


def delete(precedent_id: int) -> None:
    """판례 원문을 Redis에서 삭제한다."""
    _delete_doc(precedent_id)
    logger.info("BM25 delete 완료: precedent_id=%s", precedent_id)


def search(query: str, top_k: int = 5) -> list[dict]:
    """
    BM25 키워드 검색.
    soynlp 토크나이저로 한국어 단어 경계를 분리해 매칭 정확도를 높인다.

    Returns:
        [{"precedent_id": int, "score": float}, ...]
    """
    ids, texts = _load_docs()
    if not ids:
        return []

    tokenizer = _build_tokenizer(texts)
    tokenized_corpus = [_tokenize(t, tokenizer) for t in texts]
    bm25 = BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)
    scores = bm25.get_scores(_tokenize(query, tokenizer))

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        {"precedent_id": ids[i], "score": float(score)}
        for i, score in indexed
        if score > 0
    ]


def count() -> int:
    """Redis에 저장된 BM25 문서 수를 반환한다."""
    return _get_redis().llen(_IDS_KEY)
