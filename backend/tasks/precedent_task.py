"""
tasks/precedent_task.py

판례 임베딩 Celery task.
판례 등록/재처리 성공 후 백그라운드에서 벡터화 → Qdrant + BM25 저장.
"""

import logging

from celery_app import celery_app
from database import SessionLocal
from models.model import DocumentStatus, Precedent
from services.precedent import OptionalPrecedentMetadataParser
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_passage

logger = logging.getLogger(__name__)
_metadata_parser = OptionalPrecedentMetadataParser()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.precedent_task.index_precedent",
)
def index_precedent(self, precedent_id: int) -> dict:
    """
    판례 텍스트를 임베딩해서 Qdrant + BM25 인덱스에 저장한다.

    Args:
        precedent_id: Precedent.id

    Returns:
        {"status": "ok" | "skip", ...}
    """
    db = SessionLocal()
    try:
        precedent = db.query(Precedent).filter(Precedent.id == precedent_id).first()
        if not precedent:
            logger.warning("index_precedent: precedent_id=%s 없음", precedent_id)
            return {"status": "skip", "reason": "not found"}

        if precedent.processing_status != DocumentStatus.DONE:
            logger.warning(
                "index_precedent: precedent_id=%s status=%s, 스킵",
                precedent_id,
                precedent.processing_status,
            )
            return {"status": "skip", "reason": "not DONE"}

        if not precedent.text:
            logger.warning("index_precedent: precedent_id=%s text 없음", precedent_id)
            return {"status": "skip", "reason": "empty text"}

        # Dense 임베딩 → Qdrant
        logger.info("임베딩 시작: precedent_id=%s", precedent_id)
        vector = embed_passage(precedent.text)
        metadata = _metadata_parser.parse_text(precedent.text)
        vector_store.upsert(
            precedent_id=precedent.id,
            embedding=vector,
            payload={
                "title": precedent.title or "",
                "source_url": precedent.source_url or "",
                "text": precedent.text,
                **{k: v for k, v in metadata.items() if v},
            },
        )

        # BM25 인덱스 → Redis
        bm25_store.upsert(
            precedent_id=precedent.id,
            text=precedent.text,
        )

        logger.info("임베딩 완료: precedent_id=%s", precedent_id)
        return {"status": "ok", "precedent_id": precedent_id}

    except Exception as exc:
        logger.error("임베딩 실패: precedent_id=%s, error=%s", precedent_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="tasks.precedent_task.delete_precedent_index")
def delete_precedent_index(precedent_id: int) -> dict:
    """Qdrant + BM25 인덱스에서 판례 벡터를 삭제한다."""
    try:
        vector_store.delete(precedent_id)
        bm25_store.delete(precedent_id)
        return {"status": "ok", "precedent_id": precedent_id}
    except Exception as exc:
        logger.error("인덱스 삭제 실패: precedent_id=%s, error=%s", precedent_id, exc)
        return {"status": "error", "reason": str(exc)}
