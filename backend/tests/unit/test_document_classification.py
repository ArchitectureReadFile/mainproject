"""
TC-CLS 분류 시스템 회귀 테스트

보류 처리된 케이스:
    TC-CLS-01 ~ TC-CLS-04:
        PATCH /api/groups/{group_id}/documents/{doc_id}/classification
        GET  /api/groups/{group_id}/documents/unclassified
        위 두 라우트가 현재 group_document.py에 존재하지 않는다.
        의도적 제거인지 구현 누락인지 확인 전까지 테스트를 보류한다.
        → 실제 코드 버그 후보로 별도 기록 필요.

유지 케이스:
    TC-CLS-05: category 필터 — GET /api/groups/{group_id}/documents?category=...
               현재 라우터에 존재하는 엔드포인트로 검증 가능.
"""

import pytest

from models.model import Document, DocumentApproval, Group, GroupMember, ReviewStatus
from services.auth_service import AuthService
from tests.dummy_data import groups, users

auth_service = AuthService(None)


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
    for item in data["items"]:
        assert item["category"] == "노동"
