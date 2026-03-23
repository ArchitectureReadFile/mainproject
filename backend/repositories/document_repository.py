import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from errors import AppException, ErrorCode
from models.model import Category, Document, DocumentStatus, Summary, User, UserRole

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_pending_document(
        self,
        *,
        group_id: int,
        uploader_user_id: int,
        original_filename: str,
        stored_path: str,
    ) -> Document:
        document = Document(
            group_id=group_id,
            uploader_user_id=uploader_user_id,
            original_filename=original_filename,
            stored_path=stored_path,
            processing_status=DocumentStatus.PENDING,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def update_status(self, document_id: int, status: DocumentStatus):
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.processing_status = status
            return
        logger.warning(
            "[Document 상태 변경 누락] document_id=%s, status=%s", document_id, status
        )

    def claim_next_pending_document(self) -> Document | None:
        document = (
            self.db.query(Document)
            .filter(Document.processing_status == DocumentStatus.PENDING)
            .order_by(Document.created_at.asc(), Document.id.asc())
            .first()
        )
        if not document:
            return None

        document.processing_status = DocumentStatus.PROCESSING
        self.db.flush()
        return document

    def get_list(
        self,
        skip,
        limit,
        keyword,
        status,
        user_id,
        user_role,
        view_type,
        category,
        group_id=None,
    ):
        query = self.db.query(Document).join(Document.owner).outerjoin(Document.summary)

        if group_id is not None:
            query = query.filter(Document.group_id == group_id)

        if view_type == "my":
            query = query.filter(Document.uploader_user_id == user_id)
        elif user_role != UserRole.ADMIN.value:
            query = query.filter(
                or_(Document.uploader_user_id == user_id, User.role == UserRole.ADMIN)
            )

        if category and category != "전체":
            query = query.join(Document.categories).filter(Category.name == category)

        if keyword:
            query = query.filter(
                or_(
                    Document.original_filename.contains(keyword),
                    Summary.summary_text.contains(keyword),
                )
            )

        if status:
            query = query.filter(Document.processing_status == status)

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
        if document.uploader_user_id != user_id and user_role != UserRole.ADMIN.value:
            raise AppException(ErrorCode.AUTH_FORBIDDEN)
        self.db.delete(document)
        self.db.commit()
