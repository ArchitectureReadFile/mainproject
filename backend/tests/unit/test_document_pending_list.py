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
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)

GROUP_ID = 1

reviewer_user = {
    "id": 3,
    "email": "reviewer@example.com",
    "username": "담당검토자",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}

other_member_user = {
    "id": 4,
    "email": "member@example.com",
    "username": "일반멤버",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}


# UT-DOC-009-01 그룹 OWNER 또는 ADMIN은 승인 대기 문서 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [
        (users[0], MembershipRole.OWNER),
        (users[1], MembershipRole.ADMIN),
    ],
    indirect=["logged_in_user"],
)
def test_get_pending_documents_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role
):
    """그룹 OWNER 또는 ADMIN은 승인 대기 문서 목록을 정상 조회하는지 검증한다."""
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

    uploader_data = other_member_user.copy()
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
            id=301,
            group_id=GROUP_ID,
            uploader_user_id=owner_user_id,
            original_filename="pending_owner_doc.pdf",
            stored_path="/tmp/test_docs/pending_owner_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=302,
            group_id=GROUP_ID,
            uploader_user_id=uploader.id,
            original_filename="pending_member_doc.pdf",
            stored_path="/tmp/test_docs/pending_member_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=301,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=302,
            status=ReviewStatus.PENDING_REVIEW,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/pending?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 2
    assert set(ids) == {301, 302}


# UT-DOC-009-02 담당자 필터가 mine인 경우 본인에게 지정된 승인 대기 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_get_pending_documents_success_with_assignee_type_mine(
    client, db_session, logged_in_user
):
    """담당자 필터가 mine인 경우 본인에게 지정된 승인 대기 문서만 조회하는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)

    reviewer_data = reviewer_user.copy()
    reviewer_data["password"] = auth_service.hash_password(reviewer_data["password"])
    reviewer = User(**reviewer_data)
    db_session.add(reviewer)
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
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=reviewer.id,
            group_id=GROUP_ID,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=311,
            group_id=GROUP_ID,
            uploader_user_id=owner.id,
            original_filename="mine_pending_doc.pdf",
            stored_path="/tmp/test_docs/mine_pending_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=312,
            group_id=GROUP_ID,
            uploader_user_id=owner.id,
            original_filename="other_pending_doc.pdf",
            stored_path="/tmp/test_docs/other_pending_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=311,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=logged_in_user.id,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=312,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=reviewer.id,
        )
    )
    db_session.commit()

    res = client.get(
        f"/api/groups/{GROUP_ID}/documents/pending?skip=0&limit=10&assignee_type=mine"
    )
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 1
    assert ids == [311]
    assert data["items"][0]["assignee_user_id"] == logged_in_user.id


# UT-DOC-009-03 담당자 필터가 unassigned인 경우 미지정 승인 대기 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_pending_documents_success_with_assignee_type_unassigned(
    client, db_session, logged_in_user
):
    """담당자 필터가 unassigned인 경우 미지정 승인 대기 문서만 조회하는지 검증한다."""
    reviewer_data = reviewer_user.copy()
    reviewer_data["password"] = auth_service.hash_password(reviewer_data["password"])
    reviewer = User(**reviewer_data)
    db_session.add(reviewer)
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
            user_id=reviewer.id,
            group_id=GROUP_ID,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=321,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="unassigned_pending_doc.pdf",
            stored_path="/tmp/test_docs/unassigned_pending_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=322,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="assigned_pending_doc.pdf",
            stored_path="/tmp/test_docs/assigned_pending_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=321,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=None,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=322,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=reviewer.id,
        )
    )
    db_session.commit()

    res = client.get(
        f"/api/groups/{GROUP_ID}/documents/pending?skip=0&limit=10&assignee_type=unassigned"
    )
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 1
    assert ids == [321]
    assert data["items"][0]["assignee_user_id"] is None


# UT-DOC-009-04 VIEWER는 승인 대기 문서 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_pending_documents_forbidden_for_viewer(client, db_session, logged_in_user):
    """VIEWER는 승인 대기 문서 목록을 조회할 수 없는지 검증한다."""
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
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/pending?skip=0&limit=10")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-DOC-009-05 비로그인 사용자는 승인 대기 문서 목록을 조회할 수 없다.
def test_get_pending_documents_unauthenticated(client):
    """비로그인 사용자는 승인 대기 문서 목록 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/pending?skip=0&limit=10")
    assert res.status_code == 401
