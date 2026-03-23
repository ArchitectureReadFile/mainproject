"""
tasks/precedent_task.py

판례 임베딩 Celery task.
판례 등록/재처리 성공 후 백그라운드에서 벡터화 → Qdrant + BM25 저장.
"""

import logging

from celery_app import celery_app
from database import SessionLocal
from extractors.taxlaw_precedent import fetch_taxlaw_precedent
from models.model import DocumentStatus, Precedent
from services.precedent.metadata_parser import OptionalPrecedentMetadataParser
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_passage

logger = logging.getLogger(__name__)
_metadata_parser = OptionalPrecedentMetadataParser()


def _resolve_precedent_title(raw_title: str | None, parsed_meta: dict) -> str | None:
    if raw_title and str(raw_title).strip():
        return str(raw_title).strip()

    case_number = parsed_meta.get("case_number")
    case_name = parsed_meta.get("case_name")
    court_name = parsed_meta.get("court_name")

    if case_number and case_name:
        return f"{case_number} {case_name}"
    if court_name and case_number:
        return f"{court_name} {case_number}"
    if case_name:
        return case_name
    if case_number:
        return case_number
    return raw_title


def _drop_stale_index(precedent_id: int) -> None:
    try:
        vector_store.delete(precedent_id)
        bm25_store.delete(precedent_id)
        logger.info("stale 인덱스 제거: precedent_id=%s", precedent_id)
    except Exception as exc:
        logger.error(
            "stale 인덱스 제거 실패: precedent_id=%s, error=%s", precedent_id, exc
        )


@celery_app.task(
    bind=True,
    name="tasks.precedent_task.process_next_pending_precedent",
)
def process_next_pending_precedent(self) -> dict:
    db = SessionLocal()
    claimed_precedent_id = None
    try:
        precedent = (
            db.query(Precedent)
            .filter(Precedent.processing_status == DocumentStatus.PENDING)
            .order_by(Precedent.created_at.asc(), Precedent.id.asc())
            .first()
        )
        if not precedent:
            logger.info("[precedent 태스크 종료] 처리할 PENDING 판례가 없습니다.")
            return {"status": "idle"}

        precedent.processing_status = DocumentStatus.PROCESSING
        db.commit()
        db.refresh(precedent)
        claimed_precedent_id = precedent.id

        try:
            result = fetch_taxlaw_precedent(precedent.source_url)
            precedent.title = result.get("title") or None
            precedent.text = result.get("text") or None

            if not precedent.text:
                precedent.processing_status = DocumentStatus.FAILED
                precedent.error_message = "본문 텍스트를 추출할 수 없습니다."
                _drop_stale_index(precedent.id)
            else:
                parsed_meta = _metadata_parser.parse_text(precedent.text)
                precedent.title = _resolve_precedent_title(precedent.title, parsed_meta)
                precedent.processing_status = DocumentStatus.DONE
                precedent.error_message = None
        except Exception as exc:
            logger.error("판례 추출 실패: id=%s, error=%s", precedent.id, exc)
            precedent.processing_status = DocumentStatus.FAILED
            precedent.error_message = str(exc)
            _drop_stale_index(precedent.id)

        db.commit()
        db.refresh(precedent)

        if precedent.processing_status == DocumentStatus.DONE:
            index_precedent.delay(precedent.id)

        return {
            "status": precedent.processing_status.value.lower(),
            "precedent_id": precedent.id,
        }
    finally:
        db.close()
        if claimed_precedent_id is not None:
            process_next_pending_precedent.delay()


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
