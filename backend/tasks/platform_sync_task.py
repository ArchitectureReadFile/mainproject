import logging
import sys

sys.path.insert(0, "/app")

from celery_app import celery_app
from services.admin_platform_service import execute_platform_source_sync

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="tasks.platform_sync_task.run_platform_source_sync",
)
def run_platform_source_sync(self, run_id: int) -> dict:
    try:
        execute_platform_source_sync(run_id)
        return {"status": "ok", "run_id": run_id}
    except Exception as exc:
        logger.error(
            "platform sync 실패: run_id=%s error=%s", run_id, exc, exc_info=True
        )
        return {"status": "error", "run_id": run_id, "error": str(exc)}
