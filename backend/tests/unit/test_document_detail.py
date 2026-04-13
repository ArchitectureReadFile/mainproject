import json

from models.model import Document, DocumentApproval, ReviewStatus, Summary

GROUP_ID = 1  # authenticated_client fixture seed 기준


# UT-DOC-003-01 워크스페이스 멤버는 승인된 문서의 상세 정보를 정상 조회할 수 있다.
def test_get_document_detail_success(authenticated_client):
    """워크스페이스 멤버는 승인된 문서의 상세 정보를 정상 조회하는지 검증한다."""
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 200

    data = res.json()

    assert data["id"] == 101
    assert data["status"] == "DONE"
    assert data["uploader"] == "테스트유저"
    assert data["created_at"] is not None
    assert data["summary_id"] == 1
    assert data["document_type"] == "소장"
    assert data["category"] == "민사"
    assert data["summary_text"] is not None
    assert data["key_points"] != []
    assert data["metadata"]["case_number"] == "2023다12345"
    assert data["metadata"]["case_name"] == "손해배상(기)"


# UT-DOC-003-02 문서 상세 조회 시 문서 분류값은 Document 모델 기준으로 반환된다.
def test_get_document_detail_uses_document_classification(
    authenticated_client, db_session
):
    """문서 상세 조회 시 문서 분류값은 Document 모델 기준으로 반환되는지 검증한다."""
    db_session.add(
        Document(
            id=201,
            group_id=GROUP_ID,
            uploader_user_id=1,
            original_filename="overwrite_test.pdf",
            stored_path="/tmp/test_docs/overwrite_test.pdf",
            processing_status="DONE",
            document_type="계약서",
            category="계약",
        )
    )
    db_session.add(
        Summary(
            id=99,
            document_id=201,
            summary_text="테스트 요약",
            key_points="포인트1",
            metadata_json=json.dumps(
                {
                    "document_type": "내용증명",
                    "case_number": "2024가12345",
                },
                ensure_ascii=False,
            ),
        )
    )
    db_session.add(DocumentApproval(document_id=201, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/201")
    assert res.status_code == 200

    data = res.json()
    assert data["document_type"] == "계약서"
    assert data["category"] == "계약"
    assert data["document_type"] != "내용증명"
    assert data["metadata"]["document_type"] == "내용증명"


# UT-DOC-003-03 존재하지 않는 문서의 상세 정보는 조회할 수 없다.
def test_get_document_detail_not_found(authenticated_client):
    """존재하지 않는 문서의 상세 정보는 조회할 수 없는지 검증한다."""
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/9999")
    assert res.status_code == 404


# UT-DOC-003-04 비로그인 사용자는 문서 상세 정보를 조회할 수 없다.
def test_get_document_detail_unauthenticated(client):
    """비로그인 사용자는 문서 상세 정보 조회가 차단되는지 검증한다."""
    res = client.get(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 401
