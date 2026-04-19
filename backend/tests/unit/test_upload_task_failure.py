from unittest.mock import MagicMock, patch

from errors import AppException, ErrorCode
from models.model import DocumentStatus


def test_process_next_pending_document_returns_structured_preview_failure():
    from domains.document.upload_task import process_next_pending_document

    db = MagicMock()
    document = MagicMock()
    document.id = 123
    document.original_filename = "sample.pdf"

    repository = MagicMock()
    repository.claim_next_pending_document.return_value = document

    preview_service = MagicMock()
    preview_service.ensure_preview_pdf.side_effect = AppException(
        ErrorCode.FILE_NOT_FOUND
    )

    with (
        patch("domains.document.upload_task.SessionLocal", return_value=db),
        patch(
            "domains.document.upload_task.DocumentRepository", return_value=repository
        ),
        patch(
            "domains.document.upload_task.DocumentPreviewService",
            return_value=preview_service,
        ),
        patch.object(process_next_pending_document, "delay", lambda: None),
    ):
        result = process_next_pending_document.run()

    assert result["processed"] is False
    assert result["document_id"] == 123
    assert result["status"] == "failed"
    assert result["failure_stage"] == "preview"
    assert result["failure_code"] == ErrorCode.FILE_NOT_FOUND.code
    assert result["error_message"] == ErrorCode.FILE_NOT_FOUND.message
    assert result["error_code"] == ErrorCode.FILE_NOT_FOUND.code
    assert result["message"] == ErrorCode.FILE_NOT_FOUND.message
    repository.update_status.assert_called_once_with(
        123,
        DocumentStatus.FAILED,
        failure_stage="preview",
        failure_code=ErrorCode.FILE_NOT_FOUND.code,
        error_message=ErrorCode.FILE_NOT_FOUND.message,
    )


def test_process_next_pending_document_keeps_success_when_reenqueue_fails():
    from domains.document.upload_task import process_next_pending_document

    db = MagicMock()
    document = MagicMock()
    document.id = 456
    document.original_filename = "sample.pdf"

    repository = MagicMock()
    repository.claim_next_pending_document.return_value = document

    preview_service = MagicMock()
    preview_service.ensure_preview_pdf.return_value = "/tmp/sample.preview.pdf"

    process_service = MagicMock()

    with (
        patch("domains.document.upload_task.SessionLocal", return_value=db),
        patch(
            "domains.document.upload_task.DocumentRepository", return_value=repository
        ),
        patch(
            "domains.document.upload_task.DocumentPreviewService",
            return_value=preview_service,
        ),
        patch(
            "domains.document.upload_task.ProcessService", return_value=process_service
        ),
        patch.object(
            process_next_pending_document,
            "delay",
            side_effect=RuntimeError("queue down"),
        ),
    ):
        result = process_next_pending_document.run()

    assert result == {"processed": True, "document_id": 456}
    process_service.process_file.assert_called_once_with(
        "/tmp/sample.preview.pdf",
        456,
        mark_processing=False,
    )
