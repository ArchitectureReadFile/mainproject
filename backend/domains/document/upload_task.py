import logging
import sys

sys.path.insert(0, "/app")

from celery_app import celery_app
from database import SessionLocal
from domains.document.preview_service import DocumentPreviewService
from domains.document.repository import DocumentRepository
from domains.document.summary_process import ProcessService
from errors import AppException
from models.model import DocumentStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def process_next_pending_document(self):
    db = SessionLocal()
    repository = DocumentRepository(db)
    preview_service = DocumentPreviewService(repository)

    document_id = None
    claimed_document = False
    processing_pdf_path = None

    try:
        document = repository.claim_next_pending_document()
        if document is None:
            logger.info("[태스크 종료] 처리할 PENDING 문서가 없습니다.")
            db.commit()
            return {"processed": False}

        document_id = document.id
        claimed_document = True
        db.commit()

        logger.info(
            "[태스크 시작] doc_id=%s, file=%s",
            document_id,
            document.original_filename,
        )

        processing_pdf_path = preview_service.ensure_preview_pdf(document)

        service = ProcessService()
        service.process_file(
            processing_pdf_path,
            document_id,
            mark_processing=False,
        )

        logger.info("[ProcessService 완료] doc_id=%s", document_id)
        return {"processed": True, "document_id": document_id}

    except AppException as e:
        logger.error(f"[처리 실패] doc_id={document_id}, error={e}", exc_info=True)
        if document_id is not None:
            repository.update_status(document_id, DocumentStatus.FAILED)
            db.commit()

        return {
            "processed": False,
            "document_id": document_id,
            "error_code": e.code,
            "message": e.message,
        }

    except Exception as e:
        logger.error(f"[처리 실패] doc_id={document_id}, error={e}", exc_info=True)
        if document_id is not None:
            repository.update_status(document_id, DocumentStatus.FAILED)
            db.commit()

        return {
            "processed": False,
            "document_id": document_id,
            "error": str(e),
        }

    finally:
        db.close()
        if claimed_document:
            process_next_pending_document.delay()
