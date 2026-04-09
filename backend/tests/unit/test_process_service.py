"""
tests/unit/test_process_service.py

ProcessService 단위테스트.
외부 IO(DB, LLM, 파일 추출)를 모두 mock으로 교체하고
extract → normalize → classify → summarize → save 흐름을 검증한다.

클래스 분리:
    TestProcessFlow         — orchestration 흐름 테스트
    TestNormalizeSummaryData — _normalize_summary_data 헬퍼 테스트
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from models.model import DocumentStatus

# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

_PATCH_SESSION = "services.summary.process_service.SessionLocal"
_PATCH_DOC_REPO = "services.summary.process_service.DocumentRepository"
_PATCH_SUM_REPO = "services.summary.process_service.SummaryRepository"


def _make_svc():
    from services.summary.process_service import ProcessService

    svc = ProcessService()
    svc.extractor = MagicMock()
    svc.normalizer = MagicMock()
    svc.classifier = MagicMock()
    svc.llm = MagicMock()
    svc.summary_payload = MagicMock()
    return svc


def _make_document_mock(title="테스트 문서", body_text="본문 내용"):
    doc = MagicMock()
    doc.metadata = {"title": title}
    doc.body_text = body_text
    return doc


def _run_process(svc, doc_id=1, mark_processing=True, *, doc_repo, sum_repo):
    mock_db = MagicMock()
    with (
        patch(_PATCH_SESSION, return_value=mock_db),
        patch(_PATCH_DOC_REPO, return_value=doc_repo),
        patch(_PATCH_SUM_REPO, return_value=sum_repo),
    ):
        svc.process_file("/tmp/doc.pdf", doc_id, mark_processing=mark_processing)
    return mock_db


# ══════════════════════════════════════════════════════════════════════════════
# TestProcessFlow — orchestration 흐름 테스트
# ══════════════════════════════════════════════════════════════════════════════


class TestProcessFlow:
    # TC-PS-01 정상 처리 시 DONE 상태 + classification/summary 저장
    def test_normal_flow_status_done(self):
        svc = _make_svc()
        svc.extractor.extract.return_value = MagicMock()
        svc.normalizer.normalize.return_value = _make_document_mock()
        svc.classifier.classify.return_value = {
            "document_type": "계약서",
            "category": "계약",
        }
        svc.llm.summarize.return_value = {
            "summary_text": "요약 본문",
            "key_points": ["포인트1", "포인트2"],
        }
        svc.summary_payload.build.return_value = "payload"

        doc_repo = MagicMock()
        sum_repo = MagicMock()
        _run_process(svc, doc_id=1, doc_repo=doc_repo, sum_repo=sum_repo)

        doc_repo.update_status.assert_any_call(1, DocumentStatus.DONE)
        doc_repo.update_classification.assert_called_once_with(
            1, document_type="계약서", category="계약"
        )
        sum_repo.create_summary.assert_called_once()

    # TC-PS-02 mark_processing=False이면 PROCESSING 갱신 건너뜀
    def test_mark_processing_false_skips_processing_status(self):
        svc = _make_svc()
        svc.extractor.extract.return_value = MagicMock()
        svc.normalizer.normalize.return_value = _make_document_mock()
        svc.classifier.classify.return_value = {
            "document_type": "기타",
            "category": "기타",
        }
        svc.llm.summarize.return_value = {"summary_text": "요약", "key_points": []}
        svc.summary_payload.build.return_value = "payload"

        doc_repo = MagicMock()
        sum_repo = MagicMock()
        _run_process(
            svc, doc_id=1, mark_processing=False, doc_repo=doc_repo, sum_repo=sum_repo
        )

        called_statuses = [c.args[1] for c in doc_repo.update_status.call_args_list]
        assert DocumentStatus.PROCESSING not in called_statuses

    # TC-PS-03 classify 결과가 update_classification으로 저장됨
    def test_classify_result_saved_to_repository(self):
        svc = _make_svc()
        svc.extractor.extract.return_value = MagicMock()
        svc.normalizer.normalize.return_value = _make_document_mock()
        svc.classifier.classify.return_value = {
            "document_type": "소장",
            "category": "민사",
        }
        svc.llm.summarize.return_value = {"summary_text": "요약", "key_points": []}
        svc.summary_payload.build.return_value = "payload"

        doc_repo = MagicMock()
        sum_repo = MagicMock()
        _run_process(svc, doc_id=99, doc_repo=doc_repo, sum_repo=sum_repo)

        doc_repo.update_classification.assert_called_once_with(
            99, document_type="소장", category="민사"
        )

    # TC-PS-04 key_points list → 줄바꿈 문자열로 변환
    def test_key_points_list_joined_with_newline(self):
        svc = _make_svc()
        svc.extractor.extract.return_value = MagicMock()
        svc.normalizer.normalize.return_value = _make_document_mock()
        svc.classifier.classify.return_value = {
            "document_type": "기타",
            "category": "기타",
        }
        svc.llm.summarize.return_value = {
            "summary_text": "요약",
            "key_points": ["포인트A", "포인트B", "포인트C"],
        }
        svc.summary_payload.build.return_value = "payload"

        doc_repo = MagicMock()
        sum_repo = MagicMock()
        _run_process(svc, doc_id=1, doc_repo=doc_repo, sum_repo=sum_repo)

        call_kwargs = sum_repo.create_summary.call_args[1]
        assert call_kwargs["key_points"] == "포인트A\n포인트B\n포인트C"

    # TC-PS-06 summarize 예외 시 rollback + FAILED + 재발생
    def test_summarize_exception_status_failed_and_reraise(self):
        svc = _make_svc()
        svc.extractor.extract.return_value = MagicMock()
        svc.normalizer.normalize.return_value = _make_document_mock()
        svc.classifier.classify.return_value = {
            "document_type": "기타",
            "category": "기타",
        }
        svc.llm.summarize.side_effect = RuntimeError("LLM 다운")
        svc.summary_payload.build.return_value = "payload"

        doc_repo = MagicMock()
        sum_repo = MagicMock()
        mock_db = MagicMock()

        with (
            patch(_PATCH_SESSION, return_value=mock_db),
            patch(_PATCH_DOC_REPO, return_value=doc_repo),
            patch(_PATCH_SUM_REPO, return_value=sum_repo),
            pytest.raises(RuntimeError, match="LLM 다운"),
        ):
            svc.process_file("/tmp/doc.pdf", 1)

        mock_db.rollback.assert_called_once()
        doc_repo.update_status.assert_any_call(1, DocumentStatus.FAILED)

    # TC-PS-07 classify 성공 후 summarize 실패 — FAILED 처리 유지
    def test_classify_success_summarize_fail_still_failed(self):
        svc = _make_svc()
        svc.extractor.extract.return_value = MagicMock()
        svc.normalizer.normalize.return_value = _make_document_mock()
        svc.classifier.classify.return_value = {
            "document_type": "소장",
            "category": "민사",
        }
        svc.llm.summarize.side_effect = RuntimeError("summarize 실패")
        svc.summary_payload.build.return_value = "payload"

        doc_repo = MagicMock()
        sum_repo = MagicMock()
        mock_db = MagicMock()

        with (
            patch(_PATCH_SESSION, return_value=mock_db),
            patch(_PATCH_DOC_REPO, return_value=doc_repo),
            patch(_PATCH_SUM_REPO, return_value=sum_repo),
            pytest.raises(RuntimeError),
        ):
            svc.process_file("/tmp/doc.pdf", 5)

        doc_repo.update_classification.assert_called_once_with(
            5, document_type="소장", category="민사"
        )
        doc_repo.update_status.assert_any_call(5, DocumentStatus.FAILED)
        sum_repo.create_summary.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# TestNormalizeSummaryData — _normalize_summary_data 헬퍼 테스트
# ══════════════════════════════════════════════════════════════════════════════


class TestNormalizeSummaryData:
    @pytest.fixture
    def svc(self):
        from services.summary.process_service import ProcessService

        return ProcessService()

    # TC-PS-05a None 값 정규화
    def test_none_value(self, svc):
        result = svc._normalize_summary_data({"summary_text": None, "key_points": None})
        assert result["summary_text"] is None
        assert result["key_points"] is None

    # TC-PS-05b 빈 문자열 정규화
    def test_empty_string(self, svc):
        result = svc._normalize_summary_data({"summary_text": ""})
        assert result["summary_text"] is None

    # TC-PS-05c "null" 문자열 정규화
    def test_null_string(self, svc):
        result = svc._normalize_summary_data({"summary_text": "null"})
        assert result["summary_text"] is None

    # TC-PS-05d 빈 리스트 정규화
    def test_empty_list(self, svc):
        result = svc._normalize_summary_data({"key_points": []})
        assert result["key_points"] == []

    # TC-PS-05e key_points list → 각 항목 strip
    def test_key_points_list_stripped(self, svc):
        result = svc._normalize_summary_data({"key_points": ["  항목1  ", "항목2"]})
        assert result["key_points"] == ["항목1", "항목2"]

    # TC-PS-05f key_points 문자열 → 줄바꿈 분리
    def test_key_points_string_split_by_newline(self, svc):
        result = svc._normalize_summary_data({"key_points": "항목A\n항목B\n항목C"})
        assert result["key_points"] == ["항목A", "항목B", "항목C"]
