import pytest

from domains.auth.service import AuthService
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


@pytest.fixture
def admin_client(client, db_session):
    """OWNER 권한 유저로 로그인한 클라이언트 + 그룹/멤버 설정"""
    u = users[0].copy()
    u["password"] = auth_service.hash_password(u["password"])
    user = User(**u)
    db_session.add(user)
    db_session.add(Group(**groups[0]))
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        Document(
            id=301,
            group_id=1,
            uploader_user_id=user.id,
            original_filename="cls_test.pdf",
            stored_path="/tmp/test_docs/cls_test.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
            document_type="소장",
            category="민사",
        )
    )
    db_session.add(DocumentApproval(document_id=301, status=ReviewStatus.APPROVED))
    db_session.commit()

    token = auth_service.create_access_token(users[0]["email"])
    client.cookies.set("access_token", token)
    return client


# UT-DOC-018-01 OWNER 또는 ADMIN은 처리 완료된 활성 문서의 문서 유형과 카테고리를 정상 수정할 수 있다.
def test_update_document_classification_success_for_owner_or_admin(
    admin_client, db_session, monkeypatch
):
    """OWNER 또는 ADMIN은 처리 완료된 활성 문서의 문서 유형과 카테고리를 정상 수정할 수 있는지 검증한다."""
    from domains.document.index_task import index_approved_document

    called_document_ids = []
    monkeypatch.setattr(
        index_approved_document,
        "delay",
        lambda document_id: called_document_ids.append(document_id),
    )

    payload = {
        "document_type": "계약서",
        "category": "계약",
    }

    res = admin_client.patch(
        "/api/groups/1/documents/301/classification",
        json=payload,
    )
    assert res.status_code == 200

    data = res.json()
    assert data["message"] == "문서 분류가 수정되었습니다."
    assert data["document_type"] == "계약서"
    assert data["category"] == "계약"

    document = db_session.query(Document).filter(Document.id == 301).first()
    approval = (
        db_session.query(DocumentApproval)
        .filter(DocumentApproval.document_id == 301)
        .first()
    )

    assert document is not None
    assert document.document_type == "계약서"
    assert document.category == "계약"
    assert approval is not None
    assert approval.status == ReviewStatus.APPROVED
    assert called_document_ids == [301]


# UT-DOC-018-02 DELETE_PENDING 상태의 문서는 분류를 수정할 수 없다.
def test_update_document_classification_conflict_for_delete_pending_document(
    admin_client, db_session
):
    """DELETE_PENDING 상태의 문서는 분류를 수정할 수 없는지 검증한다."""
    db_session.add(
        Document(
            id=306,
            group_id=1,
            uploader_user_id=1,
            original_filename="delete_pending_doc.pdf",
            stored_path="/tmp/test_docs/delete_pending_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.DELETE_PENDING,
            document_type="소장",
            category="민사",
        )
    )
    db_session.add(DocumentApproval(document_id=306, status=ReviewStatus.APPROVED))
    db_session.commit()

    payload = {
        "document_type": "계약서",
        "category": "계약",
    }

    res = admin_client.patch(
        "/api/groups/1/documents/306/classification",
        json=payload,
    )
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.DOC_ALREADY_DELETE_PENDING.code


# UT-DOC-018-03 처리 완료되지 않은 문서는 분류를 수정할 수 없다.
def test_update_document_classification_conflict_for_processing_document(
    admin_client, db_session
):
    """처리 완료되지 않은 문서는 분류를 수정할 수 없는지 검증한다."""
    db_session.add(
        Document(
            id=307,
            group_id=1,
            uploader_user_id=1,
            original_filename="processing_doc.pdf",
            stored_path="/tmp/test_docs/processing_doc.pdf",
            processing_status=DocumentStatus.PROCESSING,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
            document_type="미분류",
            category="미분류",
        )
    )
    db_session.add(DocumentApproval(document_id=307, status=ReviewStatus.APPROVED))
    db_session.commit()

    payload = {
        "document_type": "의견서",
        "category": "회사",
    }

    res = admin_client.patch(
        "/api/groups/1/documents/307/classification",
        json=payload,
    )
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.DOC_CLASSIFICATION_EDIT_NOT_ALLOWED.code


# UT-DOC-018-04 OWNER 또는 ADMIN이 아닌 사용자는 문서 분류를 수정할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_update_document_classification_forbidden_for_non_admin_or_owner(
    client, db_session, logged_in_user
):
    """OWNER 또는 ADMIN이 아닌 사용자는 문서 분류를 수정할 수 없는지 검증한다."""
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
    db_session.add(
        Document(
            id=308,
            group_id=1,
            uploader_user_id=owner.id,
            original_filename="editor_forbidden_doc.pdf",
            stored_path="/tmp/test_docs/editor_forbidden_doc.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
            document_type="소장",
            category="민사",
        )
    )
    db_session.add(DocumentApproval(document_id=308, status=ReviewStatus.APPROVED))
    db_session.commit()

    payload = {
        "document_type": "계약서",
        "category": "계약",
    }

    res = client.patch(
        "/api/groups/1/documents/308/classification",
        json=payload,
    )
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_ADMIN_OR_OWNER.code


# UT-DOC-018-05 다른 그룹의 문서는 분류를 수정할 수 없다.
def test_update_document_classification_not_found_for_other_group(authenticated_client):
    """다른 그룹의 문서는 분류를 수정할 수 없는지 검증한다."""
    payload = {
        "document_type": "계약서",
        "category": "계약",
    }

    res = authenticated_client.patch(
        "/api/groups/1/documents/102/classification",
        json=payload,
    )
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.DOC_NOT_FOUND.code


# UT-DOC-018-06 비로그인 사용자는 문서 분류를 수정할 수 없다.
def test_update_document_classification_unauthenticated(client):
    """비로그인 사용자는 문서 분류를 수정할 수 없는지 검증한다."""
    payload = {
        "document_type": "계약서",
        "category": "계약",
    }

    res = client.patch(
        "/api/groups/1/documents/301/classification",
        json=payload,
    )
    assert res.status_code == 401
