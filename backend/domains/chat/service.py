import logging
import os
import uuid

from celery_app import celery_app
from domains.auth.service import AuthService
from domains.chat.repository import ChatRepository
from domains.knowledge.schemas import WorkspaceSelection
from domains.workspace.service import GroupService
from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import (
    ChatMessage,
    ChatMessageRole,
    ChatSession,
    ChatSessionReference,
    ChatSessionReferenceStatus,
)
from redis_client import redis_client

logger = logging.getLogger(__name__)


class ChatService:
    REFERENCE_UPLOAD_DIR = os.getenv(
        "CHAT_REFERENCE_UPLOAD_DIR", "runtime/uploads/chat_references"
    )
    TASK_KEY_PREFIX = "chat_task"
    TASK_LOCK_KEY_PREFIX = "chat_task_lock"

    def __init__(
        self,
        chat_repo: ChatRepository,
        auth_service: AuthService,
        group_service: GroupService,
    ):
        self.chat_repo = chat_repo
        self.auth_service = auth_service
        self.group_service = group_service

    def get_sessions(self, user_id: int):
        return self.chat_repo.get_sessions_by_user_id(user_id)

    def create_session(self, user_id: int, title: str):
        new_session = ChatSession(user_id=user_id, title=title)
        return self.chat_repo.create_session(new_session)

    def update_session(self, user_id: int, session_id: int, title: str):
        session = self._get_session_with_permission(user_id, session_id)
        session.title = title
        self.chat_repo.commit()
        self.chat_repo.refresh(session)
        return session

    def stop_message(self, user_id: int, session_id: int):
        self._get_session_with_permission(user_id, session_id)

        task_key = self._task_key(session_id)
        task_id = redis_client.get(task_key)

        if task_id:
            celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
            redis_client.delete(task_key)
            return {"status": "success", "message": "Task stopped"}
        return {
            "status": "no_active_task",
            "message": "No active task found for this session",
        }

    def delete_session(self, user_id: int, session_id: int):
        session = self._get_session_with_permission(user_id, session_id)
        self.stop_message(user_id, session_id)
        self.chat_repo.delete_session(session)

    def get_messages(self, user_id: int, session_id: int):
        self._get_session_with_permission(user_id, session_id)
        messages = self.chat_repo.get_messages_by_session_id(session_id)

        is_processing = (
            redis_client.exists(self._task_key(session_id)) > 0
            or redis_client.exists(self._task_lock_key(session_id)) > 0
        )

        return {"messages": messages, "is_processing": is_processing}

    def enqueue_reference_document(
        self,
        user_id: int,
        session_id: int,
        file_name: str,
        file_bytes: bytes,
    ) -> ChatSessionReference:
        self._get_session_with_permission(user_id, session_id)
        previous_reference = self.chat_repo.get_reference_by_session_id(session_id)

        upload_path = self._write_reference_upload(session_id, file_name, file_bytes)
        old_upload_path = previous_reference.upload_path if previous_reference else None

        if previous_reference is not None:
            self.chat_repo.delete(previous_reference)
            self.chat_repo.flush()

        reference = ChatSessionReference(
            session_id=session_id,
            source_type="upload",
            title=file_name,
            upload_path=upload_path,
            extracted_text=None,
            status=ChatSessionReferenceStatus.PROCESSING,
            failure_code=None,
            error_message=None,
        )
        self.chat_repo.add(reference)
        self.chat_repo.commit()
        self.chat_repo.refresh(reference)

        if old_upload_path and old_upload_path != upload_path:
            self._remove_file_quietly(old_upload_path)

        from domains.chat.tasks import process_session_reference_document

        try:
            process_session_reference_document.delay(reference.id)
        except Exception:
            logger.exception(
                "[세션 reference enqueue 실패] session_id=%s reference_id=%s",
                session_id,
                reference.id,
            )
            reference.status = ChatSessionReferenceStatus.FAILED
            reference.failure_code = ErrorCode.CHAT_REFERENCE_ENQUEUE_FAILED.code
            reference.error_message = ErrorCode.CHAT_REFERENCE_ENQUEUE_FAILED.message
            reference.upload_path = None
            self.chat_repo.commit()
            self._remove_file_quietly(upload_path)
            raise AppException(ErrorCode.CHAT_REFERENCE_ENQUEUE_FAILED)

        return reference

    def get_reference_document(self, user_id: int, session_id: int):
        self._get_session_with_permission(user_id, session_id)
        return self.chat_repo.get_reference_by_session_id(session_id)

    def delete_reference_document(self, user_id: int, session_id: int):
        session = self._get_session_with_permission(user_id, session_id)
        reference = self.chat_repo.get_reference_by_session_id(session_id)
        if reference and reference.upload_path:
            self._remove_file_quietly(reference.upload_path)
        if reference:
            self.chat_repo.delete(reference)
        self.chat_repo.commit()
        self.chat_repo.refresh(session)
        return session

    def delete_reference_group(self, user_id: int, session_id: int):
        session = self._get_session_with_permission(user_id, session_id)
        session.reference_group_id = None
        self.chat_repo.commit()
        self.chat_repo.refresh(session)
        return session

    def send_message(
        self,
        user_id: int,
        session_id: int,
        text: str,
        group_id: int | None = None,
        workspace_selection: WorkspaceSelection | None = None,
    ):
        session = self._get_session_with_permission(user_id, session_id)
        previous_group_id = session.reference_group_id
        reference = self.chat_repo.get_reference_by_session_id(session_id)

        if (
            reference is not None
            and reference.status == ChatSessionReferenceStatus.PROCESSING
        ):
            raise AppException(ErrorCode.CHAT_REFERENCE_PROCESSING)

        if workspace_selection is not None:
            self._require_group_membership(user_id, group_id)
            session.reference_group_id = group_id
        task_key = self._task_key(session_id)
        task_lock_key = self._task_lock_key(session_id)
        task_lock_token = str(uuid.uuid4())
        if redis_client.exists(task_key) > 0:
            raise AppException(ErrorCode.CHAT_ALREADY_PROCESSING)
        if not redis_client.set(task_lock_key, task_lock_token, nx=True, ex=30):
            raise AppException(ErrorCode.CHAT_ALREADY_PROCESSING)

        try:
            user_msg = ChatMessage(
                session_id=session_id, role=ChatMessageRole.USER, content=text
            )
            self.chat_repo.add_message(user_msg)

            self.chat_repo.commit()

            from domains.chat.tasks import process_chat_message

            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "group_id": group_id or session.reference_group_id,
                "workspace_selection": (
                    {
                        "mode": workspace_selection.mode,
                        "document_ids": workspace_selection.document_ids,
                    }
                    if workspace_selection is not None
                    else (
                        {"mode": "all", "document_ids": []}
                        if session.reference_group_id
                        else None
                    )
                ),
            }
            task = process_chat_message.delay(payload)
        except Exception:
            logger.exception(
                "[채팅 enqueue 실패] session_id=%s user_id=%s",
                session_id,
                user_id,
            )
            try:
                self.chat_repo.delete_message(user_msg)
                session.reference_group_id = previous_group_id
                self.chat_repo.commit()
            except Exception:
                self.chat_repo.rollback()
                logger.exception(
                    "[채팅 enqueue 보상 실패] session_id=%s user_id=%s",
                    session_id,
                    user_id,
                )
            raise AppException(ErrorCode.CHAT_ENQUEUE_FAILED)
        finally:
            if redis_client.get(task_lock_key) == task_lock_token:
                redis_client.delete(task_lock_key)

        redis_client.set(task_key, task.id, ex=3600)

        return {"status": "success", "message": "Task queued", "task_id": task.id}

    # ── 권한 헬퍼 ─────────────────────────────────────────────────────────────

    def _require_group_membership(self, user_id: int, group_id: int | None) -> None:
        """워크스페이스 검색 사용 시 읽기 가능한 그룹 멤버인지 확인"""
        if group_id is None:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        result = self.group_service.repository.get_group_with_role(user_id, group_id)
        if result:
            group, _ = result
            self.group_service._assert_group_readable(group)
            return

        group = self.group_service.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self.group_service._assert_group_readable(group)
        raise AppException(ErrorCode.AUTH_FORBIDDEN)

    def _get_session_with_permission(
        self, user_id: int, session_id: int
    ) -> ChatSession:
        session = self.chat_repo.get_session_by_id(session_id)
        if not session:
            raise AppException(ErrorCode.CHAT_ROOM_NOT_FOUND)
        if session.user_id != user_id:
            raise AppException(ErrorCode.CHAT_UNAUTHORIZED)
        return session

    def _write_reference_upload(
        self, session_id: int, file_name: str, file_bytes: bytes
    ) -> str:
        safe_name = os.path.basename(file_name or "reference.pdf")
        session_dir = os.path.join(self.REFERENCE_UPLOAD_DIR, f"session_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        path = os.path.join(session_dir, unique_name)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return path

    def _remove_file_quietly(self, path: str | None) -> None:
        if not path:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            logger.warning(
                "[세션 reference 파일 삭제 실패] path=%s", path, exc_info=True
            )

    def _task_key(self, session_id: int) -> str:
        return f"{self.TASK_KEY_PREFIX}:{session_id}"

    def _task_lock_key(self, session_id: int) -> str:
        return f"{self.TASK_LOCK_KEY_PREFIX}:{session_id}"
