import logging
import sys

sys.path.insert(0, "/app")

from celery_app import celery_app
from database import SessionLocal
from domains.document.preview_service import DocumentPreviewService
from domains.document.repository import DocumentRepository
from domains.document.summary_process import ProcessService
from errors import ErrorCode, FailureStage, build_exception_failure_payload
from models.model import DocumentStatus

logger = logging.getLogger(__name__)


def _schedule_next_pending_document():
    try:
        process_next_pending_document.delay()
    except Exception:
        logger.error(
            "[문서 처리 재enqueue 실패] 다음 beat kick에서 복구 대기",
            exc_info=True,
        )


@celery_app.task(bind=True)
def process_next_pending_document(self):
    db = SessionLocal()
    repository = DocumentRepository(db)
    preview_service = DocumentPreviewService(repository)

    document_id = None
    claimed_document = False
    processing_pdf_path = None

    def _handle_failure(stage: FailureStage, exc: Exception):
        logger.error(
            "[처리 실패] stage=%s doc_id=%s error=%s",
            stage.value,
            document_id,
            exc,
            exc_info=True,
        )
        if document_id is not None:
            failure_payload = build_exception_failure_payload(
                stage=stage,
                exc=exc,
                fallback_error_code=ErrorCode.DOC_INTERNAL_PARSE_ERROR,
                status="failed",
                retryable=False,
                include_legacy_error_fields=True,
                processed=False,
                document_id=document_id,
            )
            repository.update_status(
                document_id,
                DocumentStatus.FAILED,
                failure_stage=failure_payload["failure_stage"],
                failure_code=failure_payload["failure_code"],
                error_message=failure_payload["error_message"],
            )
            db.commit()
            return failure_payload

        return build_exception_failure_payload(
            stage=stage,
            exc=exc,
            fallback_error_code=ErrorCode.DOC_INTERNAL_PARSE_ERROR,
            status="failed",
            retryable=False,
            include_legacy_error_fields=True,
            processed=False,
            document_id=document_id,
        )

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

        try:
            processing_pdf_path = preview_service.ensure_preview_pdf(document)
        except Exception as exc:
            return _handle_failure(FailureStage.PREVIEW, exc)

        try:
            service = ProcessService()
            service.process_file(
                processing_pdf_path,
                document_id,
                mark_processing=False,
            )
        except Exception as exc:
            return _handle_failure(FailureStage.PROCESS, exc)

        logger.info("[ProcessService 완료] doc_id=%s", document_id)
        return {"processed": True, "document_id": document_id}

    except Exception as exc:
        return _handle_failure(FailureStage.PROCESS, exc)

    finally:
        db.close()
        if claimed_document:
            _schedule_next_pending_document()
