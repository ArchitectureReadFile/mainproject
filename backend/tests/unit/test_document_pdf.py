"""
TC-014 요약 PDF 다운로드
"""


# TC-014-01 정상 다운로드
def test_download_pdf_normal(authenticated_client):
    res = authenticated_client.get("/api/summaries/1/download")
    assert res.status_code == 200

    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert len(res.content) > 0


# TC-014-02 존재하지 않는 summary_id
def test_download_pdf_not_found(authenticated_client):
    res = authenticated_client.get("/api/summaries/9999/download")
    assert res.status_code == 404


# TC-014-03 비로그인 상태
def test_download_pdf_unauthenticated(client):
    res = client.get("/api/summaries/1/download")
    assert res.status_code == 401


# TC-014-04 잘못된 summary_id(null)
def test_download_pdf_invalid_id(authenticated_client):
    res = authenticated_client.get("/api/summaries/null/download")
    assert res.status_code == 422
