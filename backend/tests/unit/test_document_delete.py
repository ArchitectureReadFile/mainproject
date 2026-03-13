# TC-016-01 본인 판례 정상 삭제
def test_delete_document_normal(authenticated_client):
    res = authenticated_client.delete("/api/documents/101")
    assert res.status_code == 204


# TC-016-02 권한 없는 다른 사용자 문서 삭제 시도
def test_delete_document_forbidden(authenticated_client):
    res = authenticated_client.delete("/api/documents/102")
    assert res.status_code == 403


# TC-016-03 존재하지 않는 판례 삭제
def test_delete_document_not_found(authenticated_client):
    res = authenticated_client.delete("/api/documents/9999")
    assert res.status_code == 404


# TC-016-04 비로그인 상태
def test_delete_document_unauthenticated(client):
    res = client.delete("/api/documents/101")
    assert res.status_code == 401


# TC-016-05 판례 삭제 후 목록 조회
def test_delete_document_not_in_list(authenticated_client):
    # 삭제
    res = authenticated_client.delete("/api/documents/101")
    assert res.status_code == 204

    # 목록 조회
    res = authenticated_client.get("/api/documents?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]
    assert 101 not in ids
