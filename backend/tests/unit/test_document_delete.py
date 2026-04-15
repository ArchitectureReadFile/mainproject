import pytest

from domains.auth.service import AuthService
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
)
from tests.dummy_data import groups, users

auth_service = AuthService(None)

GROUP_ID = 1  # seed_documents / authenticated_client 기준


# UT-DOC-006-01 문서 업로더는 문서를 정상 삭제할 수 있다.
def test_delete_document_success_for_uploader(authenticated_client, db_session):
    """문서 업로더는 문서를 정상 삭제하는지 검증한다."""
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 204

    document = db_session.query(Document).filter(Document.id == 101).first()
    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING
    assert document.deleted_by_user_id == 1
    assert document.delete_requested_at is not None
    assert document.delete_scheduled_at is not None


# UT-DOC-006-02 그룹 OWNER 또는 ADMIN은 다른 사용자의 문서를 정상 삭제할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_delete_document_success_for_group_admin(client, db_session, logged_in_user):
    """그룹 OWNER 또는 ADMIN은 다른 사용자의 문서를 정상 삭제하는지 검증한다."""
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

    db_session.add(
        Document(
            id=201,
            group_id=GROUP_ID,
            uploader_user_id=owner.id,
            original_filename="owner_doc.pdf",
            stored_path="/tmp/test_docs/owner_doc.pdf",
            processing_status=DocumentStatus.DONE,
        )
    )
    db_session.add(DocumentApproval(document_id=201, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = client.delete(f"/api/groups/{GROUP_ID}/documents/201")
    assert res.status_code == 204

    document = db_session.query(Document).filter(Document.id == 201).first()
    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING
    assert document.deleted_by_user_id == logged_in_user.id
    assert document.delete_requested_at is not None
    assert document.delete_scheduled_at is not None


# UT-DOC-006-03 다른 그룹의 문서는 삭제할 수 없다.
def test_delete_document_not_found_for_other_group(authenticated_client):
    """다른 그룹의 문서는 삭제할 수 없는지 검증한다."""
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/102")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-006-04 이미 삭제 요청 상태인 문서는 다시 삭제할 수 없다.
def test_delete_document_conflict_for_delete_pending_document(
    authenticated_client, db_session
):
    """이미 삭제 요청 상태인 문서는 다시 삭제할 수 없는지 검증한다."""
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 204

    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.DOC_ALREADY_DELETE_PENDING.code

    document = db_session.query(Document).filter(Document.id == 101).first()
    assert document is not None
    assert document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING


# UT-DOC-006-05 존재하지 않는 문서는 삭제할 수 없다.
def test_delete_document_not_found(authenticated_client):
    """존재하지 않는 문서는 삭제할 수 없는지 검증한다."""
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/9999")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-006-06 비로그인 사용자는 문서를 삭제할 수 없다.
def test_delete_document_unauthenticated(client):
    """비로그인 사용자는 문서 삭제 요청이 차단되는지 검증한다."""
    res = client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 401
