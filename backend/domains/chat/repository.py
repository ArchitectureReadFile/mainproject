from sqlalchemy.orm import Session

from models.model import ChatMessage, ChatSession, Document, GroupMember


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_sessions_by_user_id(self, user_id: int):
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def get_session_by_id(self, session_id: int) -> ChatSession | None:
        return self.db.query(ChatSession).filter(ChatSession.id == session_id).first()

    def get_session_by_id_and_user(
        self, session_id: int, user_id: int
    ) -> ChatSession | None:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

    def create_session(self, session: ChatSession) -> ChatSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session: ChatSession):
        self.db.delete(session)
        self.db.commit()

    def get_messages_by_session_id(self, session_id: int):
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def get_unsummarized_messages(self, session_id: int, last_id: int):
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.id > last_id)
            .order_by(ChatMessage.id.asc())
            .all()
        )

    def add_message(self, message: ChatMessage):
        self.db.add(message)

    def get_document_by_id(self, document_id: int) -> Document | None:
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_group_member(self, user_id: int, group_id: int) -> GroupMember | None:
        return (
            self.db.query(GroupMember)
            .filter(GroupMember.user_id == user_id, GroupMember.group_id == group_id)
            .first()
        )

    def add(self, obj):
        self.db.add(obj)

    def commit(self):
        self.db.commit()

    def refresh(self, obj):
        self.db.refresh(obj)
