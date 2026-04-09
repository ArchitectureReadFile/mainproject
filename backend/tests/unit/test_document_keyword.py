GROUP_ID = 1  # authenticated_client fixture seed 기준
# 키워드 검색도 view_type=all(기본값) 기준 → APPROVED 문서만 검색 대상
# authenticated_client에 doc_id=101 APPROVED seed 포함


# TC-012-01 키워드 포함 검색 — 승인 문서의 summary_text에서 매칭
def test_search_documents_with_keyword(authenticated_client):
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents?keyword=손해")
    assert res.status_code == 200

    data = res.json()
    assert data["total"] >= 1
    # doc_id=101의 summary_text에 "손해배상" 포함
    assert any(
        "손해" in (item.get("title") or "") or "손해" in (item.get("preview") or "")
        for item in data["items"]
    )


# TC-012-02 존재하지 않는 키워드로 검색
def test_search_documents_no_result(authenticated_client):
    res = authenticated_client.get(
        f"/api/groups/{GROUP_ID}/documents?keyword=테스트123"
    )
    assert res.status_code == 200

    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


# TC-012-03 키워드 없이 조회 — 승인 문서 1건
def test_search_documents_empty_keyword(authenticated_client):
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents?keyword=")
    assert res.status_code == 200

    data = res.json()
    assert data["total"] == 1


# TC-012-04 비로그인 상태
def test_search_documents_unauthenticated(client):
    res = client.get(f"/api/groups/{GROUP_ID}/documents?keyword=손해")
    assert res.status_code == 401
