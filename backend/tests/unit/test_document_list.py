import pytest

from models.model import Document, DocumentStatus
from tests.dummy_data import users


# TC-011-01 정상 조회(skip=0, limit=5)
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_normal(client, logged_in_user, seed_documents):
    res = client.get("/api/documents?skip=0&limit=5")
    assert res.status_code == 200

    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 5
    assert data["total"] == 1
    assert data["items"][0]["summary_id"] == 1


# TC-011-02 두 번째 페이지 조회(skip=5, limit=5)
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_second_page(client, db_session, logged_in_user, seed_documents):
    # seed_documents: user_id=1 문서 1건 포함
    # 추가 6건 삽입 → user_id=1 총 7건
    for i in range(6):
        db_session.add(
            Document(
                id=200 + i,
                user_id=logged_in_user.id,
                document_url=f"https://s3.example.com/extra_{i}.pdf",
                status=DocumentStatus.DONE,
            )
        )
    db_session.commit()

    res = client.get("/api/documents?skip=5&limit=5")
    assert res.status_code == 200

    data = res.json()
    assert data["total"] == 7
    assert len(data["items"]) == 2


# TC-011-03 view_type=all 필터(일반 사용자 계정)
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_list_documents_view_type_all(
    client, logged_in_user, registered_admin, seed_documents
):
    res = client.get("/api/documents?skip=0&limit=5&view_type=all")
    assert res.status_code == 200

    data = res.json()
    assert data["total"] == 2

    uploaders = [item["uploader"] for item in data["items"]]
    assert "테스트유저" in uploaders
    assert "관리자" in uploaders


# TC-011-04 문서가 없는 계정 → 빈 목록 반환
@pytest.mark.parametrize("logged_in_user", [users[1]], indirect=True)
def test_list_documents_empty(client, logged_in_user):
    res = client.get("/api/documents?skip=0&limit=5")
    assert res.status_code == 200

    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


# TC-011-05 비로그인 상태 → 401
def test_list_documents_unauthenticated(client):
    res = client.get("/api/documents?skip=0&limit=5")
    assert res.status_code == 401
