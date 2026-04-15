import logging
import os
from urllib.parse import urlparse

from celery_app import celery_app
from database import SessionLocal
from models.model import Document
from redis_client import redis_client

logger = logging.getLogger(__name__)

FILE_CLEANUP_DEDUPE_TTL_SECONDS = 60 * 60 * 24 * 7


def _build_document_cleanup_dedupe_key(document_id: int) -> str:
    """문서 파일 삭제 enqueue 중복 방지용 Redis 키를 생성한다."""
    return f"document_file_cleanup:{document_id}"


def _is_local_filesystem_path(path: str | None) -> bool:
    """로컬 파일시스템 경로인지 판별한다."""
    if not path:
        return False

    normalized = path.strip()
    if not normalized:
        return False

    parsed = urlparse(normalized)
    if parsed.scheme and parsed.scheme != "file":
        return False

    return True


def _normalize_local_path(path: str) -> str:
    """로컬 파일 경로를 삭제 가능한 형태로 정규화한다."""
    parsed = urlparse(path)
    if parsed.scheme == "file":
        return parsed.path
    return path


def _get_document_file_paths(document: Document) -> list[str]:
    """문서에서 삭제 대상 로컬 파일 경로를 중복 없이 수집한다."""
    seen: set[str] = set()
    paths: list[str] = []

    for raw_path in [document.stored_path, document.preview_pdf_path]:
        if not _is_local_filesystem_path(raw_path):
            continue

        normalized = _normalize_local_path(raw_path.strip())
        if normalized in seen:
            continue

        seen.add(normalized)
        paths.append(normalized)

    return paths


def enqueue_document_file_cleanup(document_ids: list[int]) -> list[int]:
    """문서 파일 삭제 task를 중복 없이 enqueue한다."""
    enqueued_ids: list[int] = []

    for document_id in document_ids:
        dedupe_key = _build_document_cleanup_dedupe_key(document_id)
        acquired = redis_client.set(
            dedupe_key,
            "1",
            nx=True,
            ex=FILE_CLEANUP_DEDUPE_TTL_SECONDS,
        )
        if not acquired:
            continue

        try:
            cleanup_document_files.delay(document_id)
            enqueued_ids.append(document_id)
        except Exception:
            redis_client.delete(dedupe_key)
            raise

    logger.info(
        "[document file cleanup enqueue] requested=%s enqueued=%s",
        len(document_ids),
        len(enqueued_ids),
    )

    return enqueued_ids


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    name="tasks.file_cleanup_task.cleanup_document_files",
)
def cleanup_document_files(self, document_id: int) -> dict:
    """문서의 로컬 원본/preview 파일을 idempotent 하게 삭제한다."""
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            logger.warning("[문서 파일 삭제] document 없음: id=%s", document_id)
            return {
                "cleaned": False,
                "reason": "document_not_found",
                "document_id": document_id,
            }

        deleted_paths: list[str] = []
        skipped_paths: list[str] = []

        for path in _get_document_file_paths(document):
            if not os.path.exists(path):
                skipped_paths.append(path)
                continue

            if not os.path.isfile(path):
                skipped_paths.append(path)
                continue

            os.remove(path)
            deleted_paths.append(path)

        logger.info(
            "[document file cleanup] document_id=%s deleted=%s skipped=%s",
            document_id,
            len(deleted_paths),
            len(skipped_paths),
        )

        return {
            "cleaned": True,
            "document_id": document_id,
            "deleted_path_count": len(deleted_paths),
            "skipped_path_count": len(skipped_paths),
        }
    finally:
        db.close()
