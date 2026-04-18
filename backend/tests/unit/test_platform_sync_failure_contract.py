from unittest.mock import patch

import pytest

from errors import AppException, ErrorCode


def test_enqueue_platform_source_sync_marks_failed_when_delay_fails(db_session):
    from domains.admin.platform_service import enqueue_platform_source_sync
    from models.platform_knowledge import PlatformSyncRun

    with patch(
        "domains.platform_sync.sync_task.run_platform_source_sync.delay",
        side_effect=RuntimeError("broker down"),
    ):
        with pytest.raises(AppException) as exc_info:
            enqueue_platform_source_sync(db_session, source_type="law")

    assert exc_info.value.code == ErrorCode.PLATFORM_SYNC_ENQUEUE_FAILED.code

    run = db_session.query(PlatformSyncRun).order_by(PlatformSyncRun.id.desc()).first()
    assert run is not None
    assert run.status == "failed"
    assert run.message == ErrorCode.PLATFORM_SYNC_ENQUEUE_FAILED.message
    assert run.metadata_json is not None
    assert ErrorCode.PLATFORM_SYNC_ENQUEUE_FAILED.code in run.metadata_json
    assert '"failure_stage": "enqueue"' in run.metadata_json


def test_run_platform_sync_task_returns_structured_failure_payload():
    from domains.platform_sync.sync_task import run_platform_source_sync

    with patch(
        "domains.platform_sync.sync_task.execute_platform_source_sync",
        side_effect=RuntimeError("sync exploded"),
    ):
        result = run_platform_source_sync.run(run_id=13)

    assert result["status"] == "failed"
    assert result["run_id"] == 13
    assert result["failure_stage"] == "process"
    assert result["failure_code"] == ErrorCode.PLATFORM_SYNC_PROCESS_FAILED.code
    assert result["error_message"] == ErrorCode.PLATFORM_SYNC_PROCESS_FAILED.message
