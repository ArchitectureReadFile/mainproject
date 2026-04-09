"""
tests/unit/test_platform_sync_task.py

platform_sync_task Celery task wrapper 단위테스트.
실제 Celery worker 없이 task 함수를 직접 호출해서 반환값을 검증한다.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

_PATCH_EXECUTE = "tasks.platform_sync_task.execute_platform_source_sync"


# ── TC-PST-01 성공 시 {"status": "ok", "run_id": ...} 반환 ───────────────────


def test_task_success_returns_ok():
    from tasks.platform_sync_task import run_platform_source_sync

    with patch(_PATCH_EXECUTE) as mock_exec:
        mock_exec.return_value = None
        result = run_platform_source_sync.run(42)

    assert result["status"] == "ok"
    assert result["run_id"] == 42
    mock_exec.assert_called_once_with(42)


# ── TC-PST-02 예외 시 {"status": "error", ...} 반환 ──────────────────────────


def test_task_exception_returns_error():
    from tasks.platform_sync_task import run_platform_source_sync

    with patch(_PATCH_EXECUTE, side_effect=RuntimeError("Qdrant 연결 실패")):
        result = run_platform_source_sync.run(99)

    assert result["status"] == "error"
    assert result["run_id"] == 99
    assert "Qdrant 연결 실패" in result["error"]


# ── TC-PST-03 예외 시 logger.error 호출 ──────────────────────────────────────


def test_task_exception_logs_error(caplog):
    from tasks.platform_sync_task import run_platform_source_sync

    with patch(_PATCH_EXECUTE, side_effect=ValueError("잘못된 run_id")):
        with caplog.at_level(logging.ERROR, logger="tasks.platform_sync_task"):
            run_platform_source_sync.run(7)

    assert any("platform sync 실패" in r.message for r in caplog.records)
