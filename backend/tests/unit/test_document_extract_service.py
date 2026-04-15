"""
tests/unit/test_document_extract_service.py

DocumentExtractService 단위 테스트.
외부 의존성(opendataloader_pdf, 파일시스템, OCR)은 mock으로 격리한다.

12단계: document_input_builder 제거에 따라
extract_body_from_markdown / extract_body_from_json 테스트는
DocumentNormalizeService 기준으로 교체됐다.
"""

from unittest.mock import MagicMock, patch

import pytest

from domains.document.extract_service import DocumentExtractService, ExtractedDocument
from domains.document.normalize_service import DocumentNormalizeService
from errors import AppException, ErrorCode
from infra.ocr.ocr_service import OcrService
from settings.chat import SESSION_DOCUMENT_BODY_MAX, SESSION_DOCUMENT_TABLE_MAX

# ── 테스트용 OCR 스텁 ─────────────────────────────────────────────────────────


class _StubOcrService(OcrService):
    def __init__(self, text: str = "", raise_exc: Exception | None = None):
        self._text = text
        self._raise_exc = raise_exc

    def extract_text(self, file_path: str) -> str:
        if self._raise_exc:
            raise self._raise_exc
        return self._text


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def service():
    return DocumentExtractService(ocr_service=_StubOcrService())


@pytest.fixture
def normalizer():
    return DocumentNormalizeService()


def _make_extracted(
    markdown: str = "",
    json_data=None,
    source_type: str = "odl",
) -> ExtractedDocument:
    return ExtractedDocument(
        markdown=markdown,
        json_data=json_data,
        source_type=source_type,  # type: ignore[arg-type]
    )


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value="/tmp/fake")
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ── DocumentNormalizeService 기준 body 추출 검증 ──────────────────────────────


class TestNormalizeBodyFromMarkdown:
    """ODL 경로: normalize → body_text는 markdown 원문 기반."""

    def test_returns_stripped_body(self, normalizer):
        extracted = _make_extracted(
            markdown="  # 제목\n\n본문 내용입니다.  ", json_data={}
        )
        doc = normalizer.normalize(extracted)
        assert doc.body_text == "# 제목\n\n본문 내용입니다."

    def test_table_rows_preserved_in_body(self, normalizer):
        md = "| 컬럼1 | 컬럼2 |\n|---|---|\n| 값1 | 값2 |"
        extracted = _make_extracted(markdown=md, json_data={})
        doc = normalizer.normalize(extracted)
        assert "| 컬럼1 | 컬럼2 |" in doc.body_text

    def test_empty_markdown_returns_empty_body(self, normalizer):
        extracted = _make_extracted(markdown="", json_data={})
        doc = normalizer.normalize(extracted)
        assert doc.body_text == ""

    def test_whitespace_markdown_returns_empty_body(self, normalizer):
        extracted = _make_extracted(markdown="   ", json_data={})
        doc = normalizer.normalize(extracted)
        assert doc.body_text == ""


class TestNormalizeBodyFromJson:
    """ODL 경로: markdown 없을 때 json fallback으로 body_text 생성."""

    def test_collects_paragraph_content(self, normalizer):
        json_data = {
            "kids": [
                {"type": "paragraph", "content": "첫 번째 문단"},
                {"type": "paragraph", "content": "두 번째 문단"},
            ]
        }
        extracted = _make_extracted(markdown="", json_data=json_data)
        doc = normalizer.normalize(extracted)
        assert "첫 번째 문단" in doc.body_text
        assert "두 번째 문단" in doc.body_text

    def test_empty_json_returns_empty_body(self, normalizer):
        extracted = _make_extracted(markdown="", json_data=None)
        doc = normalizer.normalize(extracted)
        assert doc.body_text == ""

    def test_table_content_excluded_from_body(self, normalizer):
        json_data = {
            "kids": [
                {"type": "paragraph", "content": "본문"},
                {
                    "type": "table",
                    "rows": [
                        {
                            "type": "table row",
                            "cells": [
                                {
                                    "type": "table cell",
                                    "content": "표 셀 텍스트",
                                    "kids": [],
                                }
                            ],
                        }
                    ],
                },
            ]
        }
        extracted = _make_extracted(markdown="", json_data=json_data)
        doc = normalizer.normalize(extracted)
        assert "본문" in doc.body_text
        assert "표 셀 텍스트" not in doc.body_text


# ── _extract_body ─────────────────────────────────────────────────────────────


class TestExtractBodyMethod:
    """_extract_body: raw markdown 우선, 비면 json fallback."""

    def test_markdown_present_returns_markdown(self, service):
        extracted = _make_extracted(markdown="# 제목\n\n본문")
        assert service._extract_body(extracted) == "# 제목\n\n본문"

    def test_markdown_empty_falls_back_to_json(self, service):
        json_data = {"kids": [{"type": "paragraph", "content": "JSON 본문"}]}
        extracted = _make_extracted(markdown="", json_data=json_data)
        assert "JSON 본문" in service._extract_body(extracted)

    def test_both_empty_returns_empty_string(self, service):
        extracted = _make_extracted(markdown="", json_data=None)
        assert service._extract_body(extracted) == ""


# ── 기본 추출 성공 ────────────────────────────────────────────────────────────


class TestNormalExtract:
    def test_file_not_found_raises(self, service):
        with pytest.raises(AppException) as exc_info:
            service.extract("/nonexistent/path.pdf")
        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_success_returns_extracted_without_ocr(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()
        extracted = _make_extracted(markdown="# 제목\n\n본문 내용입니다.")

        svc = DocumentExtractService(ocr_service=_StubOcrService(text=""))
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=extracted)

        result = svc.extract("/fake/file.pdf")
        assert result is extracted
        svc._convert.assert_called_once_with("/fake/file.pdf", "/tmp/fake")

    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_raw_markdown_with_table_accepted(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()
        extracted = _make_extracted(
            markdown="| 컬럼1 | 컬럼2 |\n|---|---|\n| 값1 | 값2 |"
        )

        svc = DocumentExtractService(ocr_service=_StubOcrService())
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=extracted)

        result = svc.extract("/fake/file.pdf")
        assert result is extracted

    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_json_content_fallback_accepted(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()
        json_data = {"kids": [{"type": "paragraph", "content": "JSON 본문입니다."}]}
        extracted = _make_extracted(markdown="", json_data=json_data)

        svc = DocumentExtractService(ocr_service=_StubOcrService())
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=extracted)

        result = svc.extract("/fake/file.pdf")
        assert result is extracted


# ── OCR fallback (body empty) ─────────────────────────────────────────────────


class TestOcrFallbackFromEmptyBody:
    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_empty_body_triggers_ocr_and_returns(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()

        ocr = _StubOcrService(text="OCR로 추출된 본문입니다.")
        svc = DocumentExtractService(ocr_service=ocr)
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=_make_extracted(markdown=""))

        result = svc.extract("/fake/scanned.pdf")
        assert result.markdown == "OCR로 추출된 본문입니다."
        assert result.json_data is None
        assert result.source_type == "ocr"

    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_ocr_empty_raises_too_short(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()

        svc = DocumentExtractService(ocr_service=_StubOcrService(text=""))
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=_make_extracted(markdown=""))

        with pytest.raises(AppException) as exc_info:
            svc.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_PDF_TEXT_TOO_SHORT

    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_ocr_exception_raises_internal_error(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()

        svc = DocumentExtractService(
            ocr_service=_StubOcrService(raise_exc=RuntimeError("OCR 실패"))
        )
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=_make_extracted(markdown=""))

        with pytest.raises(AppException) as exc_info:
            svc.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_INTERNAL_PARSE_ERROR


# ── OCR fallback (convert 실패) ───────────────────────────────────────────────


class TestOcrFallbackFromConvertError:
    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_convert_error_triggers_ocr_success(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()

        ocr = _StubOcrService(text="OCR 추출 결과.")
        svc = DocumentExtractService(ocr_service=ocr)
        svc._convert = MagicMock(side_effect=Exception("변환 실패"))
        svc._load_results = MagicMock()

        result = svc.extract("/fake/scanned.pdf")
        assert result.markdown == "OCR 추출 결과."
        assert result.source_type == "ocr"
        svc._load_results.assert_not_called()

    @patch("domains.document.extract_service.os.path.exists", return_value=True)
    @patch("domains.document.extract_service.tempfile.TemporaryDirectory")
    def test_convert_error_and_ocr_empty_raises_too_short(self, mock_tmpdir, _exists):
        mock_tmpdir.return_value = _ctx()

        svc = DocumentExtractService(ocr_service=_StubOcrService(text=""))
        svc._convert = MagicMock(side_effect=Exception("변환 실패"))

        with pytest.raises(AppException) as exc_info:
            svc.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_PDF_TEXT_TOO_SHORT


# ── SessionDocumentPayloadService 기준 truncate 검증 ─────────────────────────


class TestSessionDocumentPayload:
    """SessionDocumentPayloadService: body/table truncate 정책."""

    @pytest.fixture
    def payload_svc(self):
        from domains.chat.session_payload import (
            SessionDocumentPayloadService,
        )

        return SessionDocumentPayloadService()

    def _doc(self, body="", tables=None):
        from domains.document.document_schema import DocumentSchema, DocumentTableBlock

        blocks = [
            DocumentTableBlock(table_id=f"table:{i}", text=t)
            for i, t in enumerate(tables or [])
        ]
        return DocumentSchema(source_type="odl", body_text=body, table_blocks=blocks)

    def test_body_section_present(self, payload_svc):
        result = payload_svc.build(self._doc(body="본문 내용"))
        assert "[본문]" in result
        assert "본문 내용" in result

    def test_table_section_present(self, payload_svc):
        result = payload_svc.build(self._doc(body="본문", tables=["[표 1]\ncol"]))
        assert "[표]" in result

    def test_table_section_omitted_when_empty(self, payload_svc):
        result = payload_svc.build(self._doc(body="본문"))
        assert "[표]" not in result

    def test_body_truncated_at_6000(self, payload_svc):
        long_body = "가" * 7000
        result = payload_svc.build(self._doc(body=long_body))
        # [본문]\n 이후 body 부분이 설정값 이하
        body_part = result.split("[본문]\n", 1)[1].split("\n\n[표]")[0]
        assert len(body_part) <= SESSION_DOCUMENT_BODY_MAX

    def test_table_truncated_at_2000(self, payload_svc):
        long_table = "가" * 3000
        result = payload_svc.build(self._doc(body="본문", tables=[long_table]))
        table_part = result.split("[표]\n", 1)[1]
        assert len(table_part) <= SESSION_DOCUMENT_TABLE_MAX
