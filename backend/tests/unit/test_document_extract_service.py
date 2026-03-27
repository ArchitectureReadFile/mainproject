"""
tests/unit/test_document_extract_service.py

DocumentExtractService 단위 테스트.
외부 의존성(opendataloader_pdf, 파일시스템, OCR)은 mock으로 격리한다.
"""

from unittest.mock import MagicMock, patch

import pytest

from errors import AppException, ErrorCode
from services.document_extract_service import DocumentExtractService, ExtractedDocument
from services.document_input_builder import (
    extract_body_from_json,
    extract_body_from_markdown,
)
from services.ocr.ocr_service import OcrService

# ── 테스트용 OCR 스텁 ─────────────────────────────────────────────────────────


class _StubOcrService(OcrService):
    """테스트에서 OCR 결과를 직접 주입할 수 있는 스텁."""

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


def _make_extracted(markdown: str = "", json_data=None) -> ExtractedDocument:
    return ExtractedDocument(markdown=markdown, json_data=json_data)


def _ctx():
    """TemporaryDirectory context manager mock."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value="/tmp/fake")
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ── document_input_builder 기준 ───────────────────────────────────────────────


class TestExtractBodyFromMarkdown:
    """extract_body_from_markdown: 후처리 없이 markdown 원문을 그대로 반환한다."""

    def test_returns_stripped_markdown(self):
        md = "  # 제목\n\n본문 내용입니다.  "
        assert extract_body_from_markdown(md) == "# 제목\n\n본문 내용입니다."

    def test_table_rows_preserved(self):
        md = "| 컬럼1 | 컬럼2 |\n|---|---|\n| 값1 | 값2 |"
        result = extract_body_from_markdown(md)
        assert "| 컬럼1 | 컬럼2 |" in result

    def test_empty_returns_empty(self):
        assert extract_body_from_markdown("") == ""
        assert extract_body_from_markdown("   ") == ""

    def test_raw_body_with_heading_and_list(self):
        md = "# 제목\n\n- 항목1\n- 항목2\n\n본문 단락입니다."
        assert extract_body_from_markdown(md) == md.strip()


class TestExtractBodyFromJson:
    """extract_body_from_json: content 수집 후 단순 join만 수행한다."""

    def test_collects_paragraph_content(self):
        json_data = {
            "kids": [
                {"type": "paragraph", "content": "첫 번째 문단"},
                {"type": "paragraph", "content": "두 번째 문단"},
            ]
        }
        result = extract_body_from_json(json_data)
        assert "첫 번째 문단" in result
        assert "두 번째 문단" in result

    def test_empty_json_returns_empty(self):
        assert extract_body_from_json(None) == ""
        assert extract_body_from_json({}) == ""

    def test_table_content_excluded(self):
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
        result = extract_body_from_json(json_data)
        assert "본문" in result
        assert "표 셀 텍스트" not in result


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
    """1차 기본 추출 케이스."""

    def test_file_not_found_raises(self, service):
        with pytest.raises(AppException) as exc_info:
            service.extract("/nonexistent/path.pdf")
        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_success_returns_extracted_without_ocr(self, mock_tmpdir, _exists):
        """1차 추출 body 있으면 OCR 없이 반환한다."""
        mock_tmpdir.return_value = _ctx()
        extracted = _make_extracted(markdown="# 제목\n\n본문 내용입니다.")

        ocr = _StubOcrService(text="")
        svc = DocumentExtractService(ocr_service=ocr)
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=extracted)

        result = svc.extract("/fake/file.pdf")

        assert result is extracted
        svc._convert.assert_called_once_with("/fake/file.pdf", "/tmp/fake")

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_raw_markdown_with_table_accepted(self, mock_tmpdir, _exists):
        """표가 포함된 raw markdown도 body로 인정된다."""
        mock_tmpdir.return_value = _ctx()
        extracted = _make_extracted(
            markdown="| 컬럼1 | 컬럼2 |\n|---|---|\n| 값1 | 값2 |"
        )

        svc = DocumentExtractService(ocr_service=_StubOcrService())
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=extracted)

        result = svc.extract("/fake/file.pdf")

        assert result is extracted
        svc._convert.assert_called_once()

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_json_content_fallback_accepted(self, mock_tmpdir, _exists):
        """markdown 비어 있고 json content 있으면 body로 인정된다."""
        mock_tmpdir.return_value = _ctx()
        json_data = {"kids": [{"type": "paragraph", "content": "JSON 본문입니다."}]}
        extracted = _make_extracted(markdown="", json_data=json_data)

        svc = DocumentExtractService(ocr_service=_StubOcrService())
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=extracted)

        result = svc.extract("/fake/file.pdf")

        assert result is extracted
        svc._convert.assert_called_once()


# ── OCR fallback (body empty) ─────────────────────────────────────────────────


class TestOcrFallbackFromEmptyBody:
    """1차 추출 body 비어 있어 OCR fallback 진입하는 케이스."""

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_empty_body_triggers_ocr_and_returns(self, mock_tmpdir, _exists):
        """1차 body empty → OCR 호출 → 성공 반환."""
        mock_tmpdir.return_value = _ctx()

        ocr = _StubOcrService(text="OCR로 추출된 본문입니다.")
        svc = DocumentExtractService(ocr_service=ocr)
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=_make_extracted(markdown=""))

        result = svc.extract("/fake/scanned.pdf")

        assert result.markdown == "OCR로 추출된 본문입니다."
        assert result.json_data is None
        svc._convert.assert_called_once()  # ODL convert는 1회만 호출

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_ocr_empty_raises_too_short(self, mock_tmpdir, _exists):
        """1차 empty + OCR도 empty → DOC_PDF_TEXT_TOO_SHORT."""
        mock_tmpdir.return_value = _ctx()

        svc = DocumentExtractService(ocr_service=_StubOcrService(text=""))
        svc._convert = MagicMock()
        svc._load_results = MagicMock(return_value=_make_extracted(markdown=""))

        with pytest.raises(AppException) as exc_info:
            svc.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_PDF_TEXT_TOO_SHORT

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_ocr_exception_raises_internal_error(self, mock_tmpdir, _exists):
        """OCR 서비스 예외 → DOC_INTERNAL_PARSE_ERROR."""
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
    """1차 convert 실패 시 OCR fallback 진입하는 케이스."""

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_convert_error_triggers_ocr_success(self, mock_tmpdir, _exists):
        """1차 convert 실패 → OCR fallback → 성공 반환."""
        mock_tmpdir.return_value = _ctx()

        ocr = _StubOcrService(text="OCR 추출 결과.")
        svc = DocumentExtractService(ocr_service=ocr)
        svc._convert = MagicMock(side_effect=Exception("변환 실패"))
        svc._load_results = MagicMock()

        result = svc.extract("/fake/scanned.pdf")

        assert result.markdown == "OCR 추출 결과."
        svc._load_results.assert_not_called()

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_convert_error_and_ocr_empty_raises_too_short(self, mock_tmpdir, _exists):
        """1차 convert 실패 + OCR empty → DOC_PDF_TEXT_TOO_SHORT."""
        mock_tmpdir.return_value = _ctx()

        svc = DocumentExtractService(ocr_service=_StubOcrService(text=""))
        svc._convert = MagicMock(side_effect=Exception("변환 실패"))

        with pytest.raises(AppException) as exc_info:
            svc.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_PDF_TEXT_TOO_SHORT
