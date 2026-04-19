"""
tests/unit/test_document_pipeline.py

그룹 문서 처리/승인/인덱싱 파이프라인 정합성 테스트.

검증 계약:
    1. process_file() 완료 시 APPROVED 문서 → index enqueue
    2. process_file() 완료 시 PENDING_REVIEW 문서 → index enqueue 안 함
    3. approve_document() 에서 processing_status == DONE → 즉시 index enqueue
    4. approve_document() 에서 processing_status != DONE → index enqueue 안 함
    5. auto-approved 업로드 후 process_file 완료 → index enqueue (1번 경로로 흡수)
    6. celery task_routes key가 실제 task name과 일치
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from models.model import DocumentStatus, ReviewStatus

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _make_approval(status: ReviewStatus) -> MagicMock:
    approval = MagicMock()
    approval.status = status
    return approval


def _make_doc(processing_status: DocumentStatus, approval_status: ReviewStatus | None):
    doc = MagicMock()
    doc.processing_status = processing_status
    if approval_status is not None:
        doc.approval = _make_approval(approval_status)
    else:
        doc.approval = None
    return doc


# ── 1·2. process_file 완료 후 approval 상태에 따른 enqueue 분기 ──────────────


class TestProcessFileIndexEnqueue:
    """ProcessService.process_file 완료 후 index enqueue 경로를 검증한다."""

    def _run_process_file(self, approval_status: ReviewStatus | None):
        """process_file을 최소 mock으로 실행하고 index_approved_document.delay 호출 여부를 반환."""
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

        mock_doc = _make_doc(DocumentStatus.PENDING, approval_status)
        mock_doc.original_filename = "test.pdf"

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = mock_doc
        mock_summary_repo = MagicMock()

        with (
            patch("domains.document.summary_process.SessionLocal") as mock_session,
            patch(
                "domains.document.summary_process.DocumentRepository",
                return_value=mock_repo,
            ),
            patch(
                "domains.document.summary_process.SummaryRepository",
                return_value=mock_summary_repo,
            ),
            patch(
                "domains.document.index_task.index_approved_document"
            ) as mock_index_task,
        ):
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_index_task.delay = MagicMock()

            svc.process_file("/fake/path.pdf", 42)

        return mock_index_task.delay

    def test_approved_document_enqueues_index_after_process(self):
        """process_file 완료 시 APPROVED 문서는 index_approved_document.delay 호출."""
        delay = self._run_process_file(ReviewStatus.APPROVED)
        delay.assert_called_once_with(42)

    def test_pending_review_document_does_not_enqueue_index(self):
        """process_file 완료 시 PENDING_REVIEW 문서는 index enqueue 안 함."""
        delay = self._run_process_file(ReviewStatus.PENDING_REVIEW)
        delay.assert_not_called()

    def test_no_approval_does_not_enqueue_index(self):
        """process_file 완료 시 approval 레코드가 없으면 enqueue 안 함."""
        delay = self._run_process_file(None)
        delay.assert_not_called()


# ── 3·4. approve_document processing_status 조건 분기 ────────────────────────


class TestApproveDocumentIndexEnqueue:
    """approve_document 에서 processing_status 에 따른 index enqueue 분기를 검증한다."""

    def _make_review_service(self):
        from domains.document.review_service import DocumentReviewService

        svc = DocumentReviewService.__new__(DocumentReviewService)
        svc.review_repository = MagicMock()
        svc.notification_service = MagicMock()
        svc.notification_service.create_notification_sync = MagicMock()
        return svc

    def _setup_doc(self, svc, processing_status: DocumentStatus):
        from models.model import DocumentLifecycleStatus

        doc = MagicMock()
        doc.id = 99
        doc.group_id = 1
        doc.lifecycle_status = DocumentLifecycleStatus.ACTIVE
        doc.processing_status = processing_status
        doc.uploader_user_id = 10
        doc.original_filename = "doc.pdf"

        approval = MagicMock()
        approval.status = ReviewStatus.PENDING_REVIEW
        doc.approval = approval

        svc.review_repository.get_review_target.return_value = doc
        svc.review_repository.update_document_approval = MagicMock()
        svc.review_repository.db = MagicMock()

        return doc

    def test_done_status_enqueues_index_immediately(self):
        """approve_document: processing_status == DONE → index enqueue."""
        svc = self._make_review_service()
        self._setup_doc(svc, DocumentStatus.DONE)

        with patch(
            "domains.document.review_service.index_approved_document"
        ) as mock_task:
            mock_task.delay = MagicMock()
            svc.approve_document(doc_id=99, user_id=1, group_id=1)

        mock_task.delay.assert_called_once_with(99)

    def test_processing_status_not_done_does_not_enqueue(self):
        """approve_document: processing_status != DONE → index enqueue 안 함."""
        svc = self._make_review_service()

        for status in (
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.FAILED,
        ):
            self._setup_doc(svc, status)

            with patch(
                "domains.document.review_service.index_approved_document"
            ) as mock_task:
                mock_task.delay = MagicMock()
                svc.approve_document(doc_id=99, user_id=1, group_id=1)

            (
                mock_task.delay.assert_not_called(),
                f"status={status}일 때 enqueue되면 안 됨",
            )


# ── 5. auto-approved 업로드 후 process 완료 → index enqueue (1번 경로 흡수) ──


class TestAutoApprovedIndexViaProcess:
    """
    auto-approved 문서는 upload 시점에 별도 index enqueue 없이
    process_file 완료 경로(APPROVED 확인 → enqueue)로 인덱싱된다.
    """

    def test_auto_approved_doc_indexed_after_process_completes(self):
        """
        APPROVED 상태 문서의 process_file 완료 시 index enqueue가 호출되는지 확인.
        upload_service에 별도 index 로직이 없어도 이 경로로 커버된다.
        """
        from domains.document.summary_process import ProcessService

        svc = ProcessService.__new__(ProcessService)
        svc.llm = MagicMock()
        svc.llm.summarize.return_value = {"summary_text": "요약", "key_points": []}
        svc.document_resolver = MagicMock()
        svc.document_resolver.get_or_create.return_value = MagicMock(body_text="본문")
        svc.classifier = MagicMock()
        svc.classifier.classify.return_value = {
            "document_type": "기타",
            "category": "기타",
        }
        svc.summary_payload = MagicMock()
        svc.summary_payload.build.return_value = "요약 입력"

        # auto-approved: APPROVED 상태
        mock_doc = _make_doc(DocumentStatus.PENDING, ReviewStatus.APPROVED)
        mock_doc.original_filename = "auto.pdf"
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = mock_doc

        with (
            patch("domains.document.summary_process.SessionLocal") as mock_session,
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
            mock_session.return_value = MagicMock()
            mock_task.delay = MagicMock()
            svc.process_file("/fake/auto.pdf", 77)

        mock_task.delay.assert_called_once_with(77)


# ── 6. celery task_routes key와 실제 task name 일치 검증 ─────────────────────


class TestCeleryTaskRoutes:
    """
    celery_app.task_routes의 key가 실제 task name= 인자와 일치하는지 검증한다.
    route key 불일치는 document_queue 라우팅 실패로 이어진다.
    """

    def test_upload_task_route_key_matches_task_name(self):
        from celery_app import celery_app
        from domains.document.upload_task import process_next_pending_document

        routes = celery_app.conf.task_routes
        assert process_next_pending_document.name in routes, (
            f"upload task name '{process_next_pending_document.name}' 이 task_routes에 없음"
        )
        assert routes[process_next_pending_document.name]["queue"] == "document_queue"

    def test_upload_task_has_periodic_kick_schedule(self):
        from celery_app import celery_app
        from domains.document.upload_task import process_next_pending_document

        beat_schedule = celery_app.conf.beat_schedule
        assert "kick-pending-documents-every-minute" in beat_schedule
        assert (
            beat_schedule["kick-pending-documents-every-minute"]["task"]
            == process_next_pending_document.name
        )

    def test_index_task_route_key_matches_task_name(self):
        from celery_app import celery_app
        from domains.document.index_task import index_approved_document

        routes = celery_app.conf.task_routes
        assert index_approved_document.name in routes, (
            f"index task name '{index_approved_document.name}' 이 task_routes에 없음"
        )
        assert routes[index_approved_document.name]["queue"] == "document_queue"

    def test_deindex_task_route_key_matches_task_name(self):
        from celery_app import celery_app
        from domains.document.index_task import deindex_document

        routes = celery_app.conf.task_routes
        assert deindex_document.name in routes, (
            f"deindex task name '{deindex_document.name}' 이 task_routes에 없음"
        )
        assert routes[deindex_document.name]["queue"] == "document_queue"

    def test_workspace_task_route_key_matches_task_name(self):
        from celery_app import celery_app
        from domains.workspace.tasks import finalize_pending_workspaces

        routes = celery_app.conf.task_routes
        assert finalize_pending_workspaces.name in routes, (
            f"workspace task name '{finalize_pending_workspaces.name}' 이 task_routes에 없음"
        )

    def test_deletion_task_route_key_matches_task_name(self):
        from celery_app import celery_app
        from domains.document.deletion_task import finalize_pending_documents

        routes = celery_app.conf.task_routes
        assert finalize_pending_documents.name in routes, (
            f"deletion task name '{finalize_pending_documents.name}' 이 task_routes에 없음"
        )
