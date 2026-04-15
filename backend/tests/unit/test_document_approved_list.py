from datetime import timedelta

import pytest

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
    utc_now_naive,
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)

GROUP_ID = 1

uploader_user = {
    "id": 3,
    "email": "uploader@example.com",
    "username": "업로더",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}

other_uploader_user = {
    "id": 4,
    "email": "other_uploader@example.com",
    "username": "다른업로더",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}


# UT-DOC-010-01 그룹 OWNER 또는 ADMIN은 본인이 승인한 문서 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [
        (users[0], MembershipRole.OWNER),
        (users[1], MembershipRole.ADMIN),
    ],
    indirect=["logged_in_user"],
)
def test_get_approved_documents_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role
):
    """그룹 OWNER 또는 ADMIN은 본인이 승인한 문서 목록을 정상 조회하는지 검증한다."""
    now = utc_now_naive()

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

    uploader_data = uploader_user.copy()
    uploader_data["password"] = auth_service.hash_password(uploader_data["password"])
    uploader = User(**uploader_data)
    db_session.add(uploader)
    db_session.flush()

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
            id=401,
            group_id=GROUP_ID,
            uploader_user_id=owner_user_id,
            original_filename="approved_doc_1.pdf",
            stored_path="/tmp/test_docs/approved_doc_1.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=402,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="approved_doc_2.pdf",
            stored_path="/tmp/test_docs/approved_doc_2.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=403,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="approved_doc_other_reviewer.pdf",
            stored_path="/tmp/test_docs/approved_doc_other_reviewer.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )

    db_session.add(
        DocumentApproval(
            document_id=401,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=logged_in_user.id,
            reviewed_at=now - timedelta(minutes=2),
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=402,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=logged_in_user.id,
            reviewed_at=now - timedelta(minutes=1),
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=403,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=999,
            reviewed_at=now,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/approved?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 2
    assert set(ids) == {401, 402}


# UT-DOC-010-02 업로더 필터가 있는 경우 해당 업로더의 승인 완료 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_approved_documents_success_with_uploader_filter(
    client, db_session, logged_in_user
):
    """업로더 필터가 있는 경우 해당 업로더의 승인 완료 문서만 조회하는지 검증한다."""
    now = utc_now_naive()

    uploader_data = uploader_user.copy()
    uploader_data["password"] = auth_service.hash_password(uploader_data["password"])
    uploader = User(**uploader_data)

    other_uploader_data = other_uploader_user.copy()
    other_uploader_data["password"] = auth_service.hash_password(
        other_uploader_data["password"]
    )
    other_uploader = User(**other_uploader_data)

    db_session.add(uploader)
    db_session.add(other_uploader)
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
            role=MembershipRole.OWNER,
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
        GroupMember(
            user_id=other_uploader.id,
            group_id=GROUP_ID,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=411,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="filtered_uploader_doc.pdf",
            stored_path="/tmp/test_docs/filtered_uploader_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=412,
            group_id=GROUP_ID,
            uploader_user_id=other_uploader.id,
            original_filename="other_uploader_doc.pdf",
            stored_path="/tmp/test_docs/other_uploader_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )

    db_session.add(
        DocumentApproval(
            document_id=411,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=logged_in_user.id,
            reviewed_at=now - timedelta(minutes=1),
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=412,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=logged_in_user.id,
            reviewed_at=now,
        )
    )
    db_session.commit()

    res = client.get(
        f"/api/groups/{GROUP_ID}/documents/approved?skip=0&limit=10&uploader={uploader.username}"
    )
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 1
    assert ids == [411]
    assert data["items"][0]["uploader"] == uploader.username


# UT-DOC-010-03 OWNER 또는 ADMIN이 아닌 사용자는 승인 완료 문서 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize("member_role", [MembershipRole.EDITOR, MembershipRole.VIEWER])
def test_get_approved_documents_forbidden_for_non_admin_or_owner(
    client, db_session, logged_in_user, member_role
):
    """OWNER 또는 ADMIN이 아닌 사용자는 승인 완료 문서 목록을 조회할 수 없는지 검증한다."""
    owner_data = users[1].copy()
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
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/approved?skip=0&limit=10")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-DOC-010-04 비로그인 사용자는 승인 완료 문서 목록을 조회할 수 없다.
def test_get_approved_documents_unauthenticated(client):
    """비로그인 사용자는 승인 완료 문서 목록 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/approved?skip=0&limit=10")
    assert res.status_code == 401
