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


def _create_group(db_session, *, owner_user_id: int) -> None:
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
    """댓글 조회 대상 문서와 승인 상태를 생성한다."""
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


def _create_comment(
    db_session,
    *,
    document_id: int,
    author_user_id: int,
    content: str,
    scope: str,
    parent_id: int | None = None,
) -> DocumentComment:
    """문서 댓글 또는 답글을 DB에 직접 생성한다."""
    comment = DocumentComment(
        document_id=document_id,
        author_user_id=author_user_id,
        parent_id=parent_id,
        content=content,
        comment_scope=scope,
        page=1 if parent_id is None else None,
        x=0.11 if parent_id is None else None,
        y=0.22 if parent_id is None else None,
    )
    db_session.add(comment)
    db_session.flush()
    return comment


# UT-DOC-017-01 문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_list_general_comments_success_for_workspace_member(
    client, db_session, logged_in_user
):
    """문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글 목록을 정상 조회하는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(db_session, owner_user_id=owner.id)
    _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)
    _add_member(db_session, user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    _create_document(
        db_session,
        doc_id=1001,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    _create_comment(
        db_session,
        document_id=1001,
        author_user_id=owner.id,
        content="일반 댓글입니다.",
        scope="GENERAL",
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/1001/comments?scope=GENERAL")
    assert res.status_code == 200

    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["document_id"] == 1001
    assert data["items"][0]["scope"] == "GENERAL"
    assert data["items"][0]["content"] == "일반 댓글입니다."


# UT-DOC-017-02 OWNER 또는 ADMIN은 검토 댓글 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role", "doc_id"),
    [
        (users[0], MembershipRole.OWNER, 1002),
        (users[1], MembershipRole.ADMIN, 1003),
    ],
    indirect=["logged_in_user"],
)
def test_list_review_comments_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role, doc_id
):
    """OWNER 또는 ADMIN은 검토 댓글 목록을 정상 조회하는지 검증한다."""
    uploader = _create_user(db_session, uploader_user)

    if member_role == MembershipRole.OWNER:
        owner_user_id = logged_in_user.id
    else:
        owner = _create_user(db_session, users[0])
        owner_user_id = owner.id
        _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)

    _create_group(db_session, owner_user_id=owner_user_id)
    _add_member(db_session, user_id=logged_in_user.id, role=member_role)
    _add_member(db_session, user_id=uploader.id, role=MembershipRole.VIEWER)
    _create_document(
        db_session,
        doc_id=doc_id,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    _create_comment(
        db_session,
        document_id=doc_id,
        author_user_id=uploader.id,
        content="검토 댓글입니다.",
        scope="REVIEW",
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/{doc_id}/comments?scope=REVIEW")
    assert res.status_code == 200

    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["document_id"] == doc_id
    assert data["items"][0]["scope"] == "REVIEW"
    assert data["items"][0]["content"] == "검토 댓글입니다."


# UT-DOC-017-03 문서 업로더는 EDITOR 역할이어도 검토 댓글 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_list_review_comments_success_for_uploader_even_if_editor(
    client, db_session, logged_in_user
):
    """문서 업로더는 EDITOR 역할이어도 검토 댓글 목록을 정상 조회하는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(db_session, owner_user_id=owner.id)
    _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)
    _add_member(db_session, user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    _create_document(
        db_session,
        doc_id=1004,
        uploader_user_id=logged_in_user.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    _create_comment(
        db_session,
        document_id=1004,
        author_user_id=owner.id,
        content="업로더 대상 검토 댓글입니다.",
        scope="REVIEW",
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/1004/comments?scope=REVIEW")
    assert res.status_code == 200

    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["document_id"] == 1004
    assert data["items"][0]["scope"] == "REVIEW"
    assert data["items"][0]["content"] == "업로더 대상 검토 댓글입니다."


# UT-DOC-017-04 OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_list_review_comments_forbidden_for_non_owner_admin_or_uploader(
    client, db_session, logged_in_user
):
    """OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 목록 조회가 차단되는지 검증한다."""
    owner = _create_user(db_session, users[0])
    uploader = _create_user(db_session, uploader_user)

    _create_group(db_session, owner_user_id=owner.id)
    _add_member(db_session, user_id=owner.id, role=MembershipRole.OWNER)
    _add_member(db_session, user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    _add_member(db_session, user_id=uploader.id, role=MembershipRole.VIEWER)
    _create_document(
        db_session,
        doc_id=1005,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.APPROVED,
    )
    _create_comment(
        db_session,
        document_id=1005,
        author_user_id=owner.id,
        content="권한 없는 사용자 대상 검토 댓글입니다.",
        scope="REVIEW",
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents/1005/comments?scope=REVIEW")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-DOC-017-05 비로그인 사용자는 댓글 목록을 조회할 수 없다.
def test_list_comments_unauthenticated(client):
    """비로그인 사용자는 댓글 목록 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/101/comments?scope=GENERAL")
    assert res.status_code == 401
