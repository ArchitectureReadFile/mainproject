import json
import logging
import os
import sys

sys.path.insert(0, "/app")

from redis import Redis

from celery_app import celery_app
from services.summary.process_service import ProcessService

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
logger = logging.getLogger(__name__)


def _get_redis():
    return Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)


def _publish(user_id: int, message: dict):
    try:
        r = _get_redis()
        r.publish(f"upload:{user_id}", json.dumps(message, ensure_ascii=False))
        r.close()
    except Exception as e:
        logger.error(f"[publish 실패] user_id={user_id}, error={e}")


@celery_app.task(bind=True)
def process_upload_task(
    self, file_path: str, document_id: int, user_id: int, file_name: str
):
    logger.info(
        f"[태스크 시작] doc_id={document_id}, user_id={user_id}, file={file_name}"
    )

    try:
        r = _get_redis()
        r.setex(f"upload_task:{user_id}:{document_id}", 3600, self.request.id)
        r.close()
    except Exception as e:
        logger.warning(f"[task_id 저장 실패] {e}")

    _publish(
        user_id,
        {
            "type": "upload_processing",
            "doc_id": document_id,
            "file_name": file_name,
        },
    )

    try:
        logger.info(f"[ProcessService 시작] doc_id={document_id}")
        service = ProcessService()
        service.process_file(file_path, document_id)
        logger.info(f"[ProcessService 완료] doc_id={document_id}")

        from services.upload.session_service import UploadSessionService

        session = UploadSessionService().get_session(user_id)
        summary = next(
            (
                item.get("summary")
                for item in session.get("items", [])
                if item.get("doc_id") == document_id
            ),
            None,
        )

        _publish(
            user_id,
            {
                "type": "upload_done",
                "doc_id": document_id,
                "file_name": file_name,
                "summary": summary,
            },
        )

    except Exception as e:
        logger.error(f"[처리 실패] doc_id={document_id}, error={e}", exc_info=True)
        _publish(
            user_id,
            {
                "type": "upload_failed",
                "doc_id": document_id,
                "file_name": file_name,
                "error": str(e),
            },
        )
