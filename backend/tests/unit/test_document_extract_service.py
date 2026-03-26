"""
tests/unit/test_document_extract_service.py

DocumentExtractService 단위 테스트.
외부 의존성(opendataloader_pdf, 파일시스템)은 mock으로 격리한다.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from errors import AppException, ErrorCode
from services.document_extract_service import (
    DocumentExtractService,
    ExtractedDocument,
    _HybridConnectionError,
    _HybridParseError,
)


@pytest.fixture
def service():
    return DocumentExtractService()


def _make_extracted(markdown: str = "", json_data=None) -> ExtractedDocument:
    return ExtractedDocument(markdown=markdown, json_data=json_data)


def _ctx():
    """TemporaryDirectory context manager mock."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value="/tmp/fake")
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestNormalExtract:
    """1차 일반 추출 성공/실패 케이스."""

    def test_file_not_found_raises(self, service):
        with pytest.raises(AppException) as exc_info:
            service.extract("/nonexistent/path.pdf")
        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_success_returns_extracted_without_ocr(self, mock_tmpdir, _exists, service):
        """1차 추출 body 있으면 OCR 없이 반환한다."""
        mock_tmpdir.return_value = _ctx()
        extracted = _make_extracted(markdown="# 제목\n\n본문 내용입니다.")
        service._convert = MagicMock()
        service._load_results = MagicMock(return_value=extracted)

        result = service.extract("/fake/file.pdf")

        assert result is extracted
        service._convert.assert_called_once_with(
            "/fake/file.pdf", "/tmp/fake", force_ocr=False
        )


class TestOcrFallbackFromEmptyBody:
    """1차 추출 성공했지만 body 비어 있어 OCR fallback 진입하는 케이스."""

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_empty_body_triggers_ocr_fallback(self, mock_tmpdir, _exists, service):
        """1차 body empty → OCR fallback 진입, _convert 총 2회 호출."""
        mock_tmpdir.return_value = _ctx()
        empty = _make_extracted(markdown="")
        ocr_result = _make_extracted(markdown="OCR 본문입니다.")
        service._convert = MagicMock()
        service._load_results = MagicMock(side_effect=[empty, ocr_result])

        result = service.extract("/fake/scanned.pdf")

        assert result is ocr_result
        assert service._convert.call_count == 2
        assert service._convert.call_args_list[0] == call(
            "/fake/scanned.pdf", "/tmp/fake", force_ocr=False
        )
        assert service._convert.call_args_list[1] == call(
            "/fake/scanned.pdf", "/tmp/fake", force_ocr=True
        )

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_ocr_fallback_also_empty_raises_too_short(
        self, mock_tmpdir, _exists, service
    ):
        """1차 + OCR fallback 모두 body empty → DOC_PDF_TEXT_TOO_SHORT."""
        mock_tmpdir.return_value = _ctx()
        service._convert = MagicMock()
        service._load_results = MagicMock(
            side_effect=[
                _make_extracted(markdown=""),
                _make_extracted(markdown=""),
            ]
        )

        with pytest.raises(AppException) as exc_info:
            service.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_PDF_TEXT_TOO_SHORT


class TestOcrFallbackFromConvertError:
    """1차 convert가 _HybridParseError로 실패해 OCR fallback 진입하는 케이스."""

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_parse_error_triggers_ocr_fallback_success(
        self, mock_tmpdir, _exists, service
    ):
        """1차 _HybridParseError → OCR fallback → 성공 반환."""
        mock_tmpdir.return_value = _ctx()
        ocr_result = _make_extracted(markdown="스캔 본문 추출.")
        service._convert = MagicMock(
            side_effect=[
                _HybridParseError("변환 실패"),
                None,  # OCR fallback convert 성공
            ]
        )
        service._load_results = MagicMock(return_value=ocr_result)

        result = service.extract("/fake/scanned.pdf")

        assert result is ocr_result
        assert service._convert.call_count == 2
        assert service._convert.call_args_list[1] == call(
            "/fake/scanned.pdf", "/tmp/fake", force_ocr=True
        )

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_parse_error_then_ocr_also_fails_raises_internal(
        self, mock_tmpdir, _exists, service
    ):
        """1차 _HybridParseError → OCR fallback도 실패 → DOC_INTERNAL_PARSE_ERROR."""
        mock_tmpdir.return_value = _ctx()
        service._convert = MagicMock(
            side_effect=[
                _HybridParseError("1차 실패"),
                _HybridParseError("OCR도 실패"),
            ]
        )
        service._load_results = MagicMock()

        with pytest.raises(AppException) as exc_info:
            service.extract("/fake/scanned.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_INTERNAL_PARSE_ERROR
        service._load_results.assert_not_called()


class TestConnectionErrorNoFallback:
    """연결 실패(_HybridConnectionError)는 OCR fallback 없이 즉시 실패하는 케이스."""

    @patch("services.document_extract_service.os.path.exists", return_value=True)
    @patch("services.document_extract_service.tempfile.TemporaryDirectory")
    def test_connection_error_raises_immediately_no_fallback(
        self, mock_tmpdir, _exists, service
    ):
        """1차 _HybridConnectionError → fallback 없이 DOC_INTERNAL_PARSE_ERROR."""
        mock_tmpdir.return_value = _ctx()
        service._convert = MagicMock(side_effect=_HybridConnectionError("연결 거부"))
        service._load_results = MagicMock()

        with pytest.raises(AppException) as exc_info:
            service.extract("/fake/file.pdf")
        assert exc_info.value.error_code == ErrorCode.DOC_INTERNAL_PARSE_ERROR
        # _convert는 1회만 호출되어야 함 (OCR fallback 미진입)
        service._convert.assert_called_once()
        service._load_results.assert_not_called()


class TestConvertErrorClassification:
    """_convert 내부에서 원본 예외 문자열에 따라 올바른 내부 예외가 올라오는지 확인."""

    def test_connection_refused_raises_connection_error(self):
        svc = DocumentExtractService()
        with patch(
            "services.document_extract_service.odl.convert",
            side_effect=Exception("connection refused"),
        ):
            with pytest.raises(_HybridConnectionError):
                svc._convert("/fake/file.pdf", "/tmp/out", force_ocr=False)

    def test_timeout_raises_parse_error(self):
        svc = DocumentExtractService()
        with patch(
            "services.document_extract_service.odl.convert",
            side_effect=Exception("request timed out"),
        ):
            with pytest.raises(_HybridParseError):
                svc._convert("/fake/file.pdf", "/tmp/out", force_ocr=False)

    def test_generic_error_raises_parse_error(self):
        svc = DocumentExtractService()
        with patch(
            "services.document_extract_service.odl.convert",
            side_effect=Exception("unexpected docling error"),
        ):
            with pytest.raises(_HybridParseError):
                svc._convert("/fake/file.pdf", "/tmp/out", force_ocr=False)
