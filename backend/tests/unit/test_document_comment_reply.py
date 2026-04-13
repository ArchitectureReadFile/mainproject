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
    utc_now_naive,
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


def _create_group(
    db_session, *, group_id: int, owner_user_id: int, group_data: dict
) -> None:
    """활성 상태의 테스트 워크스페이스를 생성한다."""
    db_session.add(
        Group(
            id=group_id,
            owner_user_id=owner_user_id,
            name=group_data["name"],
            description=group_data["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()


def _add_member(
    db_session,
    *,
    user_id: int,
    group_id: int,
    role: MembershipRole,
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
    group_id: int,
    uploader_user_id: int,
    approval_status: ReviewStatus,
) -> None:
    """댓글 작성 대상 문서와 승인 상태를 생성한다."""
    db_session.add(
        Document(
            id=doc_id,
            group_id=group_id,
            uploader_user_id=uploader_user_id,
            original_filename=f"reply_doc_{doc_id}.pdf",
            stored_path=f"/tmp/test_docs/reply_doc_{doc_id}.pdf",
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
    deleted: bool = False,
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
        deleted_at=utc_now_naive() if deleted else None,
    )
    db_session.add(comment)
    db_session.flush()
    return comment


def _build_reply_payload(content: str, scope: str, parent_id: int) -> dict:
    """답글 작성 payload를 생성한다."""
    return {
        "content": content,
        "scope": scope,
        "parent_id": parent_id,
        "mentions": [],
    }


# UT-DOC-016-01 문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글에 답글을 정상 작성할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_create_general_reply_success_for_workspace_member(
    client, db_session, logged_in_user
):
    """문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글에 답글을 정상 작성하는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(
        db_session,
        group_id=GROUP_ID,
        owner_user_id=owner.id,
        group_data=groups[0],
    )
    _add_member(
        db_session, user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER
    )
    _add_member(
        db_session,
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    _create_document(
        db_session,
        doc_id=901,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    parent_comment = _create_comment(
        db_session,
        document_id=901,
        author_user_id=owner.id,
        content="루트 일반 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    payload = _build_reply_payload("일반 답글입니다.", "GENERAL", parent_comment.id)

    res = client.post(f"/api/groups/{GROUP_ID}/documents/901/comments", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["document_id"] == 901
    assert data["parent_id"] == parent_comment.id
    assert data["scope"] == "GENERAL"
    assert data["content"] == "일반 답글입니다."
    assert data["author"]["id"] == logged_in_user.id

    saved_reply = (
        db_session.query(DocumentComment)
        .filter(
            DocumentComment.document_id == 901,
            DocumentComment.parent_id == parent_comment.id,
        )
        .first()
    )
    assert saved_reply is not None
    assert saved_reply.author_user_id == logged_in_user.id
    assert saved_reply.comment_scope == "GENERAL"


# UT-DOC-016-02 OWNER 또는 ADMIN은 검토 댓글에 답글을 정상 작성할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role", "doc_id"),
    [
        (users[0], MembershipRole.OWNER, 902),
        (users[1], MembershipRole.ADMIN, 903),
    ],
    indirect=["logged_in_user"],
)
def test_create_review_reply_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role, doc_id
):
    """OWNER 또는 ADMIN은 검토 댓글에 답글을 정상 작성하는지 검증한다."""
    uploader = _create_user(db_session, uploader_user)

    if member_role == MembershipRole.OWNER:
        owner_user_id = logged_in_user.id
    else:
        owner = _create_user(db_session, users[0])
        owner_user_id = owner.id
        _add_member(
            db_session, user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER
        )

    _create_group(
        db_session,
        group_id=GROUP_ID,
        owner_user_id=owner_user_id,
        group_data=groups[0],
    )
    _add_member(
        db_session, user_id=logged_in_user.id, group_id=GROUP_ID, role=member_role
    )
    _add_member(
        db_session, user_id=uploader.id, group_id=GROUP_ID, role=MembershipRole.VIEWER
    )
    _create_document(
        db_session,
        doc_id=doc_id,
        group_id=GROUP_ID,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    parent_comment = _create_comment(
        db_session,
        document_id=doc_id,
        author_user_id=uploader.id,
        content="루트 검토 댓글",
        scope="REVIEW",
    )
    db_session.commit()

    payload = _build_reply_payload("검토 답글입니다.", "REVIEW", parent_comment.id)

    res = client.post(
        f"/api/groups/{GROUP_ID}/documents/{doc_id}/comments", json=payload
    )
    assert res.status_code == 201

    data = res.json()
    assert data["document_id"] == doc_id
    assert data["parent_id"] == parent_comment.id
    assert data["scope"] == "REVIEW"
    assert data["content"] == "검토 답글입니다."
    assert data["author"]["id"] == logged_in_user.id


# UT-DOC-016-03 문서 업로더는 EDITOR 역할이어도 검토 댓글에 답글을 정상 작성할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_create_review_reply_success_for_uploader_even_if_editor(
    client, db_session, logged_in_user
):
    """문서 업로더는 EDITOR 역할이어도 검토 댓글에 답글을 정상 작성하는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(
        db_session,
        group_id=GROUP_ID,
        owner_user_id=owner.id,
        group_data=groups[0],
    )
    _add_member(
        db_session, user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER
    )
    _add_member(
        db_session,
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    _create_document(
        db_session,
        doc_id=904,
        group_id=GROUP_ID,
        uploader_user_id=logged_in_user.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    parent_comment = _create_comment(
        db_session,
        document_id=904,
        author_user_id=owner.id,
        content="업로더 대상 검토 댓글",
        scope="REVIEW",
    )
    db_session.commit()

    payload = _build_reply_payload(
        "업로더 검토 답글입니다.", "REVIEW", parent_comment.id
    )

    res = client.post(f"/api/groups/{GROUP_ID}/documents/904/comments", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["document_id"] == 904
    assert data["parent_id"] == parent_comment.id
    assert data["scope"] == "REVIEW"
    assert data["author"]["id"] == logged_in_user.id


# UT-DOC-016-04 OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글에 답글을 작성할 수 없다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_create_review_reply_forbidden_for_non_owner_admin_or_uploader(
    client, db_session, logged_in_user
):
    """OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 답글 작성이 차단되는지 검증한다."""
    owner = _create_user(db_session, users[0])
    uploader = _create_user(db_session, uploader_user)

    _create_group(
        db_session,
        group_id=GROUP_ID,
        owner_user_id=owner.id,
        group_data=groups[0],
    )
    _add_member(
        db_session, user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER
    )
    _add_member(
        db_session,
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    _add_member(
        db_session, user_id=uploader.id, group_id=GROUP_ID, role=MembershipRole.VIEWER
    )
    _create_document(
        db_session,
        doc_id=905,
        group_id=GROUP_ID,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.APPROVED,
    )
    parent_comment = _create_comment(
        db_session,
        document_id=905,
        author_user_id=owner.id,
        content="권한 없는 사용자 대상 검토 댓글",
        scope="REVIEW",
    )
    db_session.commit()

    payload = _build_reply_payload(
        "권한 없는 검토 답글입니다.", "REVIEW", parent_comment.id
    )

    res = client.post(f"/api/groups/{GROUP_ID}/documents/905/comments", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-DOC-016-05 대댓글에는 추가 답글을 작성할 수 없다.
def test_create_reply_conflict_for_reply_depth_exceeded(
    authenticated_client, db_session
):
    """대댓글에는 추가 답글을 작성할 수 없는지 검증한다."""
    parent_comment = _create_comment(
        db_session,
        document_id=101,
        author_user_id=1,
        content="루트 댓글",
        scope="GENERAL",
    )
    child_reply = _create_comment(
        db_session,
        document_id=101,
        author_user_id=1,
        content="기존 답글",
        scope="GENERAL",
        parent_id=parent_comment.id,
    )
    db_session.commit()

    payload = _build_reply_payload("대댓글의 답글 시도", "GENERAL", child_reply.id)

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/101/comments",
        json=payload,
    )
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.COMMENT_REPLY_DEPTH_EXCEEDED.code


# UT-DOC-016-06 삭제된 댓글에는 답글을 작성할 수 없다.
def test_create_reply_conflict_for_deleted_parent_comment(
    authenticated_client, db_session
):
    deleted_parent = _create_comment(
        db_session,
        document_id=101,
        author_user_id=1,
        content="삭제된 루트 댓글",
        scope="GENERAL",
        deleted=True,
    )
    db_session.commit()

    payload = _build_reply_payload("삭제 댓글 답글 시도", "GENERAL", deleted_parent.id)

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/101/comments",
        json=payload,
    )
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.COMMENT_PARENT_DELETED.code


# UT-DOC-016-07 다른 그룹 또는 다른 문서의 댓글에는 답글을 작성할 수 없다.
def test_create_reply_bad_request_for_comment_of_other_group_or_document(
    authenticated_client, db_session
):
    """다른 그룹 또는 다른 문서의 댓글에는 답글을 작성할 수 없는지 검증한다."""
    other_group_id = 99

    _create_group(
        db_session,
        group_id=other_group_id,
        owner_user_id=2,
        group_data={
            "name": "다른 워크스페이스",
            "description": "다른 그룹 테스트용",
        },
    )
    _add_member(
        db_session,
        user_id=2,
        group_id=other_group_id,
        role=MembershipRole.OWNER,
    )
    _create_document(
        db_session,
        doc_id=906,
        group_id=other_group_id,
        uploader_user_id=2,
        approval_status=ReviewStatus.APPROVED,
    )
    foreign_group_parent = _create_comment(
        db_session,
        document_id=906,
        author_user_id=2,
        content="다른 그룹 문서 댓글",
        scope="GENERAL",
    )

    _create_document(
        db_session,
        doc_id=907,
        group_id=GROUP_ID,
        uploader_user_id=1,
        approval_status=ReviewStatus.APPROVED,
    )
    other_document_parent = _create_comment(
        db_session,
        document_id=907,
        author_user_id=1,
        content="같은 그룹 다른 문서 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    foreign_group_payload = _build_reply_payload(
        "다른 그룹 댓글 답글 시도",
        "GENERAL",
        foreign_group_parent.id,
    )
    other_document_payload = _build_reply_payload(
        "다른 문서 댓글 답글 시도",
        "GENERAL",
        other_document_parent.id,
    )

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/101/comments",
        json=foreign_group_payload,
    )
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.COMMENT_PARENT_MISMATCH.code

    res = authenticated_client.post(
        f"/api/groups/{GROUP_ID}/documents/101/comments",
        json=other_document_payload,
    )
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.COMMENT_PARENT_MISMATCH.code


# UT-DOC-016-08 비로그인 사용자는 문서 답글을 작성할 수 없다.
def test_create_reply_unauthenticated(client, db_session):
    """비로그인 사용자는 문서 답글 작성이 차단되는지 검증한다."""
    owner = _create_user(db_session, users[0])

    _create_group(
        db_session,
        group_id=GROUP_ID,
        owner_user_id=owner.id,
        group_data=groups[0],
    )
    _add_member(
        db_session, user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER
    )
    _create_document(
        db_session,
        doc_id=907,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    parent_comment = _create_comment(
        db_session,
        document_id=907,
        author_user_id=owner.id,
        content="비로그인 테스트용 루트 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    payload = _build_reply_payload("비로그인 답글", "GENERAL", parent_comment.id)

    res = client.post(f"/api/groups/{GROUP_ID}/documents/907/comments", json=payload)
    assert res.status_code == 401
