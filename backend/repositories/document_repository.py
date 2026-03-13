import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from errors import AppException, ErrorCode
from models.model import Category, Document, DocumentStatus, Summary, User, UserRole

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_pending_document(self, user_id: int, document_url: str) -> Document:
        document = Document(
            user_id=user_id, document_url=document_url, status=DocumentStatus.PENDING
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_status(self, document_id: int, status: DocumentStatus):
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = status
            return
        logger.warning(
            "[Document 상태 변경 누락] document_id=%s, status=%s", document_id, status
        )

    def get_list(
        self, skip, limit, keyword, status, user_id, user_role, view_type, category
    ):
        query = self.db.query(Document).join(Document.owner).outerjoin(Document.summary)

        if view_type == "my":
            query = query.filter(Document.user_id == user_id)
        elif user_role != UserRole.ADMIN.value:
            query = query.filter(
                or_(Document.user_id == user_id, User.role == UserRole.ADMIN)
            )

        if category and category != "전체":
            query = query.join(Document.categories).filter(Category.name == category)

        if keyword:
            query = query.filter(
                or_(
                    Document.document_url.contains(keyword),
                    Summary.summary_title.contains(keyword),
                    Summary.summary_main.contains(keyword),
                )
            )

        if status:
            query = query.filter(Document.status == status)

        total = query.count()
        documents = (
            query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        )
        return documents, total

    def get_detail(self, doc_id: int):
        return (
            self.db.query(Document)
            .options(joinedload(Document.summary))
            .filter(Document.id == doc_id)
            .first()
        )

    def delete_document(self, document_id: int, user_id: int, user_role: str) -> None:
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise AppException(ErrorCode.DOC_NOT_FOUND)
        if document.user_id != user_id and user_role != UserRole.ADMIN.value:
            raise AppException(ErrorCode.AUTH_FORBIDDEN)
        self.db.delete(document)
        self.db.commit()
