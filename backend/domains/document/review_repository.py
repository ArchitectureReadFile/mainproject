import unicodedata
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from models.model import (
    Document,
    DocumentApproval,
    DocumentComment,
    DocumentCommentScope,
    DocumentLifecycleStatus,
    GroupMember,
    MembershipStatus,
    ReviewStatus,
    Summary,
    User,
)


class DocumentReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _normalize_keyword(keyword: str) -> str:
        """검색어를 NFC 기준으로 정규화"""
        return unicodedata.normalize("NFC", keyword or "").strip()

    def _apply_keyword_filter(self, query, keyword: str):
        """
        승인 문서 목록 검색 조건을 적용
        파일명과 summary metadata(case_number, case_name)를 부분 검색
        """
        normalized = self._normalize_keyword(keyword)
        if not normalized:
            return query

        pattern = f"%{normalized}%"
        return query.filter(
            or_(
                Document.original_filename.ilike(pattern),
                Summary.metadata_json.ilike(pattern),
            )
        )

    def get_member_status_map(
        self,
        *,
        group_id: int,
        user_ids: list[int],
    ) -> dict[int, MembershipStatus]:
        """
        그룹 내 사용자별 멤버십 상태 맵을 반환
        승인 목록 표시명 가공에 사용
        """
        if not user_ids:
            return {}

        rows = (
            self.db.query(GroupMember.user_id, GroupMember.status)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id.in_(user_ids),
            )
            .all()
        )

        return {user_id: status for user_id, status in rows}

    def _get_review_comment_count_subquery(self):
        """
        승인 목록 카드에서 사용할 검토 댓글 수를 문서별로 집계
        삭제된 댓글은 제외
        """
        return (
            self.db.query(
                DocumentComment.document_id.label("document_id"),
                func.count(DocumentComment.id).label("comment_count"),
            )
            .filter(
                DocumentComment.comment_scope == DocumentCommentScope.REVIEW.value,
                DocumentComment.deleted_at.is_(None),
            )
            .group_by(DocumentComment.document_id)
            .subquery()
        )

    def get_pending_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        uploader: str = "",
        assignee_type: str = "all",
        current_user_id: int | None = None,
    ) -> tuple[list[tuple[Document, int]], int]:
        """그룹 내 승인 대기 문서 전체 조회(목록용)"""
        comment_count_subquery = self._get_review_comment_count_subquery()

        query = (
            self.db.query(
                Document,
                func.coalesce(comment_count_subquery.c.comment_count, 0).label(
                    "comment_count"
                ),
            )
            .join(Document.approval)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
            )
            .outerjoin(Document.summary)
            .outerjoin(
                comment_count_subquery,
                comment_count_subquery.c.document_id == Document.id,
            )
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.PENDING_REVIEW,
            )
        )

        query = self._apply_keyword_filter(query, keyword)

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
    ) -> tuple[list[tuple[Document, int]], int]:
        """그룹 내 내가 승인한 문서 조회(목록용)"""
        comment_count_subquery = self._get_review_comment_count_subquery()

        query = (
            self.db.query(
                Document,
                func.coalesce(comment_count_subquery.c.comment_count, 0).label(
                    "comment_count"
                ),
            )
            .join(Document.approval)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
                joinedload(Document.approval).joinedload(DocumentApproval.reviewer),
            )
            .outerjoin(Document.summary)
            .outerjoin(
                comment_count_subquery,
                comment_count_subquery.c.document_id == Document.id,
            )
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.APPROVED,
                DocumentApproval.reviewer_user_id == reviewer_user_id,
            )
        )

        query = self._apply_keyword_filter(query, keyword)

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
    ) -> tuple[list[tuple[Document, int]], int]:
        """그룹 내 내가 반려한 문서 조회(목록용)"""
        comment_count_subquery = self._get_review_comment_count_subquery()

        query = (
            self.db.query(
                Document,
                func.coalesce(comment_count_subquery.c.comment_count, 0).label(
                    "comment_count"
                ),
            )
            .join(Document.approval)
            .options(
                joinedload(Document.owner),
                joinedload(Document.summary),
                joinedload(Document.approval).joinedload(DocumentApproval.assignee),
                joinedload(Document.approval).joinedload(DocumentApproval.reviewer),
            )
            .outerjoin(Document.summary)
            .outerjoin(
                comment_count_subquery,
                comment_count_subquery.c.document_id == Document.id,
            )
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
                DocumentApproval.status == ReviewStatus.REJECTED,
                DocumentApproval.reviewer_user_id == reviewer_user_id,
            )
        )

        query = self._apply_keyword_filter(query, keyword)

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
