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
    """댓글 삭제 대상 문서와 승인 상태를 생성한다."""
    db_session.add(
        Document(
            id=doc_id,
            group_id=group_id,
            uploader_user_id=uploader_user_id,
            original_filename=f"delete_comment_doc_{doc_id}.pdf",
            stored_path=f"/tmp/test_docs/delete_comment_doc_{doc_id}.pdf",
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


# UT-DOC-018-01 댓글 작성자는 본인이 작성한 일반 댓글을 정상 삭제할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_delete_comment_success_for_author(client, db_session, logged_in_user):
    """댓글 작성자는 본인이 작성한 일반 댓글을 정상 삭제하는지 검증한다."""
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
        doc_id=1101,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    comment = _create_comment(
        db_session,
        document_id=1101,
        author_user_id=logged_in_user.id,
        content="내가 쓴 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    res = client.delete(f"/api/groups/{GROUP_ID}/comments/{comment.id}")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == comment.id
    assert data["is_deleted"] is True
    assert data["content"] == "삭제된 댓글입니다."

    deleted_comment = (
        db_session.query(DocumentComment)
        .filter(DocumentComment.id == comment.id)
        .first()
    )
    assert deleted_comment is not None
    assert deleted_comment.deleted_at is not None
    assert deleted_comment.deleted_by_user_id == logged_in_user.id


# UT-DOC-018-02 OWNER 또는 ADMIN은 다른 사용자가 작성한 댓글도 정상 삭제할 수 있다.
@pytest.mark.parametrize(
    ("logged_in_user", "member_role", "doc_id"),
    [
        (users[0], MembershipRole.OWNER, 1102),
        (users[1], MembershipRole.ADMIN, 1103),
    ],
    indirect=["logged_in_user"],
)
def test_delete_comment_success_for_owner_or_admin(
    client, db_session, logged_in_user, member_role, doc_id
):
    """OWNER 또는 ADMIN은 다른 사용자가 작성한 댓글도 정상 삭제하는지 검증한다."""
    author = _create_user(db_session, uploader_user)

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
        db_session, user_id=author.id, group_id=GROUP_ID, role=MembershipRole.EDITOR
    )
    _create_document(
        db_session,
        doc_id=doc_id,
        group_id=GROUP_ID,
        uploader_user_id=author.id,
        approval_status=ReviewStatus.APPROVED,
    )
    comment = _create_comment(
        db_session,
        document_id=doc_id,
        author_user_id=author.id,
        content="다른 사용자의 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    res = client.delete(f"/api/groups/{GROUP_ID}/comments/{comment.id}")
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == comment.id
    assert data["is_deleted"] is True
    assert data["content"] == "삭제된 댓글입니다."

    deleted_comment = (
        db_session.query(DocumentComment)
        .filter(DocumentComment.id == comment.id)
        .first()
    )
    assert deleted_comment is not None
    assert deleted_comment.deleted_at is not None
    assert deleted_comment.deleted_by_user_id == logged_in_user.id


# UT-DOC-018-03 댓글 작성자도 아니고 OWNER 또는 ADMIN도 아닌 사용자는 댓글을 삭제할 수 없다.
@pytest.mark.parametrize("logged_in_user", [editor_user], indirect=True)
def test_delete_comment_forbidden_for_non_author_non_admin(
    client, db_session, logged_in_user
):
    """댓글 작성자도 아니고 OWNER 또는 ADMIN도 아닌 사용자는 댓글 삭제가 차단되는지 검증한다."""
    owner = _create_user(db_session, users[0])
    author = _create_user(db_session, uploader_user)

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
        db_session, user_id=author.id, group_id=GROUP_ID, role=MembershipRole.EDITOR
    )
    _add_member(
        db_session,
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    _create_document(
        db_session,
        doc_id=1104,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    comment = _create_comment(
        db_session,
        document_id=1104,
        author_user_id=author.id,
        content="내가 쓴 게 아닌 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    res = client.delete(f"/api/groups/{GROUP_ID}/comments/{comment.id}")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.AUTH_FORBIDDEN.code


# UT-DOC-018-04 이미 삭제된 댓글은 다시 삭제할 수 없다.
def test_delete_comment_conflict_for_already_deleted_comment(
    authenticated_client, db_session
):
    """이미 삭제된 댓글은 다시 삭제할 수 없는지 검증한다."""
    deleted_comment = _create_comment(
        db_session,
        document_id=101,
        author_user_id=1,
        content="이미 삭제된 댓글",
        scope="GENERAL",
        deleted=True,
    )
    db_session.commit()

    res = authenticated_client.delete(
        f"/api/groups/{GROUP_ID}/comments/{deleted_comment.id}"
    )
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.COMMENT_ALREADY_DELETED.code


# UT-DOC-018-05 다른 그룹의 댓글은 삭제할 수 없다.
def test_delete_comment_not_found_for_other_group_comment(
    authenticated_client, db_session
):
    """다른 그룹의 댓글은 삭제할 수 없는지 검증한다."""
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
        doc_id=1105,
        group_id=other_group_id,
        uploader_user_id=2,
        approval_status=ReviewStatus.APPROVED,
    )
    comment = _create_comment(
        db_session,
        document_id=1105,
        author_user_id=2,
        content="다른 그룹 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/comments/{comment.id}")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-018-06 비로그인 사용자는 댓글을 삭제할 수 없다.
def test_delete_comment_unauthenticated(client, db_session):
    """비로그인 사용자는 댓글 삭제가 차단되는지 검증한다."""
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
        doc_id=1106,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    comment = _create_comment(
        db_session,
        document_id=1106,
        author_user_id=owner.id,
        content="비로그인 삭제 테스트 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    res = client.delete(f"/api/groups/{GROUP_ID}/comments/{comment.id}")
    assert res.status_code == 401
