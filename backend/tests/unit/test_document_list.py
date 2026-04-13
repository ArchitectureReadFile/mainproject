import pytest

from models.model import Document, DocumentStatus
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
