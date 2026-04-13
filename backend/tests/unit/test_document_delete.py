GROUP_ID = 1  # authenticated_client fixture seed 기준


# TC-016-01 본인 문서 정상 삭제
def test_delete_document_normal(authenticated_client):
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 204


# TC-016-02 다른 그룹 문서 접근 → 404
# doc_id=102는 group_id=2 소속.
# /api/groups/1/documents/102 접근 시 doc.group_id != group_id → DOC_NOT_FOUND
def test_delete_document_other_group_not_found(authenticated_client):
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/102")
    assert res.status_code == 404


# TC-016-03 존재하지 않는 문서 삭제
def test_delete_document_not_found(authenticated_client):
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/9999")
    assert res.status_code == 404


# TC-016-04 비로그인 상태
def test_delete_document_unauthenticated(client):
    res = client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 401


# TC-016-05 문서 삭제 후 목록 조회
def test_delete_document_not_in_list(authenticated_client):
    res = authenticated_client.delete(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 204

    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents?skip=0&limit=10")
    assert res.status_code == 200

    data = res.json()
    ids = [item["id"] for item in data["items"]]
    assert 101 not in ids
