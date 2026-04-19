from unittest.mock import MagicMock, patch

import pytest

from errors import AppException, ErrorCode
from models.model import DocumentStatus, ReviewStatus


def _make_repo_with_doc(*, approval_status: ReviewStatus | None = None):
    repo = MagicMock()
    doc = MagicMock()
    doc.original_filename = "sample.pdf"
    if approval_status is None:
        doc.approval = None
    else:
        approval = MagicMock()
        approval.status = approval_status
        doc.approval = approval
    repo.get_by_id.return_value = doc
    return repo


def test_process_file_persists_failure_metadata_on_summary_error():
    from domains.document.summary_process import ProcessService

    svc = ProcessService.__new__(ProcessService)
    svc.llm = MagicMock()
    svc.llm.summarize.side_effect = AppException(ErrorCode.LLM_EMPTY_PAGES)
    svc.document_resolver = MagicMock()
    svc.document_resolver.get_or_create.return_value = MagicMock(body_text="본문")
    svc.classifier = MagicMock()
    svc.classifier.classify.return_value = {
        "document_type": "계약서",
        "category": "민사",
    }
    svc.summary_payload = MagicMock()
    svc.summary_payload.build.return_value = "요약 입력"

    mock_db = MagicMock()
    mock_repo = _make_repo_with_doc()

    with (
        patch("domains.document.summary_process.SessionLocal", return_value=mock_db),
        patch(
            "domains.document.summary_process.DocumentRepository",
            return_value=mock_repo,
        ),
        patch(
            "domains.document.summary_process.SummaryRepository",
            return_value=MagicMock(),
        ),
    ):
        with pytest.raises(AppException):
            svc.process_file("/fake/path.pdf", 42)

    assert mock_repo.update_status.call_args_list[0].args == (
        42,
        DocumentStatus.PROCESSING,
    )
    assert mock_repo.update_status.call_args_list[-1].args == (
        42,
        DocumentStatus.FAILED,
    )
    assert mock_repo.update_status.call_args_list[-1].kwargs == {
        "failure_stage": "summarize",
        "failure_code": ErrorCode.LLM_EMPTY_PAGES.code,
        "error_message": ErrorCode.LLM_EMPTY_PAGES.message,
    }
    assert mock_db.commit.call_count >= 2
    mock_db.rollback.assert_called()
    svc.llm.release_resources.assert_called_once()


def test_process_file_keeps_done_status_when_index_enqueue_fails():
    from domains.document.summary_process import ProcessService

    svc = ProcessService.__new__(ProcessService)
    svc.llm = MagicMock()
    svc.llm.summarize.return_value = {"summary_text": "요약", "key_points": []}
    svc.document_resolver = MagicMock()
    svc.document_resolver.get_or_create.return_value = MagicMock(body_text="본문")
    svc.classifier = MagicMock()
    svc.classifier.classify.return_value = {
        "document_type": "계약서",
        "category": "민사",
    }
    svc.summary_payload = MagicMock()
    svc.summary_payload.build.return_value = "요약 입력"

    mock_db = MagicMock()
    mock_repo = _make_repo_with_doc(approval_status=ReviewStatus.APPROVED)

    with (
        patch("domains.document.summary_process.SessionLocal", return_value=mock_db),
        patch(
            "domains.document.summary_process.DocumentRepository",
            return_value=mock_repo,
        ),
        patch(
            "domains.document.summary_process.SummaryRepository",
            return_value=MagicMock(),
        ),
        patch("domains.document.index_task.index_approved_document") as mock_task,
    ):
        mock_task.delay.side_effect = RuntimeError("queue down")
        svc.process_file("/fake/path.pdf", 77)

    assert mock_repo.update_status.call_args_list[0].args == (
        77,
        DocumentStatus.PROCESSING,
    )
    assert mock_repo.update_status.call_args_list[-1].args == (
        77,
        DocumentStatus.DONE,
    )
    assert mock_repo.update_status.call_args_list[-1].kwargs == {}
