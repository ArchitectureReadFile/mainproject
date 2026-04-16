import pytest

from domains.auth.service import AuthService
from domains.document.upload_service import UploadService, process_next_pending_document
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

admin_user = {
    "id": 4,
    "email": "review_admin@example.com",
    "username": "검토관리자",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}

viewer_user = {
    "id": 5,
    "email": "viewer@example.com",
    "username": "뷰어멤버",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}

non_member_user = {
    "id": 6,
    "email": "outsider@example.com",
    "username": "외부사용자",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}

other_admin_user = {
    "id": 7,
    "email": "other_admin@example.com",
    "username": "다른관리자",
    "password": "password123!",
    "role": "GENERAL",
    "is_active": True,
}


# UT-DOC-014-01 EDITOR는 OWNER 또는 ADMIN을 담당자로 지정하여 문서를 정상 업로드할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "assignee_role"),
    [
        (editor_user, MembershipRole.OWNER),
        (editor_user, MembershipRole.ADMIN),
    ],
    indirect=["logged_in_user"],
)
def test_upload_document_success_with_assignee_owner_or_admin(
    client, db_session, logged_in_user, assignee_role, monkeypatch, tmp_path
):
    """EDITOR는 OWNER 또는 ADMIN을 담당자로 지정하여 문서를 정상 업로드하는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)

    admin_data = admin_user.copy()
    admin_data["password"] = auth_service.hash_password(admin_data["password"])
    admin = User(**admin_data)
    db_session.add(admin)
    db_session.flush()

    assignee_user_id = owner.id if assignee_role == MembershipRole.OWNER else admin.id

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
            user_id=admin.id,
            group_id=GROUP_ID,
            role=MembershipRole.ADMIN,
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
    db_session.commit()

    files = {
        "file": ("assigned_doc.pdf", b"%PDF-1.4 assigned upload", "application/pdf")
    }
    data = {"assignee_user_id": str(assignee_user_id)}

    res = client.post(
        f"/api/groups/{GROUP_ID}/documents/upload", files=files, data=data
    )
    assert res.status_code == 200

    payload = res.json()
    assert payload["message"] == "업로드 완료, AI 처리 대기 중"
    assert len(payload["document_ids"]) == 1

    document = (
        db_session.query(Document)
        .filter(Document.id == payload["document_ids"][0])
        .first()
    )
    assert document is not None
    assert document.uploader_user_id == logged_in_user.id

    approval = (
        db_session.query(DocumentApproval)
        .filter(DocumentApproval.document_id == document.id)
        .first()
    )
    assert approval is not None
    assert approval.status == ReviewStatus.PENDING_REVIEW
    assert approval.assignee_user_id == assignee_user_id
    assert approval.reviewer_user_id is None


# UT-DOC-014-02 담당자로 지정된 OWNER 또는 ADMIN은 assignee_type이 mine인 경우 본인에게 지정된 승인 대기 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_get_pending_documents_success_for_assignee_mine(
    client, db_session, logged_in_user
):
    """담당자로 지정된 OWNER 또는 ADMIN은 assignee_type이 mine인 경우 본인에게 지정된 승인 대기 문서만 조회하는지 검증한다."""
    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)

    other_admin_data = other_admin_user.copy()
    other_admin_data["password"] = auth_service.hash_password(
        other_admin_data["password"]
    )
    other_admin = User(**other_admin_data)

    db_session.add(owner)
    db_session.add(other_admin)
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
            user_id=other_admin.id,
            group_id=GROUP_ID,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=801,
            group_id=GROUP_ID,
            uploader_user_id=owner.id,
            original_filename="mine_doc.pdf",
            stored_path="/tmp/test_docs/mine_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=802,
            group_id=GROUP_ID,
            uploader_user_id=owner.id,
            original_filename="others_doc.pdf",
            stored_path="/tmp/test_docs/others_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=801,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=logged_in_user.id,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=802,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=other_admin.id,
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
    assert ids == [801]
    assert data["items"][0]["assignee_user_id"] == logged_in_user.id


# UT-DOC-014-03 담당자가 지정되지 않은 승인 대기 문서는 assignee_type이 unassigned인 경우에만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_get_pending_documents_success_for_unassigned_filter(
    client, db_session, logged_in_user
):
    """담당자가 지정되지 않은 승인 대기 문서는 assignee_type이 unassigned인 경우에만 조회되는지 검증한다."""
    admin_data = admin_user.copy()
    admin_data["password"] = auth_service.hash_password(admin_data["password"])
    admin = User(**admin_data)
    db_session.add(admin)
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
            user_id=admin.id,
            group_id=GROUP_ID,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )

    db_session.add(
        Document(
            id=811,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="unassigned_doc.pdf",
            stored_path="/tmp/test_docs/unassigned_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=812,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="assigned_doc.pdf",
            stored_path="/tmp/test_docs/assigned_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=811,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=None,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=812,
            status=ReviewStatus.PENDING_REVIEW,
            assignee_user_id=admin.id,
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
    assert ids == [811]
    assert data["items"][0]["assignee_user_id"] is None


# UT-DOC-014-04 그룹 멤버가 아니거나 OWNER 또는 ADMIN이 아닌 사용자는 담당자로 지정할 수 없다.
@pytest.mark.parametrize(
    (
        "assignee_fixture",
        "is_member",
        "member_role",
        "expected_status",
        "expected_code",
    ),
    [
        (non_member_user, False, None, 404, ErrorCode.GROUP_MEMBER_NOT_FOUND.code),
        (
            viewer_user,
            True,
            MembershipRole.VIEWER,
            403,
            ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code,
        ),
    ],
)
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_upload_document_fail_for_invalid_assignee(
    client,
    db_session,
    logged_in_user,
    assignee_fixture,
    is_member,
    member_role,
    expected_status,
    expected_code,
    monkeypatch,
    tmp_path,
):
    """그룹 멤버가 아니거나 OWNER 또는 ADMIN이 아닌 사용자는 담당자로 지정할 수 없는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    owner_data = users[0].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)

    assignee_data = assignee_fixture.copy()
    assignee_data["password"] = auth_service.hash_password(assignee_data["password"])
    assignee = User(**assignee_data)

    db_session.add(owner)
    db_session.add(assignee)
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

    if is_member:
        db_session.add(
            GroupMember(
                user_id=assignee.id,
                group_id=GROUP_ID,
                role=member_role,
                status=MembershipStatus.ACTIVE,
            )
        )

    db_session.commit()

    files = {
        "file": ("assigned_doc.pdf", b"%PDF-1.4 invalid assignee", "application/pdf")
    }
    data = {"assignee_user_id": str(assignee.id)}

    res = client.post(
        f"/api/groups/{GROUP_ID}/documents/upload", files=files, data=data
    )
    assert res.status_code == expected_status
    assert res.json()["code"] == expected_code


# UT-DOC-014-05 비로그인 사용자는 담당자 지정 업로드 및 담당자별 승인 대기 조회를 할 수 없다.
def test_assignee_upload_and_pending_list_unauthenticated(client):
    """비로그인 사용자는 담당자 지정 업로드 및 담당자별 승인 대기 조회가 차단되는지 검증한다."""
    files = {"file": ("assigned_doc.pdf", b"%PDF-1.4 unauth upload", "application/pdf")}
    data = {"assignee_user_id": "1"}

    upload_res = client.post(
        f"/api/groups/{GROUP_ID}/documents/upload",
        files=files,
        data=data,
    )
    assert upload_res.status_code == 401

    pending_res = client.get(
        f"/api/groups/{GROUP_ID}/documents/pending?skip=0&limit=10&assignee_type=mine"
    )
    assert pending_res.status_code == 401
