import os

import redis

from celery_app import celery_app
from database import SessionLocal
from domains.chat.processor import ChatProcessor
from domains.chat.repository import ChatRepository
from domains.chat.session_payload import SessionDocumentPayloadService
from domains.document.extract_service import DocumentExtractService
from domains.document.normalize_service import DocumentNormalizeService
from domains.knowledge.schemas import WorkspaceSelection
from domains.knowledge.session_chunking import split_session_text
from domains.notification.repository import NotificationRepository
from errors import ErrorCode, FailureStage, build_exception_failure_payload
from models.model import ChatSessionReferenceChunk, ChatSessionReferenceStatus

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

_extractor = DocumentExtractService()
_normalizer = DocumentNormalizeService()
_session_payload = SessionDocumentPayloadService()


def _create_task_redis_client() -> redis.Redis:
    """Celery task는 매 실행마다 독립 Redis 연결을 만들고 finally에서 닫는다.

    Web/API 경로의 전역 redis_client와 섞지 않아서 worker 재사용 중에도
    publish/cleanup 연결 수명이 task 단위로 명확해진다.
    """
    return redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)


@celery_app.task(name="tasks.chat_task.process_chat_message")
def process_chat_message(payload: dict):
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")
    group_id = payload.get("group_id")

    raw_selection = payload.get("workspace_selection")
    workspace_selection: WorkspaceSelection | None = None
    if raw_selection is not None:
        workspace_selection = WorkspaceSelection(
            mode=raw_selection.get("mode", "all"),
            document_ids=raw_selection.get("document_ids", []),
        )

    redis_client = _create_task_redis_client()
    db = SessionLocal()

    try:
        chat_repo = ChatRepository(db)
        notification_repo = NotificationRepository(db)

        processor = ChatProcessor(chat_repo, notification_repo)
        processor.process_chat(
            redis_client=redis_client,
            user_id=user_id,
            session_id=session_id,
            group_id=group_id,
            workspace_selection=workspace_selection,
        )
    finally:
        redis_client.delete(f"chat_task:{session_id}")
        db.close()
        redis_client.close()


@celery_app.task(name="tasks.chat_task.process_session_reference_document")
def process_session_reference_document(reference_id: int):
    db = SessionLocal()
    try:
        chat_repo = ChatRepository(db)
        reference = chat_repo.get_reference_by_id(reference_id)
        if not reference:
            return {
                "status": "error",
                "failure_stage": FailureStage.PROCESS.value,
                "failure_code": ErrorCode.CHAT_REFERENCE_PARSE_FAILED.code,
                "error_message": "세션 첨부 문서를 찾을 수 없습니다.",
                "retryable": False,
            }

        try:
            if not reference.upload_path or not os.path.exists(reference.upload_path):
                raise FileNotFoundError(reference.upload_path or "")

            with open(reference.upload_path, "rb") as f:
                file_bytes = f.read()

            extracted = _extractor.extract_bytes(file_bytes)
            document = _normalizer.normalize(extracted)
            extracted_text = _session_payload.build(document)
            chunks = split_session_text(extracted_text)

            reference.extracted_text = extracted_text
            for existing_chunk in list(getattr(reference, "chunks", []) or []):
                chat_repo.delete(existing_chunk)
            for chunk in chunks:
                chat_repo.add(
                    ChatSessionReferenceChunk(
                        reference_id=reference.id,
                        chunk_order=chunk.chunk_order,
                        chunk_text=chunk.chunk_text,
                    )
                )
            reference.status = ChatSessionReferenceStatus.READY
            reference.failure_code = None
            reference.error_message = None
            upload_path = reference.upload_path
            reference.upload_path = None
            chat_repo.commit()

            if upload_path and os.path.exists(upload_path):
                os.remove(upload_path)

            return {
                "status": "success",
                "reference_id": reference_id,
            }
        except Exception as exc:
            failure = build_exception_failure_payload(
                stage=FailureStage.EXTRACT,
                exc=exc,
                fallback_error_code=ErrorCode.CHAT_REFERENCE_PARSE_FAILED,
            )
            reference.status = ChatSessionReferenceStatus.FAILED
            reference.failure_code = failure["failure_code"]
            reference.error_message = failure["error_message"]
            upload_path = reference.upload_path
            reference.upload_path = None
            chat_repo.commit()

            if upload_path and os.path.exists(upload_path):
                try:
                    os.remove(upload_path)
                except OSError:
                    pass

            return failure
    finally:
        db.close()
