"""
Redis-backed BM25 store for workspace and platform chunk search.

Workspace corpus and platform corpus are physically separated by key namespace.
The store keeps reverse indexes by document/group so delete and scoped search can
run without rebuilding the full corpus on every request.
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

# Workspace corpus keys.
_D_DOCS_KEY = "bm25:d:docs"
_D_IDS_KEY = "bm25:d:ids"
_D_REV_KEY = "bm25:d:rev"
_DID_KEY_PREFIX = "bm25:did:"
_DID_GROUP_KEY = "bm25:d:group_ids"
_GID_KEY_PREFIX = "bm25:gid:"

# Platform corpus keys.
_PL_DOCS_KEY = "bm25:pl:docs"
_PL_IDS_KEY = "bm25:pl:ids"
_PL_REV_KEY = "bm25:pl:rev"
_PLID_KEY_PREFIX = "bm25:plid:"

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        logger.info("BM25 Redis 연결: %s:%s", REDIS_HOST, REDIS_PORT)
    return _redis


@dataclass
class _BM25Snapshot:
    """현재 revision에 대응하는 BM25 snapshot."""

    revision: int = -1
    chunk_ids: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    tokenizer: LTokenizer | None = None
    tokenized_corpus: list[list[str]] = field(default_factory=list)
    bm25: BM25Okapi | None = None


# Workspace/platform corpus는 revision과 rebuild lock을 따로 유지한다.
_d_cache = _BM25Snapshot()
_pl_cache = _BM25Snapshot()
_d_lock = threading.Lock()
_pl_lock = threading.Lock()


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


def _rebuild_snapshot(
    cache: _BM25Snapshot,
    lock: threading.Lock,
    docs_key: str,
    ids_key: str,
    rev_key: str,
) -> _BM25Snapshot:
    """revision이 바뀐 경우에만 snapshot을 재구성한다."""
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


def _get_d_cache() -> _BM25Snapshot:
    if _d_cache.revision != _current_revision(_D_REV_KEY):
        _rebuild_snapshot(_d_cache, _d_lock, _D_DOCS_KEY, _D_IDS_KEY, _D_REV_KEY)
    return _d_cache


def _get_pl_cache() -> _BM25Snapshot:
    if _pl_cache.revision != _current_revision(_PL_REV_KEY):
        _rebuild_snapshot(_pl_cache, _pl_lock, _PL_DOCS_KEY, _PL_IDS_KEY, _PL_REV_KEY)
    return _pl_cache


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
    """BM25 score가 모두 0일 때 allowed_ids 범위에서만 lexical fallback을 수행한다."""
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


def upsert_document_chunk(
    chunk_id: str, document_id: int, group_id: int, text: str
) -> None:
    """그룹 문서 chunk를 저장하고 revision을 INCR한다."""
    r = _get_redis()
    r.hset(_DID_GROUP_KEY, str(document_id), group_id)
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
    group_id = r.hget(_DID_GROUP_KEY, str(document_id))
    for chunk_id in chunk_ids:
        r.hdel(_D_DOCS_KEY, chunk_id)
        r.lrem(_D_IDS_KEY, 1, chunk_id)
        if group_id is not None:
            r.srem(f"{_GID_KEY_PREFIX}{group_id}", chunk_id)
    r.delete(f"{_DID_KEY_PREFIX}{document_id}")
    r.hdel(_DID_GROUP_KEY, str(document_id))
    r.incr(_D_REV_KEY)
    logger.info(
        "BM25 delete (그룹문서) 완료: document_id=%s (%d chunks)",
        document_id,
        len(chunk_ids),
    )


def get_document_chunk_ids(document_id: int) -> set[str]:
    """document_id에 속한 현재 BM25 chunk_id 집합을 반환한다."""
    r = _get_redis()
    return set(r.smembers(f"{_DID_KEY_PREFIX}{document_id}"))


def delete_document_chunks(
    document_id: int, group_id: int, chunk_ids: set[str]
) -> None:
    """document_id/group_id 범위에서 지정한 stale chunk_id만 삭제한다."""
    if not chunk_ids:
        return

    r = _get_redis()
    did_key = f"{_DID_KEY_PREFIX}{document_id}"
    gid_key = f"{_GID_KEY_PREFIX}{group_id}"

    for chunk_id in chunk_ids:
        r.hdel(_D_DOCS_KEY, chunk_id)
        r.lrem(_D_IDS_KEY, 1, chunk_id)
        r.srem(did_key, chunk_id)
        r.srem(gid_key, chunk_id)

    if r.scard(did_key) == 0:
        r.delete(did_key)
        r.hdel(_DID_GROUP_KEY, str(document_id))
    r.incr(_D_REV_KEY)
    logger.info(
        "BM25 stale chunk delete 완료: document_id=%s, group_id=%s (%d chunks)",
        document_id,
        group_id,
        len(chunk_ids),
    )


def search_documents(
    query: str,
    group_id: int,
    top_k: int = 5,
    document_ids: list[int] | None = None,
) -> list[dict]:
    """
    그룹 문서 corpus BM25 검색.

    document_ids 가 None 이면 group_id 전체 범위 검색 (mode="all").
    document_ids 가 있으면 group_id ∩ document_ids whitelist 범위만 검색 (mode="documents").

    fail-closed:
        document_ids=[] 같은 빈 리스트는 parser 단계에서 이미 막혀 있으므로
        이 함수에 도달할 때는 None 또는 non-empty list 중 하나다.
        그러나 방어적으로 빈 리스트가 오면 빈 결과를 반환한다.
    """
    r = _get_redis()

    # group_id 범위 집합
    group_allowed = r.smembers(f"{_GID_KEY_PREFIX}{group_id}")
    if not group_allowed:
        return []

    if document_ids is not None:
        if not document_ids:
            logger.warning(
                "[bm25_store] search_documents: document_ids 빈 리스트 → 빈 결과 반환"
            )
            return []

        doc_keys = [f"{_DID_KEY_PREFIX}{did}" for did in document_ids]
        doc_allowed = r.sunion(*doc_keys)  # type: ignore[arg-type]
        allowed_ids = group_allowed & doc_allowed
    else:
        allowed_ids = group_allowed

    if not allowed_ids:
        return []

    cache = _get_d_cache()
    hits = _bm25_search_from_cache(query, cache, top_k, allowed_ids=allowed_ids)
    if hits:
        return hits

    logger.debug(
        "BM25 결과 없음 (small-group), lexical fallback 실행: group_id=%s document_ids=%s",
        group_id,
        document_ids,
    )
    return _fallback_lexical_search(query, _D_DOCS_KEY, allowed_ids, top_k)


def upsert_platform_chunk(chunk_id: str, platform_document_id: str, text: str) -> None:
    """Platform chunk를 저장하고 revision을 증가시킨다."""
    _save_chunk(
        _PL_DOCS_KEY,
        _PL_IDS_KEY,
        _PL_REV_KEY,
        [f"{_PLID_KEY_PREFIX}{platform_document_id}"],
        chunk_id,
        text,
    )
    logger.debug("BM25 upsert (platform) 완료: chunk_id=%s", chunk_id)


def delete_platform_document(platform_document_id: str) -> None:
    """platform_document_id에 속한 모든 chunk를 삭제하고 revision을 INCR한다."""
    deleted = _delete_by_index_key(
        _PL_DOCS_KEY,
        _PL_IDS_KEY,
        _PL_REV_KEY,
        f"{_PLID_KEY_PREFIX}{platform_document_id}",
    )
    logger.info(
        "BM25 delete (platform) 완료: platform_document_id=%s (%d chunks)",
        platform_document_id,
        deleted,
    )


def search_platform(query: str, top_k: int = 5) -> list[dict]:
    """Platform corpus를 BM25로 검색한다."""
    cache = _get_pl_cache()
    return _bm25_search_from_cache(query, cache, top_k)


def platform_corpus_exists() -> bool:
    """platform corpus가 비어있지 않은지 확인한다. (PlatformRetriever 조기 반환용)"""
    try:
        r = _get_redis()
        return bool(r.exists(_PL_IDS_KEY))
    except Exception:
        return False


def count() -> int:
    r = _get_redis()
    return r.llen(_D_IDS_KEY) + r.llen(_PL_IDS_KEY)


def clear() -> None:
    r = _get_redis()
    for key in [
        _D_DOCS_KEY,
        _D_IDS_KEY,
        _D_REV_KEY,
        _DID_GROUP_KEY,
        _PL_DOCS_KEY,
        _PL_IDS_KEY,
        _PL_REV_KEY,
    ]:
        r.delete(key)
    for prefix in (_DID_KEY_PREFIX, _GID_KEY_PREFIX, _PLID_KEY_PREFIX):
        for key in r.scan_iter(f"{prefix}*"):
            r.delete(key)
    for cache in (_d_cache, _pl_cache):
        cache.revision = -1
        cache.chunk_ids = []
        cache.texts = []
        cache.tokenizer = None
        cache.tokenized_corpus = []
        cache.bm25 = None
    logger.info("BM25 Redis 데이터 전체 삭제 완료")
