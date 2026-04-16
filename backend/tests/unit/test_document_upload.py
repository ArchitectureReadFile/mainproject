import pytest

from domains.auth.service import AuthService
from domains.document.upload_service import UploadService, process_next_pending_document
from errors import ErrorCode
from models.model import (
    Document,
    DocumentApproval,
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
    User,
)
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


# UT-DOC-001-01 OWNER 또는 ADMIN은 문서를 정상 업로드할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0], users[1]], indirect=True)
def test_upload_document_success_for_owner_or_admin(
    client, db_session, logged_in_user, monkeypatch, tmp_path
):
    """OWNER 또는 ADMIN은 문서를 정상 업로드하는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    if logged_in_user.id == users[0]["id"]:
        owner_user_id = logged_in_user.id
        member_role = MembershipRole.OWNER
    else:
        owner_data = users[0].copy()
        owner_data["password"] = auth_service.hash_password(owner_data["password"])
        owner = User(**owner_data)
        db_session.add(owner)
        db_session.flush()
        owner_user_id = owner.id
        member_role = MembershipRole.ADMIN

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
            group_id=1,
            role=member_role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    files = {"file": ("sample.pdf", b"%PDF-1.4 owner admin upload", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 200

    data = res.json()
    assert data["message"] == "업로드 완료, AI 처리 대기 중"
    assert len(data["document_ids"]) == 1

    document = (
        db_session.query(Document)
        .filter(Document.id == data["document_ids"][0])
        .first()
    )
    assert document is not None
    assert document.original_filename == "sample.pdf"
    assert document.uploader_user_id == logged_in_user.id

    approval = (
        db_session.query(DocumentApproval)
        .filter(DocumentApproval.document_id == document.id)
        .first()
    )
    assert approval is not None
    assert approval.status == ReviewStatus.APPROVED
    assert approval.reviewer_user_id == logged_in_user.id


# UT-DOC-001-02 EDITOR는 문서를 정상 업로드할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_upload_document_success_for_editor(
    client, db_session, logged_in_user, monkeypatch, tmp_path
):
    """EDITOR는 문서를 정상 업로드하는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

    owner_data = users[0].copy()
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
            role=MembershipRole.EDITOR,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    files = {"file": ("sample.pdf", b"%PDF-1.4 editor upload", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 200

    data = res.json()
    assert data["message"] == "업로드 완료, AI 처리 대기 중"
    assert len(data["document_ids"]) == 1

    document = (
        db_session.query(Document)
        .filter(Document.id == data["document_ids"][0])
        .first()
    )
    assert document is not None
    assert document.original_filename == "sample.pdf"
    assert document.uploader_user_id == logged_in_user.id

    approval = (
        db_session.query(DocumentApproval)
        .filter(DocumentApproval.document_id == document.id)
        .first()
    )
    assert approval is not None
    assert approval.status == ReviewStatus.PENDING_REVIEW
    assert approval.assignee_user_id is None
    assert approval.reviewer_user_id is None


# UT-DOC-001-03 VIEWER는 문서를 업로드할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_upload_document_forbidden_for_viewer(
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
            name=groups[0]["name"],
            description=groups[0]["description"],
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

    files = {"file": ("sample.pdf", b"%PDF-1.4 viewer upload", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-DOC-001-04 허용되지 않은 형식의 파일은 업로드할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_upload_document_invalid_file_type(
    client, db_session, logged_in_user, monkeypatch, tmp_path
):
    """허용되지 않은 형식의 파일은 업로드할 수 없는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

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

    files = {"file": ("sample.txt", b"plain text content", "text/plain")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 415
    assert res.json()["code"] == ErrorCode.DOC_INVALID_FILE_TYPE.code


# UT-DOC-001-05 20MB를 초과하는 파일은 업로드할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_upload_document_file_too_large(
    client, db_session, logged_in_user, monkeypatch, tmp_path
):
    """20MB를 초과하는 파일은 업로드할 수 없는지 검증한다."""
    monkeypatch.setattr(UploadService, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(process_next_pending_document, "delay", lambda: None)

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

    files = {
        "file": (
            "large.pdf",
            b"0" * (20 * 1024 * 1024 + 1),
            "application/pdf",
        )
    }

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 413
    assert res.json()["code"] == ErrorCode.DOC_FILE_TOO_LARGE.code


# UT-DOC-001-06 비활성 상태의 워크스페이스에는 문서를 업로드할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_upload_document_forbidden_for_non_active_group(
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
            description="문서 업로드 테스트",
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

    files = {"file": ("sample.pdf", b"%PDF-1.4 inactive group", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ACTIVE.code


# UT-DOC-001-07 비로그인 사용자는 문서를 업로드할 수 없다.
def test_upload_document_unauthenticated(client):
    """비로그인 사용자는 문서 업로드 요청이 차단되는지 검증한다."""
    files = {"file": ("sample.pdf", b"%PDF-1.4 unauthenticated", "application/pdf")}

    res = client.post("/api/groups/1/documents/upload", files=files)
    assert res.status_code == 401
