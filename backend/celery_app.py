import os
import sys

sys.path.insert(0, "/app")

from celery import Celery
from celery.schedules import crontab

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_URL = f"redis://{REDIS_HOST}:6379/0"

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "domains.document.upload_task",
        "domains.chat.tasks",
        "domains.document.index_task",
        "domains.platform_sync.sync_task",
        "tasks.subscription_task",
        "domains.export.tasks",
        "domains.workspace.tasks",
        "domains.document.deletion_task",
        "domains.document.file_cleanup_task",
    ],
)

from domains.chat.tasks import (  # noqa: E402
    process_chat_message,
    process_session_reference_document,
)
from domains.document.deletion_task import finalize_pending_documents  # noqa: E402
from domains.document.file_cleanup_task import cleanup_document_files  # noqa: E402
from domains.document.index_task import (  # noqa: E402
    deindex_document,
    index_approved_document,
)
from domains.document.upload_task import process_next_pending_document  # noqa: E402
from domains.export.tasks import (  # noqa: E402
    build_group_export,
    cleanup_expired_exports,
)
from domains.platform_sync.sync_task import run_platform_source_sync  # noqa: E402
from domains.workspace.tasks import finalize_pending_workspaces  # noqa: E402
from tasks.subscription_task import reconcile_subscriptions  # noqa: E402

ROUTED_TASKS = (
    (process_chat_message, "chat_queue"),
    (process_session_reference_document, "chat_reference_queue"),
    (process_next_pending_document, "document_queue"),
    (index_approved_document, "document_queue"),
    (deindex_document, "document_queue"),
    (finalize_pending_documents, "maintenance_queue"),
    (cleanup_document_files, "maintenance_queue"),
    (finalize_pending_workspaces, "maintenance_queue"),
    (build_group_export, "export_queue"),
    (cleanup_expired_exports, "maintenance_queue"),
    (run_platform_source_sync, "platform_sync_queue"),
    (reconcile_subscriptions, "maintenance_queue"),
)

TASK_ROUTES = {task.name: {"queue": queue} for task, queue in ROUTED_TASKS}

if len(TASK_ROUTES) != len(ROUTED_TASKS):
    raise RuntimeError("Celery task route 구성 검증 실패: task name 중복이 있습니다.")

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_default_queue="maintenance_queue",
    task_routes=TASK_ROUTES,
    beat_schedule={
        "kick-pending-documents-every-minute": {
            "task": process_next_pending_document.name,
            "schedule": crontab(),
        },
        "reconcile-subscriptions-every-hour": {
            "task": reconcile_subscriptions.name,
            "schedule": crontab(minute=0),
        },
        "finalize-pending-workspaces-every-10-minutes": {
            "task": finalize_pending_workspaces.name,
            "schedule": crontab(minute="*/10"),
        },
        "finalize-pending-documents-every-10-minutes": {
            "task": finalize_pending_documents.name,
            "schedule": crontab(minute="*/10"),
        },
        "cleanup-expired-exports-every-10-minutes": {
            "task": cleanup_expired_exports.name,
            "schedule": crontab(minute="*/10"),
        },
    },
)
