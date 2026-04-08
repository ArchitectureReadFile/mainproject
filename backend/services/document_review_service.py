from errors import AppException, ErrorCode
from models.model import (
    DocumentLifecycleStatus,
    MembershipStatus,
    ReviewStatus,
    utc_now_naive,
)
from repositories.document_review_repository import DocumentReviewRepository
from schemas.document import (
    PendingDocumentListItemResponse,
    ReviewedDocumentListItemResponse,
)
from services.summary.summary_mapper import (
    build_document_title,
    build_summary_preview,
)
from tasks.group_document_task import index_approved_document


class DocumentReviewService:
    def __init__(self, review_repository: DocumentReviewRepository):
        self.review_repository = review_repository

    @staticmethod
    def _build_user_display_name(
        user,
        member_status: MembershipStatus | None = None,
    ) -> str | None:
        """
        계정 탈퇴 또는 그룹 탈퇴 상태를 반영한 사용자 표시명을 반환
        """
        if not user:
            return None

        is_deactivated = user.is_active is False
        is_removed_member = member_status == MembershipStatus.REMOVED

        return (
            f"{user.username}(탈퇴)"
            if is_deactivated or is_removed_member
            else user.username
        )

    @staticmethod
    def _build_document_title(doc, summary) -> str:
        fallback_title = getattr(doc, "original_filename", None) or "요약 대기중"
        if not summary:
            return fallback_title
        return build_document_title(summary, fallback_title)

    @staticmethod
    def _build_preview(summary) -> str:
        if not summary:
            return ""
        return build_summary_preview(summary)

    def get_pending_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        uploader: str = "",
        assignee_type: str = "all",
        current_user_id: int | None = None,
    ) -> tuple[list[PendingDocumentListItemResponse], int]:
        limit = min(limit, 50)

        documents, total = self.review_repository.get_pending_list(
            skip,
            limit,
            keyword,
            group_id,
            uploader,
            assignee_type,
            current_user_id,
        )

        user_ids = []
        for doc, _ in documents:
            if getattr(doc, "owner", None):
                user_ids.append(doc.owner.id)

            approval = getattr(doc, "approval", None)
            assignee = getattr(approval, "assignee", None) if approval else None
            if assignee:
                user_ids.append(assignee.id)

        member_status_map = self.review_repository.get_member_status_map(
            group_id=group_id,
            user_ids=list(set(user_ids)),
        )

        results: list[PendingDocumentListItemResponse] = []

        for doc, comment_count in documents:
            summary = getattr(doc, "summary", None)
            approval = getattr(doc, "approval", None)
            assignee = getattr(approval, "assignee", None) if approval else None

            results.append(
                PendingDocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=self._build_document_title(doc, summary),
                    preview=self._build_preview(summary),
                    status=doc.processing_status.value,
                    approval_status=approval.status.value if approval else "",
                    document_type=doc.document_type,
                    category=doc.category,
                    created_at=doc.created_at,
                    uploader=self._build_user_display_name(
                        doc.owner,
                        member_status_map.get(doc.owner.id) if doc.owner else None,
                    ),
                    assignee_user_id=approval.assignee_user_id if approval else None,
                    assignee_username=self._build_user_display_name(
                        assignee,
                        member_status_map.get(assignee.id) if assignee else None,
                    ),
                    comment_count=comment_count,
                )
            )

        return results, total

    def get_pending_uploaders(self, group_id: int) -> list[str]:
        return self.review_repository.get_pending_uploaders(group_id)

    def approve_document(self, doc_id: int, user_id: int, group_id: int):
        doc = self.review_repository.get_review_target(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        approval = getattr(doc, "approval", None)

        if not approval or approval.status != ReviewStatus.PENDING_REVIEW:
            raise AppException(ErrorCode.DOC_NOT_PENDING_REVIEW)

        self.review_repository.update_document_approval(
            approval=approval,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=user_id,
            reviewed_at=utc_now_naive(),
        )
        self.review_repository.db.commit()

        index_approved_document.delay(doc.id)

        return {"message": "문서가 승인되었습니다."}

    def reject_document(self, doc_id: int, user_id: int, group_id: int, feedback: str):
        doc = self.review_repository.get_review_target(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        approval = getattr(doc, "approval", None)

        if not approval or approval.status != ReviewStatus.PENDING_REVIEW:
            raise AppException(ErrorCode.DOC_NOT_PENDING_REVIEW)

        self.review_repository.update_document_approval(
            approval=approval,
            status=ReviewStatus.REJECTED,
            reviewer_user_id=user_id,
            feedback=feedback,
            reviewed_at=utc_now_naive(),
        )

        self.review_repository.db.commit()

        return {"message": "문서가 반려되었습니다."}

    def get_approved_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        reviewer_user_id: int,
        uploader: str = "",
    ) -> tuple[list[ReviewedDocumentListItemResponse], int]:
        limit = min(limit, 50)

        documents, total = self.review_repository.get_approved_list(
            skip,
            limit,
            keyword,
            group_id,
            reviewer_user_id,
            uploader,
        )

        user_ids = []
        for doc, _ in documents:
            if getattr(doc, "owner", None):
                user_ids.append(doc.owner.id)

            approval = getattr(doc, "approval", None)
            assignee = getattr(approval, "assignee", None) if approval else None
            reviewer = getattr(approval, "reviewer", None) if approval else None

            if assignee:
                user_ids.append(assignee.id)
            if reviewer:
                user_ids.append(reviewer.id)

        member_status_map = self.review_repository.get_member_status_map(
            group_id=group_id,
            user_ids=list(set(user_ids)),
        )

        results: list[ReviewedDocumentListItemResponse] = []

        for doc, comment_count in documents:
            summary = getattr(doc, "summary", None)
            approval = getattr(doc, "approval", None)
            assignee = getattr(approval, "assignee", None) if approval else None
            reviewer = getattr(approval, "reviewer", None) if approval else None

            results.append(
                ReviewedDocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=self._build_document_title(doc, summary),
                    preview=self._build_preview(summary),
                    status=doc.processing_status.value,
                    approval_status=approval.status.value if approval else "",
                    document_type=doc.document_type,
                    category=doc.category,
                    created_at=doc.created_at,
                    uploader=self._build_user_display_name(
                        doc.owner,
                        member_status_map.get(doc.owner.id) if doc.owner else None,
                    ),
                    assignee_user_id=approval.assignee_user_id if approval else None,
                    assignee_username=self._build_user_display_name(
                        assignee,
                        member_status_map.get(assignee.id) if assignee else None,
                    ),
                    reviewed_at=approval.reviewed_at if approval else None,
                    reviewer_username=self._build_user_display_name(
                        reviewer,
                        member_status_map.get(reviewer.id) if reviewer else None,
                    ),
                    feedback=approval.feedback if approval else None,
                    comment_count=comment_count,
                )
            )

        return results, total

    def get_approved_uploaders(self, group_id: int, reviewer_user_id: int) -> list[str]:
        return self.review_repository.get_approved_uploaders(group_id, reviewer_user_id)

    def get_rejected_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        reviewer_user_id: int,
        uploader: str = "",
    ) -> tuple[list[ReviewedDocumentListItemResponse], int]:
        limit = min(limit, 50)

        documents, total = self.review_repository.get_rejected_list(
            skip,
            limit,
            keyword,
            group_id,
            reviewer_user_id,
            uploader,
        )

        user_ids = []
        for doc, _ in documents:
            if getattr(doc, "owner", None):
                user_ids.append(doc.owner.id)

            approval = getattr(doc, "approval", None)
            assignee = getattr(approval, "assignee", None) if approval else None
            reviewer = getattr(approval, "reviewer", None) if approval else None

            if assignee:
                user_ids.append(assignee.id)
            if reviewer:
                user_ids.append(reviewer.id)

        member_status_map = self.review_repository.get_member_status_map(
            group_id=group_id,
            user_ids=list(set(user_ids)),
        )

        results: list[ReviewedDocumentListItemResponse] = []

        for doc, comment_count in documents:
            summary = getattr(doc, "summary", None)
            approval = getattr(doc, "approval", None)
            assignee = getattr(approval, "assignee", None) if approval else None
            reviewer = getattr(approval, "reviewer", None) if approval else None

            results.append(
                ReviewedDocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=self._build_document_title(doc, summary),
                    preview=self._build_preview(summary),
                    status=doc.processing_status.value,
                    approval_status=approval.status.value if approval else "",
                    document_type=doc.document_type,
                    category=doc.category,
                    created_at=doc.created_at,
                    uploader=self._build_user_display_name(
                        doc.owner,
                        member_status_map.get(doc.owner.id) if doc.owner else None,
                    ),
                    assignee_user_id=approval.assignee_user_id if approval else None,
                    assignee_username=self._build_user_display_name(
                        assignee,
                        member_status_map.get(assignee.id) if assignee else None,
                    ),
                    reviewed_at=approval.reviewed_at if approval else None,
                    reviewer_username=self._build_user_display_name(
                        reviewer,
                        member_status_map.get(reviewer.id) if reviewer else None,
                    ),
                    feedback=approval.feedback if approval else None,
                    comment_count=comment_count,
                )
            )

        return results, total

    def get_rejected_uploaders(self, group_id: int, reviewer_user_id: int) -> list[str]:
        return self.review_repository.get_rejected_uploaders(group_id, reviewer_user_id)
