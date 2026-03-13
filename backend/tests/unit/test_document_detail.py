# TC-013-01 정상 상세 조회
def test_get_document_detail(authenticated_client):
    res = authenticated_client.get("/api/documents/101")
    assert res.status_code == 200

    data = res.json()

    assert data["id"] == 101
    assert data["status"] == "DONE"
    assert data["uploader"] == "테스트유저"
    assert data["created_at"] is not None

    assert data["summary_id"] == 1
    assert data["case_number"] == "2023다12345"
    assert data["case_name"] == "손해배상(기)"
    assert data["court_name"] == "대법원"
    assert data["judgment_date"] == "2023-10-01"
    assert data["summary_title"] == "손해배상 청구 사건 요약"
    assert (
        data["summary_main"]
        == "본 사건은 불법행위로 인한 손해배상 청구에 관한 대법원 판결입니다."
    )
    assert data["plaintiff"] == "홍길동"
    assert data["defendant"] == "김철수"
    assert data["facts"] == "피고는 원고에게 폭행을 가하여 상해를 입혔음."
    assert data["judgment_order"] == "피고는 원고에게 금 10,000,000원을 지급하라."
    assert data["judgment_reason"] == "증거에 비추어 볼 때 피고의 불법행위가 인정됨."
    assert data["related_laws"] == "민법 제750조"


# TC-013-02 존재하지 않는 판례 ID
def test_get_document_detail_not_found(authenticated_client):
    res = authenticated_client.get("/api/documents/9999")
    assert res.status_code == 404


# TC-013-03 비로그인 상태
def test_get_document_detail_unauthenticated(client):
    res = client.get("/api/documents/101")
    assert res.status_code == 401
