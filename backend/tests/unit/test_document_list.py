import pytest

from models.model import Document, DocumentApproval, DocumentStatus, ReviewStatus
from tests.dummy_data import users

GROUP_ID = 1  # seed_documents / authenticated_client 기준


# UT-DOC-002-01 워크스페이스 멤버는 승인된 문서 목록을 정상 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_success(client, logged_in_user, seed_documents):
    """워크스페이스 멤버는 승인된 문서 목록을 정상 조회하는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 200

    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == 101
    assert data["items"][0]["summary_id"] == 1


# UT-DOC-002-02 view_type이 my인 경우 업로더 본인의 문서 목록을 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_success_with_view_type_my(
    client, db_session, logged_in_user, seed_documents
):
    """view_type이 my인 경우 업로더 본인의 문서 목록을 정상 조회하는지 검증한다."""
    for i in range(6):
        db_session.add(
            Document(
                id=200 + i,
                group_id=GROUP_ID,
                uploader_user_id=logged_in_user.id,
                original_filename=f"extra_{i}.pdf",
                stored_path=f"/tmp/test_docs/extra_{i}.pdf",
                processing_status=DocumentStatus.DONE,
            )
        )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=5&limit=5&view_type=my")
    assert res.status_code == 200

    data = res.json()
    assert data["total"] == 8
    assert len(data["items"]) == 3

    ids = [item["id"] for item in data["items"]]
    assert set(ids).issubset({101, 103, 200, 201, 202, 203, 204, 205})


# UT-DOC-002-03 비멤버는 문서 목록을 조회할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_list_documents_not_found_for_non_member(
    client, logged_in_user, seed_documents
):
    """비멤버는 문서 목록을 조회할 수 없는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 404


# UT-DOC-002-04 문서가 없는 경우 빈 목록을 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_empty(client, db_session, logged_in_user):
    """문서가 없는 경우 빈 목록을 정상 조회하는지 검증한다."""
    from models.model import Group, GroupMember, MembershipRole, MembershipStatus

    db_session.add(
        Group(
            id=1,
            owner_user_id=1,
            name="빈 그룹",
            status="ACTIVE",
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 200

    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


# UT-DOC-002-05 비로그인 사용자는 문서 목록을 조회할 수 없다.
def test_list_documents_unauthenticated(client):
    """비로그인 사용자는 문서 목록 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 401


# UT-DOC-002-06 카테고리 필터를 적용하면 해당 조건의 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_success_with_category_filter(
    client, db_session, logged_in_user, seed_documents
):
    """카테고리 필터를 적용하면 해당 카테고리의 문서만 정상 조회하는지 검증한다."""
    db_session.add(
        Document(
            id=210,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="labor_doc.pdf",
            stored_path="/tmp/test_docs/labor_doc.pdf",
            processing_status=DocumentStatus.DONE,
            document_type="신청서",
            category="노동",
        )
    )
    db_session.add(
        Document(
            id=211,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="civil_doc.pdf",
            stored_path="/tmp/test_docs/civil_doc.pdf",
            processing_status=DocumentStatus.DONE,
            document_type="소장",
            category="민사",
        )
    )
    db_session.add(DocumentApproval(document_id=210, status=ReviewStatus.APPROVED))
    db_session.add(DocumentApproval(document_id=211, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = client.get(
        f"/api/groups/{GROUP_ID}/documents?skip=0&limit=10&view_type=all&category=노동"
    )
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert 210 in ids
    assert 211 not in ids
    for item in data["items"]:
        assert item["category"] == "노동"


# UT-DOC-002-07 미분류 필터를 적용하면 category가 미분류인 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_success_with_unclassified_filter(
    client, db_session, logged_in_user, seed_documents
):
    """미분류 필터를 적용하면 category가 미분류인 문서만 정상 조회하는지 검증한다."""
    db_session.add(
        Document(
            id=212,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="unclassified_doc.pdf",
            stored_path="/tmp/test_docs/unclassified_doc.pdf",
            processing_status=DocumentStatus.DONE,
            document_type="미분류",
            category="미분류",
        )
    )
    db_session.add(
        Document(
            id=213,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="classified_doc.pdf",
            stored_path="/tmp/test_docs/classified_doc.pdf",
            processing_status=DocumentStatus.DONE,
            document_type="계약서",
            category="계약",
        )
    )
    db_session.add(DocumentApproval(document_id=212, status=ReviewStatus.APPROVED))
    db_session.add(DocumentApproval(document_id=213, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = client.get(
        f"/api/groups/{GROUP_ID}/documents?skip=0&limit=10&view_type=all&category=미분류"
    )
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert 212 in ids
    assert 213 not in ids
    for item in data["items"]:
        assert item["category"] == "미분류"


# UT-DOC-002-08 키워드 검색을 적용하면 해당 키워드가 포함된 문서만 조회할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_success_with_keyword_filter(
    client, db_session, logged_in_user, seed_documents
):
    """키워드 검색을 적용하면 해당 키워드가 포함된 문서만 정상 조회하는지 검증한다."""
    db_session.add(
        Document(
            id=214,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="keyword_target_contract.pdf",
            stored_path="/tmp/test_docs/keyword_target_contract.pdf",
            processing_status=DocumentStatus.DONE,
        )
    )
    db_session.add(
        Document(
            id=215,
            group_id=GROUP_ID,
            uploader_user_id=logged_in_user.id,
            original_filename="other_document.pdf",
            stored_path="/tmp/test_docs/other_document.pdf",
            processing_status=DocumentStatus.DONE,
        )
    )
    db_session.add(DocumentApproval(document_id=214, status=ReviewStatus.APPROVED))
    db_session.add(DocumentApproval(document_id=215, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = client.get(
        f"/api/groups/{GROUP_ID}/documents?skip=0&limit=10&view_type=all&keyword=keyword_target"
    )
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]

    assert 214 in ids
    assert 215 not in ids
