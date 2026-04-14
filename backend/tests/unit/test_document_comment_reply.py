import pytest

from errors import ErrorCode
from models.model import DocumentComment, MembershipRole, ReviewStatus
from tests.dummy_data import editor_user_data, uploader_user_data, users

GROUP_ID = 1


def _build_reply_payload(content: str, scope: str, parent_id: int) -> dict:
    """답글 작성 payload를 생성한다."""
    return {
        "content": content,
        "scope": scope,
        "parent_id": parent_id,
        "mentions": [],
    }


# UT-DOC-016-01 문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글에 답글을 정상 작성할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_create_general_reply_success_for_workspace_member(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글에 답글을 정상 작성하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    group_member_factory(
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    document_factory(
        doc_id=901,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="reply_doc",
    )
    parent_comment = comment_factory(
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
    """OWNER 또는 ADMIN은 검토 댓글에 답글을 정상 작성하는지 검증한다."""
    uploader = user_factory(uploader_user_data)

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
        user_id=uploader.id,
        group_id=GROUP_ID,
        role=MembershipRole.VIEWER,
    )
    document_factory(
        doc_id=doc_id,
        group_id=GROUP_ID,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
        filename_prefix="reply_doc",
    )
    parent_comment = comment_factory(
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_create_review_reply_success_for_uploader_even_if_editor(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """문서 업로더는 EDITOR 역할이어도 검토 댓글에 답글을 정상 작성하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    group_member_factory(
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    document_factory(
        doc_id=904,
        group_id=GROUP_ID,
        uploader_user_id=logged_in_user.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
        filename_prefix="reply_doc",
    )
    parent_comment = comment_factory(
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_create_review_reply_forbidden_for_non_owner_admin_or_uploader(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 답글 작성이 차단되는지 검증한다."""
    owner = user_factory(users[0])
    uploader = user_factory(uploader_user_data)

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    group_member_factory(
        user_id=logged_in_user.id,
        group_id=GROUP_ID,
        role=MembershipRole.EDITOR,
    )
    group_member_factory(
        user_id=uploader.id,
        group_id=GROUP_ID,
        role=MembershipRole.VIEWER,
    )
    document_factory(
        doc_id=905,
        group_id=GROUP_ID,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="reply_doc",
    )
    parent_comment = comment_factory(
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
    authenticated_client, db_session, comment_factory
):
    """대댓글에는 추가 답글을 작성할 수 없는지 검증한다."""
    parent_comment = comment_factory(
        document_id=101,
        author_user_id=1,
        content="루트 댓글",
        scope="GENERAL",
    )
    child_reply = comment_factory(
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
    authenticated_client, db_session, comment_factory
):
    """삭제된 댓글에는 답글을 작성할 수 없는지 검증한다."""
    deleted_parent = comment_factory(
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
    authenticated_client,
    db_session,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """다른 그룹 또는 다른 문서의 댓글에는 답글을 작성할 수 없는지 검증한다."""
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
        doc_id=906,
        group_id=other_group_id,
        uploader_user_id=2,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="reply_doc",
    )
    foreign_group_parent = comment_factory(
        document_id=906,
        author_user_id=2,
        content="다른 그룹 문서 댓글",
        scope="GENERAL",
    )

    document_factory(
        doc_id=907,
        group_id=GROUP_ID,
        uploader_user_id=1,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="reply_doc",
    )
    other_document_parent = comment_factory(
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
def test_create_reply_unauthenticated(
    client,
    db_session,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """비로그인 사용자는 문서 답글 작성이 차단되는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(group_id=GROUP_ID, owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, group_id=GROUP_ID, role=MembershipRole.OWNER)
    document_factory(
        doc_id=907,
        group_id=GROUP_ID,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
        filename_prefix="reply_doc",
    )
    parent_comment = comment_factory(
        document_id=907,
        author_user_id=owner.id,
        content="비로그인 테스트용 루트 댓글",
        scope="GENERAL",
    )
    db_session.commit()

    payload = _build_reply_payload("비로그인 답글", "GENERAL", parent_comment.id)

    res = client.post(f"/api/groups/{GROUP_ID}/documents/907/comments", json=payload)
    assert res.status_code == 401
