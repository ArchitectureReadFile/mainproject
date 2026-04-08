"""
TC-013 문서 상세 조회

source of truth 검증 원칙:
  - document_type / category 는 Document 모델 컬럼을 기준으로 반환된다
  - summary metadata의 document_type 값이 달라도 응답에 반영되지 않는다
"""

from models.model import Document, DocumentApproval, ReviewStatus, Summary
from services.auth_service import AuthService

auth_service = AuthService()


# TC-013-01 정상 상세 조회 — Document.document_type / category source of truth 검증
def test_get_document_detail(authenticated_client):
    res = authenticated_client.get("/api/documents/101")
    assert res.status_code == 200

    data = res.json()

    assert data["id"] == 101
    assert data["status"] == "DONE"
    assert data["uploader"] == "테스트유저"
    assert data["created_at"] is not None

    assert data["summary_id"] == 1

    # source of truth: Document.document_type / category (dummy_data의 documents[0] 값)
    assert data["document_type"] == "소장"
    assert data["category"] == "민사"

    # summary metadata의 "판결문"이 document_type을 덮어쓰지 않아야 한다
    assert data["document_type"] != "판결문"

    assert (
        data["summary_text"]
        == "원고가 불법행위로 인한 손해배상을 청구한 사건으로, 검토자는 사실관계와 손해배상 인정 범위를 먼저 확인할 필요가 있습니다."
    )
    assert data["key_points"] == [
        "불법행위 성립 여부가 핵심 쟁점입니다.",
        "손해배상 인정 범위와 액수를 확인해야 합니다.",
        "판단 근거가 되는 증거 관계를 우선 검토해야 합니다.",
    ]
    # summary metadata는 metadata 필드로만 접근 가능 (보조 기록)
    assert data["metadata"]["document_type"] == "판결문"
    assert data["case_number"] == "2023다12345"
    assert data["case_name"] == "손해배상(기)"
    assert data["court_name"] == "대법원"
    assert data["judgment_date"] == "2023-10-01"
    assert data["plaintiff"] == "홍길동"
    assert data["defendant"] == "김철수"


# TC-013-02 summary metadata document_type이 달라도 응답이 덮어써지지 않음
def test_document_detail_not_overwritten_by_summary_metadata(
    authenticated_client, db_session
):
    """
    Document.document_type = "계약서" 이지만
    summary metadata.document_type = "내용증명" 인 경우
    응답은 Document 값("계약서")을 반환해야 한다.
    """
    import json

    db_session.add(
        Document(
            id=201,
            group_id=1,
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
            metadata_json=json.dumps({"document_type": "내용증명"}, ensure_ascii=False),
        )
    )
    db_session.add(DocumentApproval(document_id=201, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = authenticated_client.get("/api/documents/201")
    assert res.status_code == 200

    data = res.json()
    assert data["document_type"] == "계약서"
    assert data["document_type"] != "내용증명"
    assert data["category"] == "계약"


# TC-013-03 존재하지 않는 문서 ID
def test_get_document_detail_not_found(authenticated_client):
    res = authenticated_client.get("/api/documents/9999")
    assert res.status_code == 404


# TC-013-04 비로그인 상태
def test_get_document_detail_unauthenticated(client):
    res = client.get("/api/documents/101")
    assert res.status_code == 401
