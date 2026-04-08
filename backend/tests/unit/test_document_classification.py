"""
TC-CLS 분류 시스템 회귀 테스트

검증 항목:
  - 허용값 외 classification PATCH 입력 시 422
  - 승인 문서 수동 수정 시 재인덱싱 task 호출
  - 미분류 목록이 NULL / "미분류" 둘 다 포함
  - category 필터가 Document.category 직접 비교로 동작
"""

from unittest.mock import patch

import pytest

from models.model import Document, DocumentApproval, Group, GroupMember, ReviewStatus
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService()


@pytest.fixture
def admin_client(client, db_session):
    """OWNER 권한 유저로 로그인한 클라이언트 + 그룹/멤버 설정"""
    from models.model import MembershipRole, MembershipStatus, User

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
            processing_status="DONE",
            document_type="소장",
            category="민사",
        )
    )
    db_session.add(DocumentApproval(document_id=301, status=ReviewStatus.APPROVED))
    db_session.commit()

    token = auth_service.create_access_token(users[0]["email"])
    client.cookies.set("access_token", token)
    return client


# TC-CLS-01 허용값 외 document_type → 422
def test_classification_patch_invalid_document_type(admin_client):
    res = admin_client.patch(
        "/api/groups/1/documents/301/classification",
        json={"document_type": "판결문", "category": "민사"},
    )
    assert res.status_code == 422


# TC-CLS-02 허용값 외 category → 422
def test_classification_patch_invalid_category(admin_client):
    res = admin_client.patch(
        "/api/groups/1/documents/301/classification",
        json={"document_type": "소장", "category": "부동산"},
    )
    assert res.status_code == 422


# TC-CLS-03 승인 문서 수동 수정 시 재인덱싱 task 호출
def test_classification_patch_approved_triggers_reindex(admin_client):
    with patch("tasks.group_document_task.index_approved_document") as mock_task:
        mock_task.delay = mock_task  # delay 호출을 직접 호출로 치환
        res = admin_client.patch(
            "/api/groups/1/documents/301/classification",
            json={"document_type": "계약서", "category": "계약"},
        )

    assert res.status_code == 200
    mock_task.assert_called_once()


# TC-CLS-04 미분류 목록 — NULL과 "미분류" 모두 포함
def test_unclassified_list_includes_null_and_literal(admin_client, db_session):

    # NULL 분류 문서 (doc_id=303은 dummy_data.documents[2]와 유사)
    db_session.add(
        Document(
            id=303,
            group_id=1,
            uploader_user_id=1,
            original_filename="null_cls.pdf",
            stored_path="/tmp/test_docs/null_cls.pdf",
            processing_status="DONE",
            document_type=None,
            category=None,
        )
    )
    # "미분류" 문자열 분류 문서
    db_session.add(
        Document(
            id=304,
            group_id=1,
            uploader_user_id=1,
            original_filename="unclassified_str.pdf",
            stored_path="/tmp/test_docs/unclassified_str.pdf",
            processing_status="DONE",
            document_type="미분류",
            category="미분류",
        )
    )
    db_session.commit()

    res = admin_client.get("/api/groups/1/documents/unclassified")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]
    assert 303 in ids
    assert 304 in ids
    # 분류된 문서(301)는 포함되지 않아야 함
    assert 301 not in ids


# TC-CLS-05 category 필터가 Document.category 직접 비교로 동작
def test_document_list_category_filter(admin_client, db_session):
    db_session.add(
        Document(
            id=305,
            group_id=1,
            uploader_user_id=1,
            original_filename="labor_doc.pdf",
            stored_path="/tmp/test_docs/labor_doc.pdf",
            processing_status="DONE",
            document_type="신청서",
            category="노동",
        )
    )
    db_session.add(DocumentApproval(document_id=305, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = admin_client.get("/api/groups/1/documents?category=노동&view_type=all")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]
    assert 305 in ids
    # 다른 category 문서는 포함되지 않아야 함
    for item in data["items"]:
        assert item["category"] == "노동"
