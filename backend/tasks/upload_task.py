import logging
import sys

sys.path.insert(0, "/app")

from celery_app import celery_app
from database import SessionLocal
from repositories.document_repository import DocumentRepository
from services.summary.process_service import ProcessService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def process_next_pending_document(self):
    db = SessionLocal()
    repository = DocumentRepository(db)
    document_id = None
    claimed_document = False
    file_path = None

    try:
        document = repository.claim_next_pending_document()
        if document is None:
            logger.info("[태스크 종료] 처리할 PENDING 문서가 없습니다.")
            db.commit()
            return {"processed": False}

        document_id = document.id
        file_path = document.stored_path
        original_filename = document.original_filename
        claimed_document = True
        db.commit()

        logger.info("[태스크 시작] doc_id=%s, file=%s", document_id, original_filename)
        service = ProcessService()
        service.process_file(file_path, document_id, mark_processing=False)
        logger.info("[ProcessService 완료] doc_id=%s", document_id)
        return {"processed": True, "document_id": document_id}

    except Exception as e:
        logger.error(f"[처리 실패] doc_id={document_id}, error={e}", exc_info=True)
        raise
    finally:
        db.close()
        if claimed_document:
            process_next_pending_document.delay()
