import os

from sqlalchemy.orm import Session

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import (
    ChatMessage,
    ChatMessageRole,
    ChatSession,
    Document,
    GroupMember,
)
from repositories.group_repository import GroupRepository
from schemas.knowledge import WorkspaceSelection
from services.chat.session_document_payload_service import SessionDocumentPayloadService
from services.document_extract_service import DocumentExtractService
from services.document_normalize_service import DocumentNormalizeService
from services.group_service import GroupService

_extractor = DocumentExtractService()
_normalizer = DocumentNormalizeService()
_session_payload = SessionDocumentPayloadService()


class ChatService:
    def get_sessions(self, db: Session, user_id: int):
        return (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def create_session(self, db: Session, user_id: int, title: str):
        new_session = ChatSession(user_id=user_id, title=title)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    def update_session(self, db: Session, user_id: int, session_id: int, title: str):
        session = self._get_session_with_permission(db, user_id, session_id)
        session.title = title
        db.commit()
        db.refresh(session)
        return session

    def delete_session(self, db: Session, user_id: int, session_id: int):
        session = self._get_session_with_permission(db, user_id, session_id)
        db.delete(session)
        db.commit()

    def get_messages(self, db: Session, user_id: int, session_id: int):
        self._get_session_with_permission(db, user_id, session_id)
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def upload_reference_document(
        self,
        db: Session,
        user_id: int,
        session_id: int,
        file_name: str,
        file_bytes: bytes,
    ):
        session = self._get_session_with_permission(db, user_id, session_id)
        extracted_text = self._extract_text_from_bytes(file_bytes)
        session.reference_document_title = file_name
        session.reference_document_text = extracted_text
        db.commit()
        db.refresh(session)
        return session

    def delete_reference_document(self, db: Session, user_id: int, session_id: int):
        session = self._get_session_with_permission(db, user_id, session_id)
        session.reference_document_title = None
        session.reference_document_text = None
        db.commit()
        db.refresh(session)
        return session

    def delete_reference_group(self, db: Session, user_id: int, session_id: int):
        session = self._get_session_with_permission(db, user_id, session_id)
        session.reference_group_id = None
        db.commit()
        db.refresh(session)
        return session

    def send_message(
        self,
        db: Session,
        user_id: int,
        session_id: int,
        text: str,
        document_id: int = None,
        file_name: str = None,
        file_bytes: bytes = None,
        group_id: int | None = None,
        workspace_selection: WorkspaceSelection | None = None,
    ):
        session = self._get_session_with_permission(db, user_id, session_id)

        if workspace_selection is not None:
            self._require_group_membership(db, user_id, group_id)
            session.reference_group_id = group_id

        user_msg = ChatMessage(
            session_id=session_id, role=ChatMessageRole.USER, content=text
        )
        db.add(user_msg)

        if file_bytes:
            extracted_text = self._extract_text_from_bytes(file_bytes)
            session.reference_document_title = file_name
            session.reference_document_text = extracted_text
        elif document_id:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document and self._check_document_permission(db, user_id, document_id):
                doc_text = self._get_document_full_text(document)
                session.reference_document_title = (
                    document.title or document.original_filename
                )
                session.reference_document_text = doc_text

        db.commit()

        from tasks.chat_task import process_chat_message

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
        process_chat_message.delay(payload)

        return {"status": "success", "message": "Task queued"}

    # ── 권한 헬퍼 ─────────────────────────────────────────────────────────────

    def _require_group_membership(
        self, db: Session, user_id: int, group_id: int | None
    ) -> None:
        """워크스페이스 검색 사용 시 읽기 가능한 그룹 멤버인지 확인"""
        if group_id is None:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group_service = GroupService(GroupRepository(db), db)

        result = group_service.repository.get_group_with_role(user_id, group_id)
        if result:
            group, _ = result
            group_service._assert_group_readable(group)
            return

        group = group_service.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group_service._assert_group_readable(group)
        raise AppException(ErrorCode.AUTH_FORBIDDEN)

    def _get_session_with_permission(
        self, db: Session, user_id: int, session_id: int
    ) -> ChatSession:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
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

    def _check_document_permission(
        self, db: Session, user_id: int, doc_id: int
    ) -> bool:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            return False
        if document.group_id:
            member = (
                db.query(GroupMember)
                .filter(
                    GroupMember.user_id == user_id,
                    GroupMember.group_id == document.group_id,
                )
                .first()
            )
            return bool(member)
        return True

    def _get_document_full_text(self, document: Document) -> str:
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
