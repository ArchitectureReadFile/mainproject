"""
services/rag/bm25_store.py

BM25 키워드 검색 레이어. chunk 단위 저장.

Redis 키 구조:
    "bm25:docs"      → Hash  {chunk_id: text}
    "bm25:ids"       → List  [chunk_id, ...]
    "bm25:pid:{pid}" → Set   {chunk_id, ...}  (precedent_id별 역인덱스)

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
_PID_KEY_PREFIX = "bm25:pid:"

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        logger.info("BM25 Redis 연결: %s:%s", REDIS_HOST, REDIS_PORT)
    return _redis


def _pid_key(precedent_id: int) -> str:
    return f"{_PID_KEY_PREFIX}{precedent_id}"


# ── 토크나이저 ────────────────────────────────────────────────────────────────


def _build_tokenizer(texts: list[str]) -> LTokenizer:
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
    tokens = tokenizer.tokenize(text)
    return [token for token in tokens if len(token) >= 2]


# ── Redis 문서 관리 ───────────────────────────────────────────────────────────


def _load_docs() -> tuple[list[str], list[str]]:
    """(chunk_id 리스트, text 리스트) 반환."""
    r = _get_redis()
    chunk_ids = r.lrange(_IDS_KEY, 0, -1)
    if not chunk_ids:
        return [], []
    texts = [r.hget(_DOCS_KEY, cid) or "" for cid in chunk_ids]
    return chunk_ids, texts


def _save_chunk(chunk_id: str, precedent_id: int, text: str) -> None:
    r = _get_redis()
    if not r.hexists(_DOCS_KEY, chunk_id):
        r.rpush(_IDS_KEY, chunk_id)
    r.hset(_DOCS_KEY, chunk_id, text)
    r.sadd(_pid_key(precedent_id), chunk_id)


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────


def upsert(chunk_id: str, precedent_id: int, text: str) -> None:
    """chunk를 Redis에 저장한다."""
    _save_chunk(chunk_id, precedent_id, text)
    logger.debug("BM25 upsert 완료: chunk_id=%s", chunk_id)


def delete(precedent_id: int) -> None:
    """precedent_id에 속한 모든 chunk를 Redis에서 삭제한다."""
    r = _get_redis()
    chunk_ids = r.smembers(_pid_key(precedent_id))
    for chunk_id in chunk_ids:
        r.hdel(_DOCS_KEY, chunk_id)
        r.lrem(_IDS_KEY, 1, chunk_id)
    r.delete(_pid_key(precedent_id))
    logger.info(
        "BM25 delete 완료: precedent_id=%s (%d chunks)", precedent_id, len(chunk_ids)
    )


def search(query: str, top_k: int = 5) -> list[dict]:
    """
    BM25 키워드 검색. chunk 단위 hit 반환.

    Returns:
        [{"chunk_id": str, "score": float}, ...]
    """
    chunk_ids, texts = _load_docs()
    if not chunk_ids:
        return []

    tokenizer = _build_tokenizer(texts)
    tokenized_corpus = [_tokenize(t, tokenizer) for t in texts]
    bm25 = BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)
    scores = bm25.get_scores(_tokenize(query, tokenizer))

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        {"chunk_id": chunk_ids[i], "score": float(score)}
        for i, score in indexed
        if score > 0
    ]


def count() -> int:
    return _get_redis().llen(_IDS_KEY)


def clear() -> None:
    r = _get_redis()
    r.delete(_DOCS_KEY)
    r.delete(_IDS_KEY)
    for key in r.scan_iter(f"{_PID_KEY_PREFIX}*"):
        r.delete(key)
    logger.info("BM25 Redis 데이터 삭제 완료")
