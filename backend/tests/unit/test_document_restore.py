import pytest

from errors import ErrorCode
from models.model import (
    Document,
    DocumentApproval,
    DocumentLifecycleStatus,
    DocumentStatus,
    Group,
    GroupMember,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
    User,
    utc_now_naive,
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)

GROUP_ID = 1


# UT-DOC-008-01 문서 업로더는 삭제 요청 상태의 문서를 정상 복구할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_restore_document_success_for_uploader(client, db_session, logged_in_user):
    """문서 업로더는 삭제 요청 상태의 문서를 정상 복구하는지 검증한다."""
    now = utc_now_naive()

    db_session.add(
        Group(
            id=GROUP_ID,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status="ACTIVE",
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=GROUP_ID,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=101,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="deleted_doc.pdf",
            stored_path="/tmp/test_docs/deleted_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.DELETE_PENDING,
            delete_requested_at=now,
            delete_scheduled_at=now,
            deleted_by_user_id=logged_in_user.id,
        )
    )
    db_session.add(DocumentApproval(document_id=101, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = client.post(f"/api/groups/{GROUP_ID}/documents/101/restore")
    assert res.status_code == 204

    document = db_session.query(Document).filter(Document.id == 101).first()
    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.ACTIVE
    assert document.delete_requested_at is None
    assert document.delete_scheduled_at is None
    assert document.deleted_by_user_id is None


# UT-DOC-008-02 그룹 OWNER 또는 ADMIN은 다른 사용자의 삭제 요청 문서를 정상 복구할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_restore_document_success_for_group_admin(client, db_session, logged_in_user):
    """그룹 OWNER 또는 ADMIN은 다른 사용자의 삭제 요청 문서를 정상 복구하는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=GROUP_ID,
            owner_user_id=owner.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status="ACTIVE",
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=GROUP_ID,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=GROUP_ID,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )

    now = utc_now_naive()
    db_session.add(
        Document(
            id=201,
            group_id=GROUP_ID,
            uploader_user_id=owner.id,
            original_filename="deleted_owner_doc.pdf",
            stored_path="/tmp/test_docs/deleted_owner_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.DELETE_PENDING,
            delete_requested_at=now,
            delete_scheduled_at=now,
            deleted_by_user_id=logged_in_user.id,
        )
    )
    db_session.add(DocumentApproval(document_id=201, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = client.post(f"/api/groups/{GROUP_ID}/documents/201/restore")
    assert res.status_code == 204

    document = db_session.query(Document).filter(Document.id == 201).first()
    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.ACTIVE
    assert document.delete_requested_at is None
    assert document.delete_scheduled_at is None
    assert document.deleted_by_user_id is None


# UT-DOC-008-03 삭제 요청 상태가 아닌 문서는 복구할 수 없다.
def test_restore_document_bad_request_for_non_delete_pending_document(
    authenticated_client, db_session
):
    """삭제 요청 상태가 아닌 문서는 복구할 수 없는지 검증한다."""
    document = db_session.query(Document).filter(Document.id == 101).first()
    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.ACTIVE

    res = authenticated_client.post(f"/api/groups/{GROUP_ID}/documents/101/restore")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.DOC_NOT_DELETE_PENDING.code


# UT-DOC-008-04 존재하지 않는 문서는 복구할 수 없다.
def test_restore_document_not_found(authenticated_client):
    """존재하지 않는 문서는 복구할 수 없는지 검증한다."""
    res = authenticated_client.post(f"/api/groups/{GROUP_ID}/documents/9999/restore")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-008-05 비로그인 사용자는 삭제 문서를 복구할 수 없다.
def test_restore_document_unauthenticated(client):
    """비로그인 사용자는 삭제 문서 복구 요청이 차단되는지 검증한다."""
    res = client.post(f"/api/groups/{GROUP_ID}/documents/101/restore")
    assert res.status_code == 401
