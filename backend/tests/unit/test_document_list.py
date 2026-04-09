import pytest

from models.model import Document, DocumentStatus
from tests.dummy_data import users

GROUP_ID = 1  # seed_documents / authenticated_client 기준


# TC-011-01 정상 조회 — 승인 문서 1건
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_normal(client, logged_in_user, seed_documents):
    # seed: doc_id=101 (group_id=1, APPROVED) 1건
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 200

    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 5
    assert data["total"] == 1
    assert data["items"][0]["summary_id"] == 1


# TC-011-02 두 번째 페이지 조회 — view_type=my로 검증
# 기본 view_type=all은 APPROVED 문서만 반환하므로,
# approval 없는 추가 문서는 업로더 기준 목록(view_type=my)으로 검증한다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_second_page(client, db_session, logged_in_user, seed_documents):
    # 기존 seed에는 user_id=1이 업로드한 group 1 문서가 2건(id=101, 103) 있다.
    # 여기에 approval 없는 문서 6건을 추가하므로 view_type=my 기준 총 8건이 된다.
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


# TC-011-03 view_type=all — 승인 문서만 반환됨을 확인
# group_id=1에 APPROVED 문서는 doc_id=101(uploader=users[0]) 1건뿐.
# doc_id=102는 group_id=2 소속이므로 group_id=1 조회에 포함되지 않는다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_view_type_all(client, logged_in_user, seed_documents):
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5&view_type=all")
    assert res.status_code == 200

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["uploader"] == "테스트유저"


# TC-011-04 비멤버 접근 → 404
# users[1]은 group_id=1 비멤버 → assert_view_permission → GROUP_NOT_FOUND
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_list_documents_non_member(client, logged_in_user, seed_documents):
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 404


# TC-011-05 멤버이지만 문서 없음 → 빈 목록
# users[0]를 group_id=1 멤버로 세팅하되 승인 문서를 추가하지 않는다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_empty_for_member(client, db_session, logged_in_user):
    from models.model import Group, GroupMember, MembershipRole, MembershipStatus

    db_session.add(
        Group(**{"id": 1, "owner_user_id": 1, "name": "빈 그룹", "status": "ACTIVE"})
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


# TC-011-06 비로그인 상태 → 401
def test_list_documents_unauthenticated(client):
    res = client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=5")
    assert res.status_code == 401
