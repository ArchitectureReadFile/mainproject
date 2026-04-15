import pytest

from errors import ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    User,
)
from services.auth_service import AuthService
from services.upload.service import UploadService, process_next_pending_document
from tests.dummy_data import groups, users

auth_service = AuthService(None)

editor_user = {
    "id": 3,
    "email": "editor@example.com",
    "username": "편집자",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}


# UT-GRP-017-01 워크스페이스 멤버는 ACTIVE 상태의 워크스페이스를 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_workspace_access_success_for_active_member(client, db_session, logged_in_user):
    """워크스페이스 멤버는 ACTIVE 상태의 워크스페이스를 정상 조회하는지 검증한다."""
    db_session.add(
        Group(
            id=1,
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
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == 1
    assert data["status"] == "ACTIVE"
    assert data["my_role"] == "OWNER"


# UT-GRP-017-02 DELETE_PENDING 상태의 워크스페이스는 멤버가 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_workspace_access_success_for_delete_pending_member(
    client, db_session, logged_in_user
):
    """DELETE_PENDING 상태의 워크스페이스는 멤버가 정상 조회하는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="삭제 대기 워크스페이스",
            description="접근 권한 테스트",
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == 1
    assert data["status"] == "DELETE_PENDING"
    assert data["pending_reason"] == "OWNER_DELETE_REQUEST"


# UT-GRP-017-03 BLOCKED 상태의 워크스페이스는 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_workspace_access_forbidden_for_blocked_group(
    client, db_session, logged_in_user
):
    """BLOCKED 상태의 워크스페이스는 조회할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="차단된 워크스페이스",
            description="접근 권한 테스트",
            status=GroupStatus.BLOCKED,
            pending_reason=GroupPendingReason.SUBSCRIPTION_EXPIRED,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code


# UT-GRP-017-04 비멤버는 워크스페이스를 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_workspace_access_not_found_for_non_member(client, db_session, logged_in_user):
    """비멤버는 워크스페이스를 조회할 수 없는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.GROUP_NOT_FOUND.code


# UT-GRP-017-05 OWNER 또는 ADMIN은 승인 목록을 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
@pytest.mark.parametrize("member_role", [MembershipRole.OWNER, MembershipRole.ADMIN])
def test_review_access_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role
):
    """OWNER 또는 ADMIN은 승인 목록을 정상 조회하는지 검증한다."""
    if member_role == MembershipRole.OWNER:
        group_owner_id = logged_in_user.id
    else:
        owner_data = users[1].copy()
        owner_data["password"] = auth_service.hash_password(owner_data["password"])
        owner = User(**owner_data)
        db_session.add(owner)
        db_session.flush()
        group_owner_id = owner.id
        db_session.add(
            GroupMember(
                user_id=owner.id,
                group_id=1,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )

    db_session.add(
        Group(
            id=1,
            owner_user_id=group_owner_id,
            name="리뷰 워크스페이스",
            description="승인 목록 권한 테스트",
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1/documents/pending")
    assert res.status_code == 200

    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


# UT-GRP-017-06 VIEWER는 승인 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_review_access_forbidden_for_viewer(client, db_session, logged_in_user):
    """VIEWER는 승인 목록을 조회할 수 없는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="리뷰 워크스페이스",
            description="승인 목록 권한 테스트",
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get("/api/groups/1/documents/pending")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-GRP-017-07 OWNER, ADMIN, EDITOR는 ACTIVE 워크스페이스에 문서를 업로드할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role"),
    [
        (users[0], MembershipRole.OWNER),
        (users[1], MembershipRole.ADMIN),
        (editor_user, MembershipRole.EDITOR),
    ],
    indirect=["logged_in_user"],
)
def test_upload_access_success_for_owner_admin_editor(
    client, db_session, logged_in_user, member_role, monkeypatch, tmp_path
):
    """OWNER, ADMIN, EDITOR는 ACTIVE 워크스페이스에 문서를 업로드할 수 있는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    if member_role == MembershipRole.OWNER:
        group_owner_id = logged_in_user.id
    else:
        owner_data = users[0].copy()
        owner_data["password"] = auth_service.hash_password(owner_data["password"])
        owner = User(**owner_data)
        db_session.add(owner)
        db_session.flush()
        group_owner_id = owner.id
        db_session.add(
            GroupMember(
                user_id=owner.id,
                group_id=1,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )

    db_session.add(
        Group(
            id=1,
            owner_user_id=group_owner_id,
            name="업로드 워크스페이스",
            description="업로드 권한 테스트",
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    files = {"file": ("sample.pdf", b"%PDF-1.4 test content", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 200

    data = res.json()
    assert data["message"] == "업로드 완료, AI 처리 대기 중"
    assert len(data["document_ids"]) == 1


# UT-GRP-017-08 VIEWER는 문서를 업로드할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_upload_access_forbidden_for_viewer(
    client, db_session, logged_in_user, monkeypatch, tmp_path
):
    """VIEWER는 문서를 업로드할 수 없는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name="업로드 워크스페이스",
            description="업로드 권한 테스트",
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    files = {"file": ("sample.pdf", b"%PDF-1.4 test content", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-GRP-017-09 비활성 상태의 워크스페이스에는 문서를 업로드할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_upload_access_forbidden_for_non_active_group(
    client, db_session, logged_in_user, monkeypatch, tmp_path
):
    """비활성 상태의 워크스페이스에는 문서를 업로드할 수 없는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name="비활성 워크스페이스",
            description="업로드 권한 테스트",
            status=GroupStatus.DELETE_PENDING,
            pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        )
    )
    db_session.flush()
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    files = {"file": ("sample.pdf", b"%PDF-1.4 test content", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code
