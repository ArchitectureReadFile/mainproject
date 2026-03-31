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
        "tasks.precedent_task",
        "tasks.subscription_task",
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
    beat_schedule={
        "reconcile-subscriptions-every-hour": {
            "task": "tasks.subscription_task.reconcile_subscriptions",
            "schedule": crontab(minute=0),
        }
    },
)
