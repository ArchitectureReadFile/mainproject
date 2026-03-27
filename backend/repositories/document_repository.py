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
        documents = (
            query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        )
        return documents, total

    def get_detail(self, doc_id: int):
        return (
            self.db.query(Document)
            .options(
                joinedload(Document.summary),
                joinedload(Document.owner),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
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

    def get_pending_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
    ) -> tuple[list[Document], int]:
        """그룹 내 승인 대기 문서 전체 조회"""
        query = (
            self.db.query(Document)
            .join(Document.approval)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
            )
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.PENDING_REVIEW,
            )
        )

        if keyword:
            query = query.filter(Document.original_filename.contains(keyword))

        total = query.count()
        documents = (
            query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        )

        return documents, total

    def get_review_target(self, doc_id: int) -> Optional[Document]:
        """승인/반려 처리에 필요한 문서 단건 조회"""
        return (
            self.db.query(Document)
            .options(
                joinedload(Document.owner),
                joinedload(Document.approval),
            )
            .filter(Document.id == doc_id)
            .first()
        )

    def update_document_approval(
        self,
        approval: DocumentApproval,
        status: ReviewStatus,
        reviewer_user_id: int,
        feedback: Optional[str] = None,
        reviewed_at=None,
    ) -> DocumentApproval:
        """문서 승인 상태를 갱신"""
        approval.status = status
        approval.reviewer_user_id = reviewer_user_id
        approval.feedback = feedback
        approval.reviewed_at = reviewed_at
        self.db.flush()

        return approval
