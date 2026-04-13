import pytest

from errors import ErrorCode
from models.model import DocumentComment, MembershipRole, ReviewStatus
from tests.dummy_data import editor_user_data, uploader_user_data, users

GROUP_ID = 1


# UT-DOC-018-01 댓글 작성자는 본인이 작성한 일반 댓글을 정상 삭제할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_delete_comment_success_for_author(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """댓글 작성자는 본인이 작성한 일반 댓글을 정상 삭제하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    group_member_factory(
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    document_factory(
        doc_id=1101,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="delete_comment_doc",
    )
    comment = comment_factory(
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
    client,
    db_session,
    logged_in_user,
    member_role,
    doc_id,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """OWNER 또는 ADMIN은 다른 사용자가 작성한 댓글도 정상 삭제하는지 검증한다."""
    author = user_factory(uploader_user_data)

    if member_role == MembershipRole.OWNER:
        owner_user_id = logged_in_user.id
    else:
        owner = user_factory(users[0])
        owner_user_id = owner.id
        group_member_factory(
            user_id=owner.id,
            group_id=GROUP_ID,
            role=MembershipRole.OWNER,
        )

    group_factory(group_id=GROUP_ID, owner_user_id=owner_user_id)
    group_member_factory(
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=member_role,
    )
    group_member_factory(
        user_id=author.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    document_factory(
        doc_id=doc_id,
        group_id=GROUP_ID,
        uploader_user_id=author.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="delete_comment_doc",
    )
    comment = comment_factory(
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_delete_comment_forbidden_for_non_author_non_admin(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """댓글 작성자도 아니고 OWNER 또는 ADMIN도 아닌 사용자는 댓글 삭제가 차단되는지 검증한다."""
    owner = user_factory(users[0])
    author = user_factory(uploader_user_data)

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    group_member_factory(
        user_id=author.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    group_member_factory(
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    document_factory(
        doc_id=1104,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="delete_comment_doc",
    )
    comment = comment_factory(
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
    authenticated_client, db_session, comment_factory
):
    """이미 삭제된 댓글은 다시 삭제할 수 없는지 검증한다."""
    deleted_comment = comment_factory(
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
    authenticated_client,
    db_session,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """다른 그룹의 댓글은 삭제할 수 없는지 검증한다."""
    other_group_id = 99

    group_factory(
        group_id=other_group_id,
        owner_user_id=2,
        name="다른 워크스페이스",
        description="다른 그룹 테스트용",
    )
    group_member_factory(
        user_id=2,
        group_id=other_group_id,
        role=MembershipRole.OWNER,
    )
    document_factory(
        doc_id=1105,
        group_id=other_group_id,
        uploader_user_id=2,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="delete_comment_doc",
    )
    comment = comment_factory(
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
def test_delete_comment_unauthenticated(
    client,
    db_session,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """비로그인 사용자는 댓글 삭제가 차단되는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    document_factory(
        doc_id=1106,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="delete_comment_doc",
    )
    comment = comment_factory(
        document_id=1106,
        author_user_id=owner.id,
        content="비로그인 삭제 테스트 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    res = client.delete(f"/api/groups/{GROUP_ID}/comments/{comment.id}")
    assert res.status_code == 401
