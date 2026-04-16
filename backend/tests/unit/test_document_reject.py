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


# UT-DOC-013-01 그룹 OWNER 또는 ADMIN은 승인 대기 상태의 문서를 정상 반려할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [
        (users[0], MembershipRole.OWNER),
        (users[1], MembershipRole.ADMIN),
    ],
    indirect=["logged_in_user"],
)
def test_reject_document_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role
):
    """그룹 OWNER 또는 ADMIN은 승인 대기 상태의 문서를 정상 반려하는지 검증한다."""
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
            id=701,
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
            document_id=701,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    payload = {"feedback": "보완이 필요합니다."}

    res = client.post(f"/api/groups/{GROUP_ID}/documents/701/reject", json=payload)
    assert res.status_code == 200
    assert res.json()["message"] == "문서가 반려되었습니다."

    approval = (
        db_session.query(DocumentApproval)
        .filter(DocumentApproval.document_id == 701)
        .first()
    )
    assert approval is not None
    assert approval.status == ReviewStatus.REJECTED
    assert approval.reviewer_user_id == logged_in_user.id
    assert approval.feedback == "보완이 필요합니다."
    assert approval.reviewed_at is not None


# UT-DOC-013-02 이미 반려된 문서는 다시 반려할 수 없다.
def test_reject_document_conflict_for_already_rejected_document(
    authenticated_client, db_session
):
    """이미 반려된 문서는 다시 반려할 수 없는지 검증한다."""
    db_session.add(
        DocumentApproval(
            document_id=103,
            status=ReviewStatus.REJECTED,
            reviewer_user_id=1,
            feedback="기존 반려 의견",
        )
    )
    db_session.commit()

    payload = {"feedback": "다시 반려합니다."}

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/103/reject", json=payload
    )
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.DOC_NOT_PENDING_REVIEW.code


# UT-DOC-013-03 다른 그룹의 문서는 반려할 수 없다.
def test_reject_document_not_found_for_other_group(authenticated_client):
    """다른 그룹의 문서는 반려할 수 없는지 검증한다."""
    payload = {"feedback": "그룹이 다릅니다."}

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/102/reject", json=payload
    )
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-013-04 OWNER 또는 ADMIN이 아닌 사용자는 문서를 반려할 수 없다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_reject_document_forbidden_for_non_admin_or_owner(
    client, db_session, logged_in_user
):
    """OWNER 또는 ADMIN이 아닌 사용자는 문서를 반려할 수 없는지 검증한다."""
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
            id=702,
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
            document_id=702,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    payload = {"feedback": "권한 없음"}

    res = client.post(f"/api/groups/{GROUP_ID}/documents/702/reject", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-DOC-013-05 비로그인 사용자는 문서를 반려할 수 없다.
def test_reject_document_unauthenticated(client):
    """비로그인 사용자는 문서 반려 요청이 차단되는지 검증한다."""
    payload = {"feedback": "비로그인"}

    res = client.post(f"/api/groups/{GROUP_ID}/documents/701/reject", json=payload)
    assert res.status_code == 401
