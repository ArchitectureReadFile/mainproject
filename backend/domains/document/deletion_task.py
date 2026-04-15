import logging

from celery_app import celery_app
from database import SessionLocal
from domains.document.file_cleanup_task import enqueue_document_file_cleanup
from models.model import (
    Document,
    DocumentLifecycleStatus,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


def _get_due_documents(*, db, now) -> list[Document]:
    """휴지통 유예가 끝난 문서를 조회한다."""
    return (
        db.query(Document)
        .filter(
            Document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING,
            Document.delete_scheduled_at.isnot(None),
            Document.delete_scheduled_at <= now,
        )
        .all()
    )


@celery_app.task(name="tasks.document_deletion_task.finalize_pending_documents")
def finalize_pending_documents():
    """휴지통 유예가 끝난 문서를 최종 삭제 상태로 전환한다."""
    db = SessionLocal()
    try:
        now = utc_now_naive()
        documents = _get_due_documents(db=db, now=now)

        finalized_document_count = 0
        deleted_document_ids: list[int] = []

        for document in documents:
            document.lifecycle_status = DocumentLifecycleStatus.DELETED
            document.deleted_at = now
            finalized_document_count += 1
            deleted_document_ids.append(document.id)

        if finalized_document_count > 0:
            db.commit()

        enqueued_document_ids: list[int] = []
        if deleted_document_ids:
            enqueued_document_ids = enqueue_document_file_cleanup(deleted_document_ids)

        logger.info(
            "[document finalize] finalized_documents=%s file_cleanup_enqueued=%s",
            finalized_document_count,
            len(enqueued_document_ids),
        )

        return {
            "finalized_document_count": finalized_document_count,
            "deleted_document_ids": deleted_document_ids,
            "file_cleanup_enqueued_count": len(enqueued_document_ids),
        }
    except Exception:
        db.rollback()
        logger.exception("document finalize 실패")
        raise
    finally:
        db.close()
