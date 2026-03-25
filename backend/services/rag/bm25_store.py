"""
services/rag/bm25_store.py

BM25 키워드 검색 레이어. chunk 단위 저장.

판례(precedent_id)와 그룹 문서(document_id) 두 경로를 모두 지원한다.
키 네임스페이스로 corpus를 물리적으로 분리한다.

Redis 키 구조:
    판례 corpus:
        "bm25:p:docs"      → Hash  {chunk_id: text}
        "bm25:p:ids"       → List  [chunk_id, ...]
        "bm25:p:rev"       → Int   revision 카운터 (변경 시 INCR)
        "bm25:pid:{pid}"   → Set   {chunk_id, ...}  (precedent_id별 역인덱스)

    그룹 문서 corpus:
        "bm25:d:docs"      → Hash  {chunk_id: text}
        "bm25:d:ids"       → List  [chunk_id, ...]
        "bm25:d:rev"       → Int   revision 카운터 (변경 시 INCR)
        "bm25:did:{did}"   → Set   {chunk_id, ...}  (document_id별 역인덱스)

    그룹 문서 검색 시 group_id 범위 제한:
        "bm25:gid:{gid}"   → Set   {chunk_id, ...}  (group_id별 역인덱스)

환경 변수:
    REDIS_HOST   기본값 "redis"
    REDIS_PORT   기본값 6379
    BM25_K1      기본값 1.5
    BM25_B       기본값 0.75
"""

import logging
import os
import threading
from dataclasses import dataclass, field

import redis
from rank_bm25 import BM25Okapi
from soynlp.tokenizer import LTokenizer
from soynlp.word import WordExtractor

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
BM25_K1 = float(os.getenv("BM25_K1", "1.5"))
BM25_B = float(os.getenv("BM25_B", "0.75"))

# 판례 corpus 키
_P_DOCS_KEY = "bm25:p:docs"
_P_IDS_KEY = "bm25:p:ids"
_P_REV_KEY = "bm25:p:rev"
_PID_KEY_PREFIX = "bm25:pid:"

# 그룹 문서 corpus 키
_D_DOCS_KEY = "bm25:d:docs"
_D_IDS_KEY = "bm25:d:ids"
_D_REV_KEY = "bm25:d:rev"
_DID_KEY_PREFIX = "bm25:did:"
_GID_KEY_PREFIX = "bm25:gid:"

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        logger.info("BM25 Redis 연결: %s:%s", REDIS_HOST, REDIS_PORT)
    return _redis


# ── 캐시 구조 ─────────────────────────────────────────────────────────────────


@dataclass
class _BM25Snapshot:
    """프로세스 메모리에 유지되는 BM25 snapshot 캐시."""

    revision: int = -1
    chunk_ids: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    tokenizer: LTokenizer | None = None
    tokenized_corpus: list[list[str]] = field(default_factory=list)
    bm25: BM25Okapi | None = None


# 판례·문서 캐시 및 rebuild lock 분리
_p_cache = _BM25Snapshot()
_d_cache = _BM25Snapshot()
_p_lock = threading.Lock()
_d_lock = threading.Lock()


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
    return [t for t in tokenizer.tokenize(text) if len(t) >= 2]


# ── 내부 저장 헬퍼 ────────────────────────────────────────────────────────────


def _save_chunk(
    docs_key: str,
    ids_key: str,
    rev_key: str,
    index_keys: list[str],
    chunk_id: str,
    text: str,
) -> None:
    r = _get_redis()
    if not r.hexists(docs_key, chunk_id):
        r.rpush(ids_key, chunk_id)
    r.hset(docs_key, chunk_id, text)
    for key in index_keys:
        r.sadd(key, chunk_id)
    r.incr(rev_key)


def _delete_by_index_key(
    docs_key: str, ids_key: str, rev_key: str, index_key: str
) -> int:
    r = _get_redis()
    chunk_ids = r.smembers(index_key)
    for chunk_id in chunk_ids:
        r.hdel(docs_key, chunk_id)
        r.lrem(ids_key, 1, chunk_id)
    r.delete(index_key)
    r.incr(rev_key)
    return len(chunk_ids)


def _load_corpus(
    docs_key: str, ids_key: str, allowed_ids: set[str] | None = None
) -> tuple[list[str], list[str]]:
    r = _get_redis()
    chunk_ids = r.lrange(ids_key, 0, -1)
    if not chunk_ids:
        return [], []
    if allowed_ids is not None:
        chunk_ids = [cid for cid in chunk_ids if cid in allowed_ids]
    texts = [r.hget(docs_key, cid) or "" for cid in chunk_ids]
    return chunk_ids, texts


def _current_revision(rev_key: str) -> int:
    r = _get_redis()
    val = r.get(rev_key)
    return int(val) if val is not None else 0


# ── 캐시 rebuild ──────────────────────────────────────────────────────────────


def _rebuild_snapshot(
    cache: _BM25Snapshot,
    lock: threading.Lock,
    docs_key: str,
    ids_key: str,
    rev_key: str,
) -> _BM25Snapshot:
    """
    revision이 다를 때만 rebuild한다.
    lock으로 동시 rebuild를 방지하고, double-check로 중복 rebuild를 차단한다.
    """
    current_rev = _current_revision(rev_key)
    if cache.revision == current_rev:
        return cache

    with lock:
        current_rev = _current_revision(rev_key)
        if cache.revision == current_rev:
            return cache

        logger.info(
            "BM25 캐시 rebuild: rev=%s → %s (%s)", cache.revision, current_rev, rev_key
        )
        chunk_ids, texts = _load_corpus(docs_key, ids_key)

        if not chunk_ids:
            cache.revision = current_rev
            cache.chunk_ids = []
            cache.texts = []
            cache.tokenizer = None
            cache.tokenized_corpus = []
            cache.bm25 = None
            return cache

        tokenizer = _build_tokenizer(texts)
        tokenized_corpus = [_tokenize(t, tokenizer) for t in texts]
        bm25 = BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)

        cache.revision = current_rev
        cache.chunk_ids = chunk_ids
        cache.texts = texts
        cache.tokenizer = tokenizer
        cache.tokenized_corpus = tokenized_corpus
        cache.bm25 = bm25

    return cache


def _get_p_cache() -> _BM25Snapshot:
    if _p_cache.revision != _current_revision(_P_REV_KEY):
        _rebuild_snapshot(_p_cache, _p_lock, _P_DOCS_KEY, _P_IDS_KEY, _P_REV_KEY)
    return _p_cache


def _get_d_cache() -> _BM25Snapshot:
    if _d_cache.revision != _current_revision(_D_REV_KEY):
        _rebuild_snapshot(_d_cache, _d_lock, _D_DOCS_KEY, _D_IDS_KEY, _D_REV_KEY)
    return _d_cache


# ── 검색 코어 ─────────────────────────────────────────────────────────────────


def _bm25_search_from_cache(
    query: str,
    cache: _BM25Snapshot,
    top_k: int,
    allowed_ids: set[str] | None = None,
) -> list[dict]:
    if cache.bm25 is None or not cache.chunk_ids:
        return []

    tokenizer = cache.tokenizer
    chunk_ids = cache.chunk_ids
    bm25 = cache.bm25

    if allowed_ids is not None:
        indices = [i for i, cid in enumerate(chunk_ids) if cid in allowed_ids]
        if not indices:
            return []
        filtered_corpus = [cache.tokenized_corpus[i] for i in indices]
        filtered_ids = [chunk_ids[i] for i in indices]
        bm25_filtered = BM25Okapi(filtered_corpus, k1=BM25_K1, b=BM25_B)
        scores = bm25_filtered.get_scores(_tokenize(query, tokenizer))
        chunk_ids_to_score = filtered_ids
    else:
        scores = bm25.get_scores(_tokenize(query, tokenizer))
        chunk_ids_to_score = chunk_ids

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {"chunk_id": chunk_ids_to_score[i], "score": float(score)}
        for i, score in indexed
        if score > 0
    ]


def _fallback_lexical_search(
    query: str,
    docs_key: str,
    allowed_ids: set[str],
    top_k: int,
) -> list[dict]:
    """
    BM25 score가 전부 0인 small-group 상황을 위한 lexical fallback.
    allowed_ids 범위 내에서만 동작해 corpus isolation을 유지한다.
    """
    r = _get_redis()
    query_lower = query.lower()
    query_tokens = [t for t in query_lower.split() if len(t) >= 2]

    results: list[dict] = []
    for chunk_id in allowed_ids:
        text = r.hget(docs_key, chunk_id) or ""
        text_lower = text.lower()
        if not query_tokens:
            score = 0.1
        else:
            matched = sum(1 for t in query_tokens if t in text_lower)
            if matched == 0:
                continue
            score = matched / len(query_tokens)
        results.append({"chunk_id": chunk_id, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ── 공개 인터페이스 (판례) ────────────────────────────────────────────────────


def upsert(chunk_id: str, precedent_id: int, text: str) -> None:
    """판례 chunk를 Redis 판례 corpus에 저장하고 revision을 INCR한다."""
    _save_chunk(
        _P_DOCS_KEY,
        _P_IDS_KEY,
        _P_REV_KEY,
        [f"{_PID_KEY_PREFIX}{precedent_id}"],
        chunk_id,
        text,
    )
    logger.debug("BM25 upsert (판례) 완료: chunk_id=%s", chunk_id)


def delete(precedent_id: int) -> None:
    """precedent_id에 속한 모든 chunk를 삭제하고 revision을 INCR한다."""
    count = _delete_by_index_key(
        _P_DOCS_KEY, _P_IDS_KEY, _P_REV_KEY, f"{_PID_KEY_PREFIX}{precedent_id}"
    )
    logger.info(
        "BM25 delete (판례) 완료: precedent_id=%s (%d chunks)", precedent_id, count
    )


def search(query: str, top_k: int = 5) -> list[dict]:
    """판례 corpus BM25 검색. 캐시 revision 확인 후 필요 시만 rebuild한다."""
    cache = _get_p_cache()
    return _bm25_search_from_cache(query, cache, top_k)


# ── 공개 인터페이스 (그룹 문서) ───────────────────────────────────────────────


def upsert_document_chunk(
    chunk_id: str, document_id: int, group_id: int, text: str
) -> None:
    """그룹 문서 chunk를 저장하고 revision을 INCR한다."""
    _save_chunk(
        _D_DOCS_KEY,
        _D_IDS_KEY,
        _D_REV_KEY,
        [f"{_DID_KEY_PREFIX}{document_id}", f"{_GID_KEY_PREFIX}{group_id}"],
        chunk_id,
        text,
    )
    logger.debug("BM25 upsert (그룹문서) 완료: chunk_id=%s", chunk_id)


def delete_document(document_id: int) -> None:
    """document_id에 속한 모든 chunk를 삭제하고 revision을 INCR한다."""
    r = _get_redis()
    chunk_ids = r.smembers(f"{_DID_KEY_PREFIX}{document_id}")
    for chunk_id in chunk_ids:
        r.hdel(_D_DOCS_KEY, chunk_id)
        r.lrem(_D_IDS_KEY, 1, chunk_id)
        for key in r.scan_iter(f"{_GID_KEY_PREFIX}*"):
            r.srem(key, chunk_id)
    r.delete(f"{_DID_KEY_PREFIX}{document_id}")
    r.incr(_D_REV_KEY)
    logger.info(
        "BM25 delete (그룹문서) 완료: document_id=%s (%d chunks)",
        document_id,
        len(chunk_ids),
    )


def search_documents(query: str, group_id: int, top_k: int = 5) -> list[dict]:
    """
    그룹 문서 corpus BM25 검색. 캐시 재사용 + group_id 범위 필터링.
    small-group fallback 포함.
    """
    r = _get_redis()
    allowed_ids = r.smembers(f"{_GID_KEY_PREFIX}{group_id}")
    if not allowed_ids:
        return []

    cache = _get_d_cache()
    hits = _bm25_search_from_cache(query, cache, top_k, allowed_ids=allowed_ids)
    if hits:
        return hits

    logger.debug(
        "BM25 결과 없음 (small-group), lexical fallback 실행: group_id=%s", group_id
    )
    return _fallback_lexical_search(query, _D_DOCS_KEY, allowed_ids, top_k)


# ── 유틸리티 ─────────────────────────────────────────────────────────────────


def count() -> int:
    r = _get_redis()
    return r.llen(_P_IDS_KEY) + r.llen(_D_IDS_KEY)


def clear() -> None:
    r = _get_redis()
    for key in [
        _P_DOCS_KEY,
        _P_IDS_KEY,
        _P_REV_KEY,
        _D_DOCS_KEY,
        _D_IDS_KEY,
        _D_REV_KEY,
    ]:
        r.delete(key)
    for prefix in (_PID_KEY_PREFIX, _DID_KEY_PREFIX, _GID_KEY_PREFIX):
        for key in r.scan_iter(f"{prefix}*"):
            r.delete(key)
    for cache in (_p_cache, _d_cache):
        cache.revision = -1
        cache.chunk_ids = []
        cache.texts = []
        cache.tokenizer = None
        cache.tokenized_corpus = []
        cache.bm25 = None
    logger.info("BM25 Redis 데이터 전체 삭제 완료")
