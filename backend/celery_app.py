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
        "tasks.upload_task",
        "tasks.chat_task",
        "tasks.group_document_task",
        "tasks.precedent_task",
        "tasks.platform_sync_task",
        "tasks.subscription_task",
        "tasks.export_task",
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
        "tasks.chat_task.process_chat_message": {"queue": "chat_queue"},
        "tasks.upload_task.process_next_pending_document": {"queue": "document_queue"},
        "tasks.group_document_task.index_approved_document": {
            "queue": "document_queue"
        },
        "tasks.group_document_task.deindex_document": {"queue": "document_queue"},
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
        "cleanup-expired-exports-every-10-minutes": {
            "task": "tasks.export_task.cleanup_expired_exports",
            "schedule": crontab(minute="*/10"),
        },
    },
)
