import logging

from celery_app import celery_app
from database import SessionLocal
from domains.document.file_cleanup_task import enqueue_document_file_cleanup
from models.model import (
    Document,
    DocumentLifecycleStatus,
    Group,
    GroupPendingReason,
    GroupStatus,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


def _get_due_workspaces(*, db, now) -> list[Group]:
    """최종 삭제 시각이 도래한 OWNER 삭제 요청 워크스페이스를 조회한다."""
    return (
        db.query(Group)
        .filter(
            Group.status == GroupStatus.DELETE_PENDING,
            Group.pending_reason == GroupPendingReason.OWNER_DELETE_REQUEST,
            Group.delete_scheduled_at.isnot(None),
            Group.delete_scheduled_at <= now,
        )
        .all()
    )


def _get_deletable_documents(*, db, group_id: int) -> list[Document]:
    """워크스페이스 삭제 시 함께 정리할 문서를 조회한다."""
    return (
        db.query(Document)
        .filter(
            Document.group_id == group_id,
            Document.lifecycle_status != DocumentLifecycleStatus.DELETED,
        )
        .all()
    )


@celery_app.task(name="tasks.workspace_deletion_task.finalize_pending_workspaces")
def finalize_pending_workspaces():
    """OWNER 삭제 요청 유예가 끝난 워크스페이스를 최종 삭제 상태로 전환한다."""
    db = SessionLocal()
    try:
        now = utc_now_naive()
        workspaces = _get_due_workspaces(db=db, now=now)

        finalized_workspace_count = 0
        finalized_document_count = 0
        deleted_document_ids: list[int] = []

        for workspace in workspaces:
            workspace.status = GroupStatus.DELETED
            workspace.deleted_at = now

            documents = _get_deletable_documents(
                db=db,
                group_id=workspace.id,
            )

            for document in documents:
                document.lifecycle_status = DocumentLifecycleStatus.DELETED
                document.deleted_at = now
                finalized_document_count += 1
                deleted_document_ids.append(document.id)

            finalized_workspace_count += 1

        if finalized_workspace_count > 0:
            db.commit()

        enqueued_document_ids: list[int] = []
        if deleted_document_ids:
            enqueued_document_ids = enqueue_document_file_cleanup(deleted_document_ids)

        logger.info(
            "[workspace finalize] finalized_workspaces=%s finalized_documents=%s file_cleanup_enqueued=%s",
            finalized_workspace_count,
            finalized_document_count,
            len(enqueued_document_ids),
        )

        return {
            "finalized_workspace_count": finalized_workspace_count,
            "finalized_document_count": finalized_document_count,
            "deleted_document_ids": deleted_document_ids,
            "file_cleanup_enqueued_count": len(enqueued_document_ids),
        }
    except Exception:
        db.rollback()
        logger.exception("workspace finalize 실패")
        raise
    finally:
        db.close()
