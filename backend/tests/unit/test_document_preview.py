from domains.document.service import DocumentService

GROUP_ID = 1  # authenticated_client fixture seed 기준


# UT-DOC-004-01 워크스페이스 멤버는 미리보기 가능한 문서의 PDF 미리보기를 정상 조회할 수 있다.
def test_view_document_preview_success(authenticated_client, monkeypatch, tmp_path):
    """워크스페이스 멤버는 미리보기 가능한 문서의 PDF 미리보기를 정상 조회하는지 검증한다."""
    preview_file = tmp_path / "doc_101_preview.pdf"
    preview_file.write_bytes(b"%PDF-1.4 test preview")

    monkeypatch.setattr(
        DocumentService,
        "get_preview_file_in_group",
        lambda self, doc_id, group_id, current_user_id, current_user_role: (
            str(preview_file),
            "doc_101.pdf",
        ),
    )

    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/101/preview")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")
    assert "inline" in res.headers["content-disposition"]


# UT-DOC-004-02 존재하지 않는 문서의 미리보기는 조회할 수 없다.
def test_view_document_preview_not_found(authenticated_client):
    """존재하지 않는 문서의 미리보기는 조회할 수 없는지 검증한다."""
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/9999/preview")
    assert res.status_code == 404


# UT-DOC-004-03 비로그인 사용자는 문서 미리보기를 조회할 수 없다.
def test_view_document_preview_unauthenticated(client):
    """비로그인 사용자는 문서 미리보기 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/101/preview")
    assert res.status_code == 401
