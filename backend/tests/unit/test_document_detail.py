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
    assert data["document_type"] == "판결문"
    assert (
        data["summary_text"]
        == "원고가 불법행위로 인한 손해배상을 청구한 사건으로, 검토자는 사실관계와 손해배상 인정 범위를 먼저 확인할 필요가 있습니다."
    )
    assert data["key_points"] == [
        "불법행위 성립 여부가 핵심 쟁점입니다.",
        "손해배상 인정 범위와 액수를 확인해야 합니다.",
        "판단 근거가 되는 증거 관계를 우선 검토해야 합니다.",
    ]
    assert data["metadata"]["document_type"] == "판결문"
    assert data["case_number"] == "2023다12345"
    assert data["case_name"] == "손해배상(기)"
    assert data["court_name"] == "대법원"
    assert data["judgment_date"] == "2023-10-01"
    assert data["plaintiff"] == "홍길동"
    assert data["defendant"] == "김철수"


# TC-013-02 존재하지 않는 판례 ID
def test_get_document_detail_not_found(authenticated_client):
    res = authenticated_client.get("/api/documents/9999")
    assert res.status_code == 404


# TC-013-03 비로그인 상태
def test_get_document_detail_unauthenticated(client):
    res = client.get("/api/documents/101")
    assert res.status_code == 401
