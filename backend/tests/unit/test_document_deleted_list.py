import pytest

from models.model import (
    Document,
    DocumentLifecycleStatus,
    DocumentStatus,
    Group,
    GroupMember,
    MembershipRole,
    MembershipStatus,
    User,
    utc_now_naive,
)
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)

GROUP_ID = 1


# UT-DOC-007-01 문서 업로더는 본인의 삭제 요청 문서 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_deleted_documents_success_for_uploader(client, db_session, logged_in_user):
    """문서 업로더는 본인의 삭제 요청 문서 목록을 정상 조회하는지 검증한다."""
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
            original_filename="deleted_my_doc.pdf",
            stored_path="/tmp/test_docs/deleted_my_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.DELETE_PENDING,
            delete_requested_at=now,
        )
    )
    db_session.add(
        Document(
            id=102,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="active_my_doc.pdf",
            stored_path="/tmp/test_docs/active_my_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/deleted?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 1
    assert ids == [101]


# UT-DOC-007-02 그룹 OWNER 또는 ADMIN은 그룹 내 전체 삭제 요청 문서 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_get_deleted_documents_success_for_group_admin(
    client, db_session, logged_in_user
):
    """그룹 OWNER 또는 ADMIN은 그룹 내 전체 삭제 요청 문서 목록을 정상 조회하는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    target_user_data = {
        "id": 3,
        "email": "member@example.com",
        "username": "일반멤버",
        "password": auth_service.hash_password("password123!"),
        "role": "GENERAL",
        "is_active": True,
    }
    target_user = User(**target_user_data)
    db_session.add(target_user)
    db_session.flush()

    now = utc_now_naive()

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
        GroupMember(
            user_id=target_user.id,
            group_id=GROUP_ID,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )

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
        )
    )
    db_session.add(
        Document(
            id=202,
            group_id=GROUP_ID,
            uploader_user_id=target_user.id,
            original_filename="deleted_member_doc.pdf",
            stored_path="/tmp/test_docs/deleted_member_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.DELETE_PENDING,
            delete_requested_at=now,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/deleted?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert data["total"] == 2
    assert set(ids) == {201, 202}


# UT-DOC-007-03 삭제 요청 상태의 문서가 없는 경우 빈 목록을 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_deleted_documents_empty(client, db_session, logged_in_user):
    """삭제 요청 상태의 문서가 없는 경우 빈 목록을 정상 조회하는지 검증한다."""
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
            id=301,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="active_doc.pdf",
            stored_path="/tmp/test_docs/active_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/deleted?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


# UT-DOC-007-04 비로그인 사용자는 삭제 문서 목록을 조회할 수 없다.
def test_get_deleted_documents_unauthenticated(client):
    """비로그인 사용자는 삭제 문서 목록 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/deleted?skip=0&limit=10")
    assert res.status_code == 401
