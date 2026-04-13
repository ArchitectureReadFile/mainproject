import pytest

from errors import ErrorCode
from models.model import MembershipRole, ReviewStatus
from tests.dummy_data import editor_user_data, uploader_user_data, users

GROUP_ID = 1


# UT-DOC-017-01 문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_list_general_comments_success_for_workspace_member(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글 목록을 정상 조회하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)
    group_member_factory(user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    document_factory(
        doc_id=1001,
        uploader_user_id=owner.id,
        approval_status=ReviewStatus.APPROVED,
    )
    comment_factory(
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
    """OWNER 또는 ADMIN은 검토 댓글 목록을 정상 조회하는지 검증한다."""
    uploader = user_factory(uploader_user_data)

    if member_role == MembershipRole.OWNER:
        owner_user_id = logged_in_user.id
    else:
        owner = user_factory(users[0])
        owner_user_id = owner.id
        group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)

    group_factory(owner_user_id=owner_user_id)
    group_member_factory(user_id=logged_in_user.id, role=member_role)
    group_member_factory(user_id=uploader.id, role=MembershipRole.VIEWER)
    document_factory(
        doc_id=doc_id,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    comment_factory(
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_list_review_comments_success_for_uploader_even_if_editor(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """문서 업로더는 EDITOR 역할이어도 검토 댓글 목록을 정상 조회하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)
    group_member_factory(user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    document_factory(
        doc_id=1004,
        uploader_user_id=logged_in_user.id,
        approval_status=ReviewStatus.PENDING_REVIEW,
    )
    comment_factory(
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_list_review_comments_forbidden_for_non_owner_admin_or_uploader(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
    comment_factory,
):
    """OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 목록 조회가 차단되는지 검증한다."""
    owner = user_factory(users[0])
    uploader = user_factory(uploader_user_data)

    group_factory(owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)
    group_member_factory(user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    group_member_factory(user_id=uploader.id, role=MembershipRole.VIEWER)
    document_factory(
        doc_id=1005,
        uploader_user_id=uploader.id,
        approval_status=ReviewStatus.APPROVED,
    )
    comment_factory(
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
