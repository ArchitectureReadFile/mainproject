import pytest

from errors import ErrorCode
from models.model import (
    Document,
    DocumentApproval,
    DocumentComment,
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


def _create_user(db_session, user_data: dict) -> User:
    """테스트용 사용자를 생성한다."""
    payload = user_data.copy()
    payload["password"] = auth_service.hash_password(payload["password"])
    user = User(**payload)
    db_session.add(user)
    db_session.flush()
    return user


def _create_group(db_session, owner_user_id: int) -> None:
    """활성 상태의 테스트 워크스페이스를 생성한다."""
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


def _add_member(
    db_session,
    *,
    user_id: int,
    role: MembershipRole,
    group_id: int = GROUP_ID,
) -> None:
    """워크스페이스 멤버십을 추가한다."""
    db_session.add(
        GroupMember(
            user_id=user_id,
            group_id=group_id,
            role=role,
            status=MembershipStatus.ACTIVE,
        )
    )


def _create_document(
    db_session,
    *,
    doc_id: int,
    uploader_user_id: int,
    approval_status: ReviewStatus,
    group_id: int = GROUP_ID,
) -> None:
    """댓글 작성 대상 문서와 승인 상태를 생성한다."""
    db_session.add(
        Document(
            id=doc_id,
            group_id=group_id,
            uploader_user_id=uploader_user_id,
            original_filename=f"comment_doc_{doc_id}.pdf",
            stored_path=f"/tmp/test_docs/comment_doc_{doc_id}.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
    )
    db_session.add(
        DocumentApproval(
            document_id=doc_id,
            status=approval_status,
        )
    )


def _build_root_comment_payload(content: str, scope: str) -> dict:
    """루트 댓글 작성 payload를 생성한다."""
    return {
        "content": content,
        "scope": scope,
        "page": 1,
        "x": 0.12,
        "y": 0.34,
        "mentions": [],
    }


# UT-DOC-015-01 문서 조회 권한이 있는 워크스페이스 멤버는 문서에 일반 댓글을 정상 작성할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_create_general_comment_success_for_workspace_member(
    client, db_session, logged_in_user
):
    """문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글을 정상 작성하는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(db_session, owner.id)
    _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)
    _add_member(db_session, user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    _create_document(
        db_session,
        doc_id=801,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    db_session.commit()

    payload = _build_root_comment_payload("일반 댓글입니다.", "GENERAL")

    res = client.post(f"/api/groups/{GROUP_ID}/documents/801/comments", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["document_id"] == 801
    assert data["scope"] == "GENERAL"
    assert data["content"] == "일반 댓글입니다."
    assert data["author"]["id"] == logged_in_user.id
    assert data["author"]["username"] == logged_in_user.username

    saved_comment = (
        db_session.query(DocumentComment)
        .filter(DocumentComment.document_id == 801)
        .first()
    )
    assert saved_comment is not None
    assert saved_comment.author_user_id == logged_in_user.id
    assert saved_comment.comment_scope == "GENERAL"


# UT-DOC-015-02 OWNER 또는 ADMIN은 문서에 검토 댓글을 정상 작성할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role", "doc_id"),
    [
        (users[0], MembershipRole.OWNER, 802),
        (users[1], MembershipRole.ADMIN, 803),
    ],
    indirect=["logged_in_user"],
)
def test_create_review_comment_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role, doc_id
):
    """OWNER 또는 ADMIN은 검토 댓글을 정상 작성하는지 검증한다."""
    uploader = _create_user(db_session, uploader_user)

    if member_role == MembershipRole.OWNER:
        owner_user_id = logged_in_user.id
    else:
        owner = _create_user(db_session, users[0])
        owner_user_id = owner.id
        _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)

    _create_group(db_session, owner_user_id)
    _add_member(db_session, user_id=logged_in_user.id, role=member_role)
    _add_member(db_session, user_id=uploader.id, role=MembershipRole.VIEWER)
    _create_document(
        db_session,
        doc_id=doc_id,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    db_session.commit()

    payload = _build_root_comment_payload("검토 댓글입니다.", "REVIEW")

    res = client.post(
        f"/api/groups/{GROUP_ID}/documents/{doc_id}/comments", json=payload
    )
    assert res.status_code == 201

    data = res.json()
    assert data["document_id"] == doc_id
    assert data["scope"] == "REVIEW"
    assert data["content"] == "검토 댓글입니다."
    assert data["author"]["id"] == logged_in_user.id

    saved_comment = (
        db_session.query(DocumentComment)
        .filter(DocumentComment.document_id == doc_id)
        .first()
    )
    assert saved_comment is not None
    assert saved_comment.author_user_id == logged_in_user.id
    assert saved_comment.comment_scope == "REVIEW"


# UT-DOC-015-03 문서 업로더는 EDITOR 역할이어도 문서에 검토 댓글을 정상 작성할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_create_review_comment_success_for_uploader_even_if_editor(
    client, db_session, logged_in_user
):
    """문서 업로더는 EDITOR 역할이어도 검토 댓글을 정상 작성하는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(db_session, owner.id)
    _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)
    _add_member(db_session, user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    _create_document(
        db_session,
        doc_id=804,
        uploader_user_id=logged_in_user.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    db_session.commit()

    payload = _build_root_comment_payload("업로더 검토 댓글입니다.", "REVIEW")

    res = client.post(f"/api/groups/{GROUP_ID}/documents/804/comments", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["document_id"] == 804
    assert data["scope"] == "REVIEW"
    assert data["content"] == "업로더 검토 댓글입니다."
    assert data["author"]["id"] == logged_in_user.id

    saved_comment = (
        db_session.query(DocumentComment)
        .filter(DocumentComment.document_id == 804)
        .first()
    )
    assert saved_comment is not None
    assert saved_comment.author_user_id == logged_in_user.id
    assert saved_comment.comment_scope == "REVIEW"


# UT-DOC-015-04 OWNER, ADMIN, 업로더가 아닌 사용자는 문서에 검토 댓글을 작성할 수 없다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_create_review_comment_forbidden_for_non_owner_admin_or_uploader(
    client, db_session, logged_in_user
):
    """OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 작성이 차단되는지 검증한다."""
    owner = _create_user(db_session, users[0])
    uploader = _create_user(db_session, uploader_user)

    _create_group(db_session, owner.id)
    _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)
    _add_member(db_session, user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    _add_member(db_session, user_id=uploader.id, role=MembershipRole.VIEWER)
    _create_document(
        db_session,
        doc_id=805,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    db_session.commit()

    payload = _build_root_comment_payload("권한 없는 검토 댓글입니다.", "REVIEW")

    res = client.post(f"/api/groups/{GROUP_ID}/documents/805/comments", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-DOC-015-05 다른 그룹의 문서에는 댓글을 작성할 수 없다.
def test_create_comment_not_found_for_other_group_document(authenticated_client):
    """다른 그룹의 문서에는 댓글을 작성할 수 없는지 검증한다."""
    payload = _build_root_comment_payload("다른 그룹 문서 댓글입니다.", "GENERAL")

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/102/comments",
        json=payload,
    )
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-015-06 비로그인 사용자는 문서 댓글을 작성할 수 없다.
def test_create_comment_unauthenticated(client):
    """비로그인 사용자는 문서 댓글 작성이 차단되는지 검증한다."""
    payload = _build_root_comment_payload("비로그인 댓글입니다.", "GENERAL")

    res = client.post(f"/api/groups/{GROUP_ID}/documents/101/comments", json=payload)
    assert res.status_code == 401
