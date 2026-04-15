from services.document_service import DocumentService

GROUP_ID = 1  # authenticated_client fixture seed 기준


# UT-DOC-005-01 워크스페이스 멤버는 다운로드 가능한 문서의 원문 파일을 정상 다운로드할 수 있다.
def test_download_document_success(authenticated_client, monkeypatch, tmp_path):
    """워크스페이스 멤버는 다운로드 가능한 문서의 원문 파일을 정상 다운로드하는지 검증한다."""
    original_file = tmp_path / "doc_101.pdf"
    original_file.write_bytes(b"%PDF-1.4 original document")

    monkeypatch.setattr(
        DocumentService,
        "get_original_file_in_group",
        lambda self, doc_id, group_id, current_user_id, current_user_role: (
            str(original_file),
            "doc_101.pdf",
        ),
    )

    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/101/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")
    assert "attachment" in res.headers["content-disposition"]


# UT-DOC-005-02 존재하지 않는 문서의 원문 파일은 다운로드할 수 없다.
def test_download_document_not_found(authenticated_client):
    """존재하지 않는 문서의 원문 파일은 다운로드할 수 없는지 검증한다."""
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/9999/download")
    assert res.status_code == 404


# UT-DOC-005-03 비로그인 사용자는 문서 원문 파일을 다운로드할 수 없다.
def test_download_document_unauthenticated(client):
    """비로그인 사용자는 문서 원문 파일 다운로드 요청이 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/101/download")
    assert res.status_code == 401
