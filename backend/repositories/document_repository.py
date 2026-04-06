import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models.model import (
    Category,
    Document,
    DocumentApproval,
    DocumentLifecycleStatus,
    DocumentStatus,
    GroupMember,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
    Summary,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def is_group_admin(self, user_id: int, group_id: int) -> bool:
        return (
            self.db.query(GroupMember.id)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.ACTIVE,
                GroupMember.role.in_([MembershipRole.OWNER, MembershipRole.ADMIN]),
            )
            .first()
            is not None
        )

    def create_document_approval(
        self,
        *,
        document_id: int,
        assignee_user_id: Optional[int] = None,
        reviewer_user_id: Optional[int] = None,
        status: ReviewStatus,
        feedback: Optional[str] = None,
        reviewed_at=None,
    ) -> DocumentApproval:
        """업로드 직후 문서 승인 레코드 생성"""
        approval = DocumentApproval(
            document_id=document_id,
            status=status,
            assignee_user_id=assignee_user_id,
            reviewer_user_id=reviewer_user_id,
            feedback=feedback,
            reviewed_at=reviewed_at,
        )
        self.db.add(approval)
        self.db.flush()
        return approval

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
            .filter(
                Document.processing_status == DocumentStatus.PENDING,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
            )
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
        view_type,
        category,
        group_id=None,
    ):
        query = (
            self.db.query(Document)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
            )
            .outerjoin(Document.summary)
            .filter(Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE)
        )

        if group_id is not None:
            query = query.filter(Document.group_id == group_id)

        if view_type == "my":
            query = query.filter(Document.uploader_user_id == user_id)
        else:
            query = query.join(Document.approval).filter(
                DocumentApproval.status == ReviewStatus.APPROVED
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

        if view_type == "my":
            documents = (
                query.order_by(Document.created_at.desc(), Document.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
        else:
            documents = (
                query.order_by(
                    DocumentApproval.reviewed_at.desc(),
                    Document.created_at.desc(),
                    Document.id.desc(),
                )
                .offset(skip)
                .limit(limit)
                .all()
            )

        return documents, total

    def get_detail(self, doc_id: int):
        return (
            self.db.query(Document)
            .options(
                joinedload(Document.summary),
                joinedload(Document.owner),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
                joinedload(Document.deleted_by),
            )
            .filter(Document.id == doc_id)
            .first()
        )

    def get_by_id(self, document_id: int) -> Document | None:
        return self.db.query(Document).filter(Document.id == document_id).first()

    def delete_document(self, document: Document, user_id: int) -> None:
        now = utc_now_naive()
        document.lifecycle_status = DocumentLifecycleStatus.DELETE_PENDING
        document.delete_requested_at = now
        document.delete_scheduled_at = now + timedelta(days=7)
        document.deleted_by_user_id = user_id
        self.db.commit()

    def restore_document(self, document: Document) -> None:
        document.lifecycle_status = DocumentLifecycleStatus.ACTIVE
        document.delete_requested_at = None
        document.delete_scheduled_at = None
        document.deleted_by_user_id = None
        self.db.commit()

    def get_deleted_list(
        self,
        skip,
        limit,
        user_id,
        group_id=None,
    ) -> tuple[list[Document], int]:
        query = (
            self.db.query(Document)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
            )
            .filter(Document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING)
        )

        if group_id is not None:
            query = query.filter(Document.group_id == group_id)

        query = query.filter(
            or_(
                Document.uploader_user_id == user_id,
                self.db.query(GroupMember.id)
                .filter(
                    GroupMember.group_id == Document.group_id,
                    GroupMember.user_id == user_id,
                    GroupMember.status == MembershipStatus.ACTIVE,
                    GroupMember.role.in_([MembershipRole.OWNER, MembershipRole.ADMIN]),
                )
                .exists(),
            )
        )

        total = query.count()

        documents = (
            query.order_by(Document.delete_requested_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return documents, total
