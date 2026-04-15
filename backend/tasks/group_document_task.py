import logging
import sys

sys.path.insert(0, "/app")

from celery_app import celery_app
from database import SessionLocal
from models.model import DocumentLifecycleStatus, GroupStatus, ReviewStatus
from repositories.document_repository import DocumentRepository
from services.document_preview_service import DocumentPreviewService
from services.rag.group_document_indexing_service import (
    deindex_group_document,
    index_group_document,
)

logger = logging.getLogger(__name__)


def _state_value(state) -> str | None:
    """
    Enum 또는 문자열 상태값을 비교 가능한 문자열로 변환한다.
    상태 객체가 없으면 None을 반환한다.
    """
    if state is None:
        return None
    return state.value if hasattr(state, "value") else state


def _matches_expected_state(current, expected: str | None) -> bool:
    """
    현재 상태가 요청 당시 기대한 상태와 일치하는지 확인한다.
    expected가 없으면 상태 검증을 생략한다.
    """
    if expected is None:
        return True

    return _state_value(current) == expected


def _get_group_status(document) -> str | None:
    """
    문서가 속한 워크스페이스 상태값을 반환한다.
    그룹 정보가 없으면 None을 반환한다.
    """
    group = getattr(document, "group", None)
    return _state_value(getattr(group, "status", None))


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    name="tasks.group_document_task.index_approved_document",
)
def index_approved_document(
    self,
    document_id: int,
    expected_lifecycle_status: str | None = DocumentLifecycleStatus.ACTIVE.value,
    expected_group_status: str | None = GroupStatus.ACTIVE.value,
) -> dict:
    """
    APPROVED 상태 그룹 문서를 RAG 인덱스에 등록한다.
    요청 당시 기대 상태와 현재 상태가 다르면 오래된 요청으로 보고 스킵한다.
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

        current_lifecycle_status = _state_value(document.lifecycle_status)
        if not _matches_expected_state(
            document.lifecycle_status,
            expected_lifecycle_status,
        ):
            logger.info(
                "[그룹문서 인덱싱 태스크] stale lifecycle 스킵: "
                "document_id=%s, current=%s, expected=%s",
                document_id,
                current_lifecycle_status,
                expected_lifecycle_status,
            )
            return {
                "indexed": False,
                "reason": "stale_lifecycle_status",
                "document_id": document_id,
                "current_lifecycle_status": current_lifecycle_status,
                "expected_lifecycle_status": expected_lifecycle_status,
            }

        current_group_status = _get_group_status(document)
        if not _matches_expected_state(
            current_group_status,
            expected_group_status,
        ):
            logger.info(
                "[그룹문서 인덱싱 태스크] stale group 스킵: "
                "document_id=%s, current=%s, expected=%s",
                document_id,
                current_group_status,
                expected_group_status,
            )
            return {
                "indexed": False,
                "reason": "stale_group_status",
                "document_id": document_id,
                "current_group_status": current_group_status,
                "expected_group_status": expected_group_status,
            }

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
def deindex_document(
    self,
    document_id: int,
    expected_lifecycle_status: str | None = None,
    expected_group_status: str | None = None,
) -> dict:
    """
    문서 삭제 시 RAG 인덱스에서 제거한다.
    요청 당시 기대 상태와 현재 상태가 다르면 오래된 요청으로 보고 스킵한다.
    실패 시 Celery retry 로 재시도한다.
    """
    db = SessionLocal()
    try:
        repository = DocumentRepository(db)
        document = repository.get_by_id(document_id)

        if document is not None:
            current_lifecycle_status = _state_value(document.lifecycle_status)
            if not _matches_expected_state(
                document.lifecycle_status,
                expected_lifecycle_status,
            ):
                logger.info(
                    "[그룹문서 디인덱싱 태스크] stale lifecycle 스킵: "
                    "document_id=%s, current=%s, expected=%s",
                    document_id,
                    current_lifecycle_status,
                    expected_lifecycle_status,
                )
                return {
                    "deindexed": False,
                    "reason": "stale_lifecycle_status",
                    "document_id": document_id,
                    "current_lifecycle_status": current_lifecycle_status,
                    "expected_lifecycle_status": expected_lifecycle_status,
                }

            current_group_status = _get_group_status(document)
            if not _matches_expected_state(
                current_group_status,
                expected_group_status,
            ):
                logger.info(
                    "[그룹문서 디인덱싱 태스크] stale group 스킵: "
                    "document_id=%s, current=%s, expected=%s",
                    document_id,
                    current_group_status,
                    expected_group_status,
                )
                return {
                    "deindexed": False,
                    "reason": "stale_group_status",
                    "document_id": document_id,
                    "current_group_status": current_group_status,
                    "expected_group_status": expected_group_status,
                }

        deindex_group_document(document_id)
        return {"deindexed": True, "document_id": document_id}
    finally:
        db.close()
