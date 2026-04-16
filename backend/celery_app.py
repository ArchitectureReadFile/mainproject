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
        "domains.platform_sync.precedent_task",
        "domains.platform_sync.sync_task",
        "tasks.subscription_task",
        "domains.export.tasks",
        "domains.workspace.tasks",
        "domains.document.deletion_task",
        "domains.document.file_cleanup_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_default_queue="platform_queue",
    task_routes={
        # chat
        "tasks.chat_task.process_chat_message": {"queue": "chat_queue"},
        # document — task name은 각 task 파일의 name= 인자와 일치해야 함
        "domains.document.upload_task.process_next_pending_document": {
            "queue": "document_queue"
        },
        "tasks.group_document_task.index_approved_document": {
            "queue": "document_queue"
        },
        "tasks.group_document_task.deindex_document": {"queue": "document_queue"},
        "tasks.document_deletion_task.finalize_pending_documents": {
            "queue": "document_queue"
        },
        "tasks.file_cleanup_task.cleanup_document_files": {"queue": "document_queue"},
        "tasks.workspace_deletion_task.finalize_pending_workspaces": {
            "queue": "document_queue"
        },
        # platform
        "tasks.platform_sync_task.run_platform_source_sync": {
            "queue": "platform_queue"
        },
        "tasks.precedent_task.process_next_pending_precedent": {
            "queue": "platform_queue"
        },
        "tasks.precedent_task.index_precedent": {"queue": "platform_queue"},
        "tasks.precedent_task.delete_precedent_index": {"queue": "platform_queue"},
        "tasks.subscription_task.reconcile_subscriptions": {"queue": "platform_queue"},
    },
    beat_schedule={
        "reconcile-subscriptions-every-hour": {
            "task": "tasks.subscription_task.reconcile_subscriptions",
            "schedule": crontab(minute=0),
        },
        "finalize-pending-workspaces-every-10-minutes": {
            "task": "tasks.workspace_deletion_task.finalize_pending_workspaces",
            "schedule": crontab(minute="*/10"),
        },
        "finalize-pending-documents-every-10-minutes": {
            "task": "tasks.document_deletion_task.finalize_pending_documents",
            "schedule": crontab(minute="*/10"),
        },
        "cleanup-expired-exports-every-10-minutes": {
            "task": "tasks.export_task.cleanup_expired_exports",
            "schedule": crontab(minute="*/10"),
        },
    },
)
