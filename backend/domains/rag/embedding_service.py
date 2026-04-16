"""
domains/rag/embedding_service.py

임베딩 인터페이스 레이어.
모델은 환경 변수로 교체 가능하다.

환경 변수:
    EMBEDDING_MODEL      기본값 "intfloat/multilingual-e5-base"
    EMBEDDING_CACHE_DIR  기본값 "runtime/cache"
    EMBEDDING_PREFIX     기본값 "e5"  →  e5 | none
                         e5   : embed_query/embed_passage에 query:/passage: prefix 자동 추가
                         none : prefix 없이 텍스트 그대로 임베딩 (KURE-v1, ko-sroberta 등)

교체 예시:
    # E5 계열
    EMBEDDING_MODEL=intfloat/multilingual-e5-base
    EMBEDDING_PREFIX=e5

    # 비-E5 계열
    EMBEDDING_MODEL=nlpai-lab/KURE-v1
    EMBEDDING_PREFIX=none

    EMBEDDING_MODEL=jhgan/ko-sroberta-multitask
    EMBEDDING_PREFIX=none
"""

import logging
import os

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
EMBEDDING_CACHE_DIR = os.getenv("EMBEDDING_CACHE_DIR", "runtime/cache")
EMBEDDING_PREFIX = os.getenv("EMBEDDING_PREFIX", "e5").lower()  # "e5" | "none"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(
            "임베딩 모델 로드 중: %s (prefix=%s)", EMBEDDING_MODEL, EMBEDDING_PREFIX
        )
        _model = SentenceTransformer(
            EMBEDDING_MODEL,
            cache_folder=EMBEDDING_CACHE_DIR,
        )
        logger.info("임베딩 모델 로드 완료: %s", EMBEDDING_MODEL)
    return _model


def _apply_prefix(text: str, prefix: str) -> str:
    """EMBEDDING_PREFIX 설정에 따라 prefix를 붙이거나 그대로 반환한다."""
    if EMBEDDING_PREFIX == "e5":
        return f"{prefix}: {text}"
    return text


def embed(text: str) -> list[float]:
    """텍스트를 벡터로 변환한다. prefix 없이 그대로 임베딩."""
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_passage(text: str) -> list[float]:
    """
    문서 저장용 임베딩.
    EMBEDDING_PREFIX=e5  → 'passage: {text}'
    EMBEDDING_PREFIX=none → text 그대로
    """
    return embed(_apply_prefix(text, "passage"))


def embed_query(text: str) -> list[float]:
    """
    검색 질문용 임베딩.
    EMBEDDING_PREFIX=e5  → 'query: {text}'
    EMBEDDING_PREFIX=none → text 그대로
    """
    return embed(_apply_prefix(text, "query"))


def embed_batch(texts: list[str]) -> list[list[float]]:
    """여러 텍스트를 한 번에 벡터로 변환한다. prefix 없이 그대로."""
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]


def embed_passages(texts: list[str]) -> list[list[float]]:
    """문서 저장용 배치 임베딩."""
    return embed_batch([_apply_prefix(t, "passage") for t in texts])
