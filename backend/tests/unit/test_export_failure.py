from unittest.mock import MagicMock, patch

import pytest

from errors import AppException, ErrorCode, FailureStage


def test_create_job_enqueue_failure_marks_failed_and_raises():
    from domains.export.service import ExportService

    repository = MagicMock()
    repository.db = MagicMock()
    repository.get_reusable_job.return_value = None

    job = MagicMock()
    job.id = 7
    job.group_id = 3
    repository.create_job.return_value = job

    group_service = MagicMock(spec=["assert_review_view_permission"])
    member = MagicMock()
    member.role = "OWNER"
    group_service.assert_review_view_permission.return_value = (MagicMock(), member)

    service = ExportService(repository=repository, group_service=group_service)

    with (
        patch(
            "domains.export.service.build_group_export.delay",
            side_effect=RuntimeError("broker down"),
        ),
        pytest.raises(AppException) as exc_info,
    ):
        service.create_job(user_id=10, group_id=3)

    assert exc_info.value.code == ErrorCode.EXPORT_ENQUEUE_FAILED.code
    repository.mark_failed.assert_called_once_with(
        7,
        failure_stage=FailureStage.ENQUEUE.value,
        failure_code=ErrorCode.EXPORT_ENQUEUE_FAILED.code,
        error_message=ErrorCode.EXPORT_ENQUEUE_FAILED.message,
    )
    assert repository.db.commit.call_count == 2


def test_run_group_export_job_returns_structured_zip_build_failure():
    from domains.export.tasks import run_group_export_job

    db = MagicMock()
    job = MagicMock()
    job.id = 11
    job.group_id = 5
    job.status = MagicMock()

    repository = MagicMock()
    repository.get_by_id.return_value = job
    repository.mark_processing.return_value = job
    repository.get_group_documents_for_export.return_value = []

    with (
        patch("domains.export.tasks.SessionLocal", return_value=db),
        patch("domains.export.tasks.ExportRepository", return_value=repository),
        patch("domains.export.tasks.os.makedirs"),
        patch(
            "domains.export.tasks.zipfile.ZipFile", side_effect=RuntimeError("zip fail")
        ),
    ):
        result = run_group_export_job(11)

    assert result["ready"] is False
    assert result["status"] == "failed"
    assert result["failure_stage"] == FailureStage.ZIP_BUILD.value
    assert result["failure_code"] == ErrorCode.EXPORT_BUILD_FAILED.code
    assert result["error_message"] == ErrorCode.EXPORT_BUILD_FAILED.message

    repository.mark_failed.assert_called_once_with(
        11,
        failure_stage=FailureStage.ZIP_BUILD.value,
        failure_code=ErrorCode.EXPORT_BUILD_FAILED.code,
        error_message=ErrorCode.EXPORT_BUILD_FAILED.message,
    )
