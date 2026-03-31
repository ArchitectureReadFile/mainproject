from typing import Optional

from sqlalchemy.orm import Session, joinedload

from models.model import (
    Document,
    DocumentApproval,
    DocumentLifecycleStatus,
    ReviewStatus,
    User,
)


class DocumentReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        uploader: str = "",
        assignee_type: str = "all",
        current_user_id: int | None = None,
    ) -> tuple[list[Document], int]:
        """그룹 내 승인 대기 문서 전체 조회(목록용)"""
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

        if uploader:
            query = query.join(Document.owner).filter(User.username == uploader)

        if assignee_type == "mine" and current_user_id is not None:
            query = query.filter(DocumentApproval.assignee_user_id == current_user_id)
        elif assignee_type == "unassigned":
            query = query.filter(DocumentApproval.assignee_user_id.is_(None))
        elif assignee_type == "others" and current_user_id is not None:
            query = query.filter(
                DocumentApproval.assignee_user_id.is_not(None),
                DocumentApproval.assignee_user_id != current_user_id,
            )

        total = query.count()

        documents = (
            query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        )

        return documents, total

    def get_pending_uploaders(
        self,
        group_id: int,
    ) -> list[str]:
        """그룹 내 승인 대기 문서 작성자 목록 조회(필터용)"""
        rows = (
            self.db.query(User.username)
            .join(Document, Document.uploader_user_id == User.id)
            .join(Document.approval)
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.PENDING_REVIEW,
            )
            .distinct()
            .order_by(User.username.asc())
            .all()
        )

        return [username for (username,) in rows]

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

    def get_approved_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        reviewer_user_id: int,
        uploader: str = "",
    ) -> tuple[list[Document], int]:
        """그룹 내 내가 승인한 문서 조회(목록용)"""
        query = (
            self.db.query(Document)
            .join(Document.approval)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
                joinedload(Document.approval).joinedload(DocumentApproval.reviewer),
            )
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.APPROVED,
                DocumentApproval.reviewer_user_id == reviewer_user_id,
            )
        )

        if keyword:
            query = query.filter(Document.original_filename.contains(keyword))

        if uploader:
            query = query.join(Document.owner).filter(User.username == uploader)

        total = query.count()

        documents = (
            query.order_by(DocumentApproval.reviewed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return documents, total

    def get_approved_uploaders(
        self,
        group_id: int,
        reviewer_user_id: int,
    ) -> list[str]:
        """그룹 내 내가 승인한 문서 작성자 목록 조회(필터용)"""
        rows = (
            self.db.query(User.username)
            .join(Document, Document.uploader_user_id == User.id)
            .join(Document.approval)
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.APPROVED,
                DocumentApproval.reviewer_user_id == reviewer_user_id,
            )
            .distinct()
            .order_by(User.username.asc())
            .all()
        )

        return [username for (username,) in rows]

    def get_rejected_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        reviewer_user_id: int,
        uploader: str = "",
    ) -> tuple[list[Document], int]:
        """그룹 내 내가 반려한 문서 조회(목록용)"""
        query = (
            self.db.query(Document)
            .join(Document.approval)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
                joinedload(Document.approval).joinedload(DocumentApproval.reviewer),
            )
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.REJECTED,
                DocumentApproval.reviewer_user_id == reviewer_user_id,
            )
        )

        if keyword:
            query = query.filter(Document.original_filename.contains(keyword))

        if uploader:
            query = query.join(Document.owner).filter(User.username == uploader)

        total = query.count()

        documents = (
            query.order_by(DocumentApproval.reviewed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return documents, total

    def get_rejected_uploaders(
        self,
        group_id: int,
        reviewer_user_id: int,
    ) -> list[str]:
        """그룹 내 내가 반려한 문서 작성자 목록 조회(필터용)"""
        rows = (
            self.db.query(User.username)
            .join(Document, Document.uploader_user_id == User.id)
            .join(Document.approval)
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.REJECTED,
                DocumentApproval.reviewer_user_id == reviewer_user_id,
            )
            .distinct()
            .order_by(User.username.asc())
            .all()
        )

        return [username for (username,) in rows]
