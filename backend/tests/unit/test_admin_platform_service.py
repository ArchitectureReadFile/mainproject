"""
tests/unit/test_admin_platform_service.py

admin_platform_service 단위테스트.
Celery task enqueue는 patch, DB는 SQLite test session 사용.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from models.platform_knowledge import (
    PlatformDocument,
    PlatformDocumentChunk,
    PlatformSyncFailure,
    PlatformSyncRun,
)
from services.admin_platform_service import (
    _build_run_message,
    _dump_run_meta,
    _load_run_meta,
    _snippet,
)

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _make_run(db_session, source_type="law", status="queued", task_id=None):
    run = PlatformSyncRun(
        source_type=source_type,
        status=status,
        message="테스트",
        fetched_count=0,
        created_count=0,
        skipped_count=0,
        failed_count=0,
    )
    if task_id:
        run.metadata_json = json.dumps({"task_id": task_id})
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


# ── TC-APS-01 _build_run_message ─────────────────────────────────────────────


def test_build_run_message_without_page():
    counts = {"fetched": 10, "created": 3, "skipped": 7, "failed": 0}
    msg = _build_run_message(counts=counts)
    assert "10건" in msg
    assert "3건" in msg
    assert "페이지" not in msg


def test_build_run_message_with_page():
    counts = {"fetched": 50, "created": 5, "skipped": 45, "failed": 0}
    msg = _build_run_message(counts=counts, page=3)
    assert "3페이지" in msg
    assert "50건" in msg


# ── TC-APS-02 _load_run_meta ──────────────────────────────────────────────────


def test_load_run_meta_none_run():
    assert _load_run_meta(None) == {}


def test_load_run_meta_empty_string():
    run = MagicMock()
    run.metadata_json = ""
    assert _load_run_meta(run) == {}


def test_load_run_meta_invalid_json():
    run = MagicMock()
    run.metadata_json = "not-json"
    assert _load_run_meta(run) == {}


def test_load_run_meta_valid():
    run = MagicMock()
    run.metadata_json = json.dumps({"current_page": 5})
    assert _load_run_meta(run) == {"current_page": 5}


# ── TC-APS-03 _dump_run_meta ──────────────────────────────────────────────────


def test_dump_run_meta_stores_json_string():
    run = MagicMock()
    _dump_run_meta(run, {"current_page": 2, "total_count": 100})
    data = json.loads(run.metadata_json)
    assert data["current_page"] == 2
    assert data["total_count"] == 100


# ── TC-APS-04 get_admin_platform_summary ─────────────────────────────────────


def test_get_admin_platform_summary_counts(db_session):
    from services.admin_platform_service import get_admin_platform_summary

    for i in range(2):
        doc = PlatformDocument(
            source_type="law",
            external_id=f"LAW-{i}",
            title=f"법령 {i}",
            status="active",
        )
        db_session.add(doc)
    db_session.flush()

    docs = db_session.query(PlatformDocument).all()
    for doc in docs:
        for j in range(1 if doc.external_id == "LAW-0" else 2):
            db_session.add(
                PlatformDocumentChunk(
                    platform_document_id=doc.id,
                    source_type="law",
                    chunk_type="article",
                    chunk_order=j,
                    chunk_text=f"조문 {j}",
                )
            )
    db_session.commit()

    result = get_admin_platform_summary(db_session)
    law_source = next(s for s in result.sources if s.source_type == "law")
    assert law_source.document_count == 2
    assert law_source.chunk_count == 3


def test_get_admin_platform_summary_latest_run_meta(db_session):
    from services.admin_platform_service import get_admin_platform_summary

    run = _make_run(db_session, "law", "success")
    _dump_run_meta(run, {"current_page": 7, "total_count": 500})
    db_session.commit()

    result = get_admin_platform_summary(db_session)
    law_source = next(s for s in result.sources if s.source_type == "law")
    assert law_source.current_page == 7
    assert law_source.total_count == 500


# ── TC-APS-05 enqueue_platform_source_sync — 정상 enqueue ────────────────────
# 구현이 함수 내부에서 `from tasks.platform_sync_task import run_platform_source_sync`
# 하므로 patch target은 tasks.platform_sync_task 모듈을 직접 지정한다.


def test_enqueue_creates_queued_run_and_calls_task(db_session):
    from services.admin_platform_service import enqueue_platform_source_sync

    mock_result = MagicMock()
    mock_result.id = "task-abc"

    with patch("tasks.platform_sync_task.run_platform_source_sync") as mock_celery:
        mock_celery.delay.return_value = mock_result
        result = enqueue_platform_source_sync(db_session, source_type="law")

    assert result.status == "queued"
    assert result.source_type == "law"
    mock_celery.delay.assert_called_once()

    run = db_session.query(PlatformSyncRun).filter_by(source_type="law").first()
    assert run is not None


# ── TC-APS-06 enqueue — 이미 running/queued이면 중복 실행 방지 ───────────────


def test_enqueue_blocks_duplicate_when_already_running(db_session):
    from services.admin_platform_service import enqueue_platform_source_sync

    existing = _make_run(db_session, "law", "running")

    with patch("tasks.platform_sync_task.run_platform_source_sync") as mock_celery:
        result = enqueue_platform_source_sync(db_session, source_type="law")

    # Celery enqueue 호출 안 됨
    mock_celery.delay.assert_not_called()
    # 기존 run을 그대로 반환
    assert result.run_id == existing.id
    assert result.status == existing.status


# ── TC-APS-07 stop_platform_source_sync ──────────────────────────────────────
# 구현이 함수 내부에서 `from celery_app import celery_app` 하고
# celery_app.control.revoke를 호출하므로 revoke 경로를 직접 patch한다.


def test_stop_queued_run_becomes_cancelled(db_session):
    from services.admin_platform_service import stop_platform_source_sync

    run = _make_run(db_session, "law", "queued")
    with patch("celery_app.celery_app.control.revoke"):
        result = stop_platform_source_sync(db_session, source_type="law")

    assert result.status == "cancelled"
    assert result.run_id == run.id
    db_session.refresh(run)
    assert run.status == "cancelled"
    assert run.finished_at is not None


def test_stop_running_run_becomes_cancelled(db_session):
    from services.admin_platform_service import stop_platform_source_sync

    _make_run(db_session, "precedent", "running")
    with patch("celery_app.celery_app.control.revoke"):
        result = stop_platform_source_sync(db_session, source_type="precedent")

    assert result.status == "cancelled"


def test_stop_revoke_called_with_task_id(db_session):
    """metadata_json에 task_id가 있을 때 revoke가 해당 id로 호출되는지 검증."""
    from services.admin_platform_service import stop_platform_source_sync

    _make_run(db_session, "law", "running", task_id="celery-task-xyz")

    with patch("celery_app.celery_app.control.revoke") as mock_revoke:
        stop_platform_source_sync(db_session, source_type="law")

    mock_revoke.assert_called_once_with(
        "celery-task-xyz", terminate=True, signal="SIGTERM"
    )


def test_stop_no_active_run_returns_not_found(db_session):
    from services.admin_platform_service import stop_platform_source_sync

    _make_run(db_session, "law", "success")
    result = stop_platform_source_sync(db_session, source_type="law")
    assert result.status == "not_found"


# ── TC-APS-08 get_admin_platform_failures 필터 ───────────────────────────────


def test_failures_filtered_by_source_type(db_session):
    from services.admin_platform_service import get_admin_platform_failures

    run = _make_run(db_session, "law", "failed")
    for source in ["law", "law", "precedent"]:
        db_session.add(
            PlatformSyncFailure(
                sync_run_id=run.id,
                source_type=source,
                error_type="fetch_error",
                error_message="에러",
            )
        )
    db_session.commit()

    result = get_admin_platform_failures(db_session, source_type="law")
    assert result.total == 2
    assert all(f.source_type == "law" for f in result.items)


def test_failures_filtered_by_run_id(db_session):
    from services.admin_platform_service import get_admin_platform_failures

    run1 = _make_run(db_session, "law", "failed")
    run2 = _make_run(db_session, "law", "failed")
    db_session.add(
        PlatformSyncFailure(
            sync_run_id=run1.id, source_type="law", error_type="fetch_error"
        )
    )
    db_session.add(
        PlatformSyncFailure(
            sync_run_id=run2.id, source_type="law", error_type="fetch_error"
        )
    )
    db_session.commit()

    result = get_admin_platform_failures(db_session, run_id=run1.id)
    assert result.total == 1
    assert result.items[0].sync_run_id == run1.id


def test_failures_limit_applied(db_session):
    from services.admin_platform_service import get_admin_platform_failures

    run = _make_run(db_session, "law", "failed")
    for _ in range(5):
        db_session.add(
            PlatformSyncFailure(
                sync_run_id=run.id, source_type="law", error_type="fetch_error"
            )
        )
    db_session.commit()

    result = get_admin_platform_failures(db_session, limit=3)
    assert len(result.items) == 3
    assert result.total == 5


# ── TC-APS-09 _snippet 길이 제한 ─────────────────────────────────────────────


def test_snippet_truncates_long_payload():
    long_dict = {"key": "v" * 1000}
    result = _snippet(long_dict)
    assert result is not None
    assert len(result) <= 500


def test_snippet_none_returns_none():
    assert _snippet(None) is None
