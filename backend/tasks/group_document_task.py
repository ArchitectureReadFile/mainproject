import logging
import sys

sys.path.insert(0, "/app")

from celery_app import celery_app
from database import SessionLocal
from models.model import ReviewStatus
from repositories.document_repository import DocumentRepository
from services.document_preview_service import DocumentPreviewService
from services.rag.group_document_indexing_service import (
    deindex_group_document,
    index_group_document,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    name="tasks.group_document_task.index_approved_document",
)
def index_approved_document(self, document_id: int) -> dict:
    """
    APPROVED 상태 그룹 문서를 RAG 인덱스에 등록한다.
    실패 시 Celery retry 로 재시도한다.
    """
    db = SessionLocal()
    try:
        repository = DocumentRepository(db)
        preview_service = DocumentPreviewService(repository)
        document = repository.get_by_id(document_id)

        if document is None:
            logger.warning("[그룹문서 인덱싱 태스크] document 없음: id=%s", document_id)
            return {"indexed": False, "reason": "document_not_found"}

        approval = document.approval
        if approval is None or approval.status != ReviewStatus.APPROVED:
            current = approval.status.value if approval else "no_approval_record"
            logger.warning(
                "[그룹문서 인덱싱 태스크] APPROVED 아님, 스킵: document_id=%s, status=%s",
                document_id,
                current,
            )
            return {
                "indexed": False,
                "reason": "document_not_approved",
                "status": current,
            }

        preview_pdf_path = preview_service.ensure_preview_pdf(document)

        chunk_count = index_group_document(
            document_id=document_id,
            group_id=document.group_id,
            file_name=document.original_filename,
            document_type=document.document_type,
            category=document.category,
            file_path=preview_pdf_path,
        )

        return {"indexed": True, "document_id": document_id, "chunks": chunk_count}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    name="tasks.group_document_task.deindex_document",
)
def deindex_document(self, document_id: int) -> dict:
    """
    문서 삭제 시 RAG 인덱스에서 제거한다.
    실패 시 Celery retry 로 재시도한다.
    """
    deindex_group_document(document_id)
    return {"deindexed": True, "document_id": document_id}
