import pytest

from errors import ErrorCode
from models.model import DocumentComment, MembershipRole, ReviewStatus
from tests.dummy_data import editor_user_data, uploader_user_data, users

GROUP_ID = 1


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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_create_general_comment_success_for_workspace_member(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
):
    """문서 조회 권한이 있는 워크스페이스 멤버는 일반 댓글을 정상 작성하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)
    group_member_factory(user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    document_factory(
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
    client,
    db_session,
    logged_in_user,
    member_role,
    doc_id,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
):
    """OWNER 또는 ADMIN은 검토 댓글을 정상 작성하는지 검증한다."""
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_create_review_comment_success_for_uploader_even_if_editor(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
):
    """문서 업로더는 EDITOR 역할이어도 검토 댓글을 정상 작성하는지 검증한다."""
    owner = user_factory(users[0])

    group_factory(owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)
    group_member_factory(user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    document_factory(
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
@pytest.mark.parametrize("logged_in_user", [editor_user_data], indirect=True)
def test_create_review_comment_forbidden_for_non_owner_admin_or_uploader(
    client,
    db_session,
    logged_in_user,
    user_factory,
    group_factory,
    group_member_factory,
    document_factory,
):
    """OWNER, ADMIN, 업로더가 아닌 사용자는 검토 댓글 작성이 차단되는지 검증한다."""
    owner = user_factory(users[0])
    uploader = user_factory(uploader_user_data)

    group_factory(owner_user_id=owner.id)
    group_member_factory(user_id=owner.id, role=MembershipRole.OWNER)
    group_member_factory(user_id=logged_in_user.id, role=MembershipRole.EDITOR)
    group_member_factory(user_id=uploader.id, role=MembershipRole.VIEWER)
    document_factory(
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
