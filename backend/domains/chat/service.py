import os

from celery_app import celery_app
from domains.auth.service import AuthService
from domains.chat.repository import ChatRepository
from domains.chat.session_payload import SessionDocumentPayloadService
from domains.document.extract_service import DocumentExtractService
from domains.document.normalize_service import DocumentNormalizeService
from domains.knowledge.schemas import WorkspaceSelection
from domains.workspace.service import GroupService
from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import (
    ChatMessage,
    ChatMessageRole,
    ChatSession,
)
from redis_client import redis_client

_extractor = DocumentExtractService()
_normalizer = DocumentNormalizeService()
_session_payload = SessionDocumentPayloadService()


class ChatService:
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

    def stop_message(self, session_id: int):
        task_key = f"chat_task:{session_id}"
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
        self.stop_message(session_id)
        self.chat_repo.delete_session(session)

    def get_messages(self, user_id: int, session_id: int):
        self._get_session_with_permission(user_id, session_id)
        messages = self.chat_repo.get_messages_by_session_id(session_id)

        is_processing = redis_client.exists(f"chat_task:{session_id}") > 0

        return {"messages": messages, "is_processing": is_processing}

    def upload_reference_document(
        self,
        user_id: int,
        session_id: int,
        file_name: str,
        file_bytes: bytes,
    ):
        session = self._get_session_with_permission(user_id, session_id)
        extracted_text = self._extract_text_from_bytes(file_bytes)
        session.reference_document_title = file_name
        session.reference_document_text = extracted_text
        self.chat_repo.commit()
        self.chat_repo.refresh(session)
        return session

    def delete_reference_document(self, user_id: int, session_id: int):
        session = self._get_session_with_permission(user_id, session_id)
        session.reference_document_title = None
        session.reference_document_text = None
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
        document_id: int = None,
        file_name: str = None,
        file_bytes: bytes = None,
        group_id: int | None = None,
        workspace_selection: WorkspaceSelection | None = None,
    ):
        session = self._get_session_with_permission(user_id, session_id)

        if workspace_selection is not None:
            self._require_group_membership(user_id, group_id)
            session.reference_group_id = group_id

        user_msg = ChatMessage(
            session_id=session_id, role=ChatMessageRole.USER, content=text
        )
        self.chat_repo.add_message(user_msg)

        if file_bytes:
            extracted_text = self._extract_text_from_bytes(file_bytes)
            session.reference_document_title = file_name
            session.reference_document_text = extracted_text
        elif document_id:
            document = self.chat_repo.get_document_by_id(document_id)
            if document and self._check_document_permission(user_id, document_id):
                doc_text = self._get_document_full_text(document)
                session.reference_document_title = (
                    document.title or document.original_filename
                )
                session.reference_document_text = doc_text

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

        redis_client.set(f"chat_task:{session_id}", task.id, ex=3600)

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

    def _extract_text_from_bytes(self, file_bytes: bytes) -> str:
        try:
            extracted = _extractor.extract_bytes(file_bytes)
            document = _normalizer.normalize(extracted)
            return _session_payload.build(document)
        except AppException:
            raise
        except Exception:
            raise AppException(ErrorCode.CHAT_FILE_PARSE_FAILED)

    def _check_document_permission(self, user_id: int, doc_id: int) -> bool:
        document = self.chat_repo.get_document_by_id(doc_id)
        if not document:
            return False
        if document.group_id:
            member = self.chat_repo.get_group_member(user_id, document.group_id)
            return bool(member)
        return True

    def _get_document_full_text(self, document):
        file_path = getattr(document, "stored_path", None) or getattr(
            document, "url", None
        )
        if not file_path or not os.path.exists(file_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)
        try:
            extracted = _extractor.extract(file_path)
            document_schema = _normalizer.normalize(extracted)
            return _session_payload.build(document_schema)
        except AppException:
            raise
        except Exception:
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR)
