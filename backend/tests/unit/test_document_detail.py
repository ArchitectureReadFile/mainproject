"""
TC-013 문서 상세 조회

source of truth 검증 원칙:
  - document_type / category 는 Document 모델 컬럼 기준 (최상위 필드)
  - 사건 메타(case_number 등)는 summary metadata → data["metadata"]["..."] 로 접근
  - summary metadata의 document_type은 보조 기록이므로 최상위를 덮어쓰지 않음

라우터: GET /api/groups/{group_id}/documents/{doc_id}
상세 조회는 업로더/OWNER/ADMIN이면 미승인 문서도 접근 가능.
"""

import json

from models.model import Document, DocumentApproval, ReviewStatus, Summary
from services.auth_service import AuthService

auth_service = AuthService(None)

GROUP_ID = 1  # authenticated_client fixture seed 기준


# TC-013-01 정상 상세 조회
def test_get_document_detail(authenticated_client):
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 200

    data = res.json()

    assert data["id"] == 101
    assert data["status"] == "DONE"
    assert data["uploader"] == "테스트유저"
    assert data["created_at"] is not None
    assert data["summary_id"] == 1

    # source of truth: Document.document_type / category
    assert data["document_type"] == "소장"
    assert data["category"] == "민사"
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

    # 사건 메타는 metadata 딕셔너리 안에서 접근
    meta = data["metadata"]
    assert meta["document_type"] == "판결문"
    assert meta["case_number"] == "2023다12345"
    assert meta["case_name"] == "손해배상(기)"
    assert meta["court_name"] == "대법원"
    assert meta["judgment_date"] == "2023-10-01"
    assert meta["plaintiff"] == "홍길동"
    assert meta["defendant"] == "김철수"

    # 사건 메타가 최상위 필드로 노출되지 않음
    assert "case_number" not in data
    assert "plaintiff" not in data


# TC-013-02 summary metadata document_type이 달라도 최상위 응답 덮어쓰지 않음
def test_document_detail_not_overwritten_by_summary_metadata(
    authenticated_client, db_session
):
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
            metadata_json=json.dumps({"document_type": "내용증명"}, ensure_ascii=False),
        )
    )
    db_session.add(DocumentApproval(document_id=201, status=ReviewStatus.APPROVED))
    db_session.commit()

    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/201")
    assert res.status_code == 200

    data = res.json()
    assert data["document_type"] == "계약서"
    assert data["document_type"] != "내용증명"
    assert data["category"] == "계약"


# TC-013-03 존재하지 않는 문서 ID
def test_get_document_detail_not_found(authenticated_client):
    res = authenticated_client.get(f"/api/groups/{GROUP_ID}/documents/9999")
    assert res.status_code == 404


# TC-013-04 비로그인 상태
def test_get_document_detail_unauthenticated(client):
    res = client.get(f"/api/groups/{GROUP_ID}/documents/101")
    assert res.status_code == 401
