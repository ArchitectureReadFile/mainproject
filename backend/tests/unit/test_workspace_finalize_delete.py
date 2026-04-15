from datetime import timedelta

from models.model import (
    Document,
    DocumentLifecycleStatus,
    DocumentStatus,
    Group,
    GroupPendingReason,
    GroupStatus,
    utc_now_naive,
)
from tasks.workspace_deletion_task import finalize_pending_workspaces


# UT-GRP-017-01 삭제 예정일이 지난 OWNER_DELETE_REQUEST 상태의 워크스페이스는 DELETED 상태로 최종 전환된다.
def test_finalize_pending_workspaces_marks_workspace_deleted(db_session, monkeypatch):
    """삭제 예정일이 지난 OWNER_DELETE_REQUEST 워크스페이스가 DELETED로 최종 전환되는지 검증한다."""
    now = utc_now_naive()

    workspace = Group(
        id=1,
        owner_user_id=1,
        name="삭제 예정 워크스페이스",
        description="최종 처리 테스트",
        status=GroupStatus.DELETE_PENDING,
        pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        delete_requested_at=now - timedelta(days=31),
        delete_scheduled_at=now - timedelta(minutes=1),
    )
    db_session.add(workspace)
    db_session.commit()

    monkeypatch.setattr(
        "tasks.workspace_deletion_task.SessionLocal",
        lambda: db_session,
    )
    monkeypatch.setattr(
        "tasks.workspace_deletion_task.enqueue_document_file_cleanup",
        lambda document_ids: [],
    )

    result = finalize_pending_workspaces()

    workspace = db_session.query(Group).filter(Group.id == 1).first()
    assert workspace is not None
    assert workspace.status == GroupStatus.DELETED
    assert workspace.deleted_at is not None

    assert result["finalized_workspace_count"] == 1
    assert result["finalized_document_count"] == 0


# UT-GRP-017-02 삭제 예정일이 지나지 않은 OWNER_DELETE_REQUEST 상태의 워크스페이스는 DELETED 상태로 전환되지 않는다.
def test_finalize_pending_workspaces_skips_not_due_workspace(db_session, monkeypatch):
    """삭제 예정일이 지나지 않은 OWNER_DELETE_REQUEST 워크스페이스는 최종 전환되지 않는지 검증한다."""
    now = utc_now_naive()

    workspace = Group(
        id=1,
        owner_user_id=1,
        name="삭제 대기 워크스페이스",
        description="최종 처리 테스트",
        status=GroupStatus.DELETE_PENDING,
        pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        delete_requested_at=now - timedelta(days=1),
        delete_scheduled_at=now + timedelta(days=29),
    )
    db_session.add(workspace)
    db_session.commit()

    monkeypatch.setattr(
        "tasks.workspace_deletion_task.SessionLocal",
        lambda: db_session,
    )
    monkeypatch.setattr(
        "tasks.workspace_deletion_task.enqueue_document_file_cleanup",
        lambda document_ids: [],
    )

    result = finalize_pending_workspaces()

    workspace = db_session.query(Group).filter(Group.id == 1).first()
    assert workspace is not None
    assert workspace.status == GroupStatus.DELETE_PENDING
    assert workspace.deleted_at is None

    assert result["finalized_workspace_count"] == 0
    assert result["finalized_document_count"] == 0


# UT-GRP-017-03 DELETED 상태로 최종 전환된 워크스페이스의 하위 문서는 함께 DELETED 상태로 처리된다.
def test_finalize_pending_workspaces_marks_child_documents_deleted(
    db_session, monkeypatch
):
    """최종 전환된 워크스페이스의 하위 문서가 함께 DELETED 상태로 처리되는지 검증한다."""
    now = utc_now_naive()

    workspace = Group(
        id=1,
        owner_user_id=1,
        name="삭제 예정 워크스페이스",
        description="최종 처리 테스트",
        status=GroupStatus.DELETE_PENDING,
        pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        delete_requested_at=now - timedelta(days=31),
        delete_scheduled_at=now - timedelta(minutes=1),
    )
    db_session.add(workspace)
    db_session.flush()

    document = Document(
        id=101,
        group_id=workspace.id,
        uploader_user_id=1,
        original_filename="doc_101.pdf",
        stored_path="/tmp/test_docs/doc_101.pdf",
        processing_status=DocumentStatus.DONE,
        lifecycle_status=DocumentLifecycleStatus.ACTIVE,
    )
    db_session.add(document)
    db_session.commit()

    monkeypatch.setattr(
        "tasks.workspace_deletion_task.SessionLocal",
        lambda: db_session,
    )
    monkeypatch.setattr(
        "tasks.workspace_deletion_task.enqueue_document_file_cleanup",
        lambda document_ids: document_ids,
    )

    result = finalize_pending_workspaces()

    workspace = db_session.query(Group).filter(Group.id == 1).first()
    document = db_session.query(Document).filter(Document.id == 101).first()

    assert workspace is not None
    assert workspace.status == GroupStatus.DELETED

    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.DELETED
    assert document.deleted_at is not None

    assert result["finalized_workspace_count"] == 1
    assert result["finalized_document_count"] == 1
    assert result["deleted_document_ids"] == [101]
    assert result["file_cleanup_enqueued_count"] == 1


# UT-GRP-017-04 삭제 예정일이 지나지 않은 OWNER_DELETE_REQUEST 상태의 워크스페이스 하위 문서는 삭제 상태로 전환되지 않는다.
def test_finalize_pending_workspaces_keeps_child_documents_of_non_due_workspace(
    db_session, monkeypatch
):
    """삭제 예정일이 지나지 않은 OWNER_DELETE_REQUEST 상태의 워크스페이스 하위 문서는 삭제 상태로 전환되지 않는지 검증한다."""
    now = utc_now_naive()

    workspace = Group(
        id=1,
        owner_user_id=1,
        name="삭제 대기 워크스페이스",
        description="최종 처리 테스트",
        status=GroupStatus.DELETE_PENDING,
        pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        delete_requested_at=now - timedelta(days=1),
        delete_scheduled_at=now + timedelta(days=29),
    )
    db_session.add(workspace)
    db_session.flush()

    document = Document(
        id=101,
        group_id=workspace.id,
        uploader_user_id=1,
        original_filename="doc_101.pdf",
        stored_path="/tmp/test_docs/doc_101.pdf",
        processing_status=DocumentStatus.DONE,
        lifecycle_status=DocumentLifecycleStatus.ACTIVE,
    )
    db_session.add(document)
    db_session.commit()

    monkeypatch.setattr(
        "tasks.workspace_deletion_task.SessionLocal",
        lambda: db_session,
    )
    monkeypatch.setattr(
        "tasks.workspace_deletion_task.enqueue_document_file_cleanup",
        lambda document_ids: [],
    )

    result = finalize_pending_workspaces()

    workspace = db_session.query(Group).filter(Group.id == 1).first()
    document = db_session.query(Document).filter(Document.id == 101).first()

    assert workspace is not None
    assert workspace.status == GroupStatus.DELETE_PENDING
    assert workspace.deleted_at is None

    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.ACTIVE
    assert document.deleted_at is None

    assert result["finalized_workspace_count"] == 0
    assert result["finalized_document_count"] == 0
    assert result["deleted_document_ids"] == []
    assert result["file_cleanup_enqueued_count"] == 0
