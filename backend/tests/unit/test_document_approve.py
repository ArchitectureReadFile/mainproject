from unittest.mock import MagicMock, patch

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
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
    User,
)
from tests.dummy_data import groups, users

auth_service = AuthService(None)

GROUP_ID = 1

editor_user = {
    "id": 3,
    "email": "editor@example.com",
    "username": "편집자",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}

uploader_user = {
    "id": 4,
    "email": "uploader@example.com",
    "username": "업로더",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}


# UT-DOC-012-01 그룹 OWNER 또는 ADMIN은 승인 대기 상태의 문서를 정상 승인할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [
        (users[0], MembershipRole.OWNER),
        (users[1], MembershipRole.ADMIN),
    ],
    indirect=["logged_in_user"],
)
def test_approve_document_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role
):
    """그룹 OWNER 또는 ADMIN은 승인 대기 상태의 문서를 정상 승인하는지 검증한다."""
    uploader_data = uploader_user.copy()
    uploader_data["password"] = auth_service.hash_password(uploader_data["password"])
    uploader = User(**uploader_data)
    db_session.add(uploader)
    db_session.flush()

    if member_role == MembershipRole.OWNER:
        owner_user_id = logged_in_user.id
    else:
        owner_data = users[0].copy()
        owner_data["password"] = auth_service.hash_password(owner_data["password"])
        owner = User(**owner_data)
        db_session.add(owner)
        db_session.flush()
        owner_user_id = owner.id

        db_session.add(
            GroupMember(
                user_id=owner.id,
                group_id=GROUP_ID,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )

    db_session.add(
        Group(
            id=GROUP_ID,
            owner_user_id=owner_user_id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=GROUP_ID,
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=uploader.id,
            group_id=GROUP_ID,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=601,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="pending_review_doc.pdf",
            stored_path="/tmp/test_docs/pending_review_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=601,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/{GROUP_ID}/documents/601/approve")
    assert res.status_code == 200
    assert res.json()["message"] == "문서가 승인되었습니다."

    approval = (
        db_session.query(DocumentApproval)
        .filter(DocumentApproval.document_id == 601)
        .first()
    )
    assert approval is not None
    assert approval.status == ReviewStatus.APPROVED
    assert approval.reviewer_user_id == logged_in_user.id
    assert approval.reviewed_at is not None


# UT-DOC-012-02 이미 승인 완료된 문서는 다시 승인할 수 없다.
def test_approve_document_conflict_for_already_approved_document(authenticated_client):
    """이미 승인 완료된 문서는 다시 승인할 수 없는지 검증한다."""
    res = authenticated_client.post(f"/api/groups/{GROUP_ID}/documents/101/approve")
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.DOC_NOT_PENDING_REVIEW.code


# UT-DOC-012-03 다른 그룹의 문서는 승인할 수 없다.
def test_approve_document_not_found_for_other_group(authenticated_client):
    """다른 그룹의 문서는 승인할 수 없는지 검증한다."""
    res = authenticated_client.post(f"/api/groups/{GROUP_ID}/documents/102/approve")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-012-04 OWNER 또는 ADMIN이 아닌 사용자는 문서를 승인할 수 없다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_approve_document_forbidden_for_non_admin_or_owner(
    client, db_session, logged_in_user
):
    """OWNER 또는 ADMIN이 아닌 사용자는 문서를 승인할 수 없는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)

    uploader_data = uploader_user.copy()
    uploader_data["password"] = auth_service.hash_password(uploader_data["password"])
    uploader = User(**uploader_data)

    db_session.add(owner)
    db_session.add(uploader)
    db_session.flush()

    db_session.add(
        Group(
            id=GROUP_ID,
            owner_user_id=owner.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
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
            role=MembershipRole.EDITOR,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=uploader.id,
            group_id=GROUP_ID,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=602,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="pending_review_doc_2.pdf",
            stored_path="/tmp/test_docs/pending_review_doc_2.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=602,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/{GROUP_ID}/documents/602/approve")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-DOC-012-05 비로그인 사용자는 문서를 승인할 수 없다.
def test_approve_document_unauthenticated(client):
    """비로그인 사용자는 문서 승인 요청이 차단되는지 검증한다."""
    res = client.post(f"/api/groups/{GROUP_ID}/documents/601/approve")
    assert res.status_code == 401


# UT-DOC-012-06 processing_status==DONE 상태에서 승인시 index가 enqueue된다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [(users[0], MembershipRole.OWNER)],
    indirect=["logged_in_user"],
)
def test_approve_document_enqueues_index_when_done(
    client, db_session, logged_in_user, member_role
):
    """processing_status==DONE 상태로 승인시 index_approved_document.delay가 호출되는지 검증."""
    uploader_data = uploader_user.copy()
    uploader_data["password"] = auth_service.hash_password(uploader_data["password"])
    uploader = User(**uploader_data)
    db_session.add(uploader)
    db_session.flush()

    db_session.add(
        Group(
            id=GROUP_ID,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=GROUP_ID,
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=uploader.id,
            group_id=GROUP_ID,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=611,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="done_doc.pdf",
            stored_path="/tmp/test_docs/done_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=611,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    with patch("domains.document.review_service.index_approved_document") as mock_task:
        mock_task.delay = MagicMock()
        res = client.post(f"/api/groups/{GROUP_ID}/documents/611/approve")

    assert res.status_code == 200
    mock_task.delay.assert_called_once_with(611)


# UT-DOC-012-07 processing_status!=DONE 상태에서 승인시 index가 enqueue되지 않는다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [(users[0], MembershipRole.OWNER)],
    indirect=["logged_in_user"],
)
def test_approve_document_does_not_enqueue_index_when_not_done(
    client, db_session, logged_in_user, member_role
):
    """processing_status!=DONE 상태 승인시 index_approved_document.delay가 호출되지 않는지 검증."""
    uploader_data = uploader_user.copy()
    uploader_data["password"] = auth_service.hash_password(uploader_data["password"])
    uploader = User(**uploader_data)
    db_session.add(uploader)
    db_session.flush()

    db_session.add(
        Group(
            id=GROUP_ID,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=GROUP_ID,
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=uploader.id,
            group_id=GROUP_ID,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=612,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="pending_doc.pdf",
            stored_path="/tmp/test_docs/pending_doc.pdf",
            processing_status=DocumentStatus.PROCESSING,  # DONE 아님
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=612,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    with patch("domains.document.review_service.index_approved_document") as mock_task:
        mock_task.delay = MagicMock()
        res = client.post(f"/api/groups/{GROUP_ID}/documents/612/approve")

    assert res.status_code == 200
    mock_task.delay.assert_not_called()
