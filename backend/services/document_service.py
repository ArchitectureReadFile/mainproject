from errors import AppException, ErrorCode
from models.model import (
    DocumentLifecycleStatus,
    MembershipRole,
    ReviewStatus,
    utc_now_naive,
)
from repositories.document_repository import DocumentRepository
from schemas.document import (
    DocumentDetailResponse,
    DocumentListItemResponse,
    PendingDocumentListItemResponse,
    ReviewedDocumentListItemResponse,
)
from services.summary.summary_mapper import (
    SUMMARY_METADATA_FIELDS,
    build_document_title,
    build_summary_preview,
    get_key_points,
    get_summary_field,
    parse_summary_metadata,
)


class DocumentService:
    def __init__(self, repository: DocumentRepository):
        self.repository = repository

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

    def get_list(
        self,
        skip,
        limit,
        keyword,
        status,
        user_id,
        view_type="all",
        category="전체",
        group_id=None,
    ):
        limit = min(limit, 50)
        documents, total = self.repository.get_list(
            skip,
            limit,
            keyword,
            status,
            user_id,
            view_type,
            category,
            group_id,
        )

        results: list[DocumentListItemResponse] = []

        for doc in documents:
            summary = getattr(doc, "summary", None)
            approval = getattr(doc, "approval", None)
            title = self._build_document_title(doc, summary)
            preview = self._build_preview(summary)

            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=title,
                    preview=preview,
                    status=doc.processing_status.value,
                    approval_status=approval.status.value if approval else None,
                    document_type=get_summary_field(summary, "document_type")
                    if summary
                    else None,
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    delete_requested_at=None,
                    delete_scheduled_at=None,
                    deleted_by=None,
                )
            )

        return results, total

    def get_detail_in_group(
        self,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> DocumentDetailResponse:
        doc = self.repository.get_detail(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        approval = getattr(doc, "approval", None)
        approval_status = approval.status if approval else None
        assignee = getattr(approval, "assignee", None) if approval else None

        is_uploader = doc.uploader_user_id == current_user_id
        is_owner_or_admin = current_user_role in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )

        if approval_status != ReviewStatus.APPROVED:
            if not (is_uploader or is_owner_or_admin):
                raise AppException(ErrorCode.AUTH_FORBIDDEN)

        summary = getattr(doc, "summary", None)
        title = self._build_document_title(doc, summary)

        response_data = {
            "id": doc.id,
            "uploader": doc.owner.username if doc.owner else None,
            "summary_id": summary.id if summary else None,
            "title": title,
            "status": doc.processing_status.value,
            "approval_status": approval.status.value if approval else None,
            "assignee_user_id": approval.assignee_user_id if approval else None,
            "assignee_username": assignee.username if assignee else None,
            "feedback": approval.feedback
            if approval and approval.status == ReviewStatus.REJECTED
            else None,
            "created_at": doc.created_at,
            "can_delete": is_uploader or is_owner_or_admin,
        }

        if summary:
            response_data["summary_text"] = get_summary_field(summary, "summary_text")
            response_data["key_points"] = get_key_points(summary)
            response_data["metadata"] = parse_summary_metadata(summary)
            response_data["document_type"] = get_summary_field(summary, "document_type")

            for field in SUMMARY_METADATA_FIELDS:
                response_data[field] = get_summary_field(summary, field)

        return DocumentDetailResponse(**response_data)

    def delete_document(self, doc_id: int, user_id: int, group_id: int) -> None:
        doc = self.repository.get_detail(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING:
            raise AppException(ErrorCode.DOC_ALREADY_DELETE_PENDING)

        is_uploader = doc.uploader_user_id == user_id

        is_group_admin = self.repository.is_group_admin(user_id, group_id)

        if not (is_uploader or is_group_admin):
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        self.repository.delete_document(doc, user_id)

    def get_deleted_list(
        self,
        skip,
        limit,
        user_id,
        group_id=None,
    ) -> tuple[list[DocumentListItemResponse], int]:
        documents, total = self.repository.get_deleted_list(
            skip,
            limit,
            user_id,
            group_id,
        )

        results = []

        for doc in documents:
            summary = getattr(doc, "summary", None)

            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=self._build_document_title(doc, summary),
                    preview=self._build_preview(summary),
                    status=doc.processing_status.value,
                    document_type=get_summary_field(summary, "document_type")
                    if summary
                    else None,
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    delete_requested_at=doc.delete_requested_at,
                    delete_scheduled_at=doc.delete_scheduled_at,
                    deleted_by=doc.deleted_by_user_id,
                )
            )

        return results, total

    def get_pending_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
    ) -> tuple[list[PendingDocumentListItemResponse], int]:
        """그룹 내 승인 대기 문서 전체 조회"""
        limit = min(limit, 50)

        documents, total = self.repository.get_pending_list(
            skip, limit, keyword, group_id
        )

        results: list[PendingDocumentListItemResponse] = []

        for doc in documents:
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
                    document_type=get_summary_field(summary, "document_type")
                    if summary
                    else None,
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    assignee_user_id=approval.assignee_user_id if approval else None,
                    assignee_username=assignee.username if assignee else None,
                )
            )

        return results, total

    def approve_document(self, doc_id: int, user_id: int, group_id: int):
        """승인"""
        doc = self.repository.get_review_target(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        approval = getattr(doc, "approval", None)

        if not approval or approval.status != ReviewStatus.PENDING_REVIEW:
            raise AppException(ErrorCode.DOC_NOT_PENDING_REVIEW)

        self.repository.update_document_approval(
            approval=approval,
            status=ReviewStatus.APPROVED,
            reviewer_user_id=user_id,
            reviewed_at=utc_now_naive(),
        )
        self.repository.db.commit()

        from tasks.group_document_task import index_approved_document

        index_approved_document.delay(doc.id)

        return {"message": "문서가 승인되었습니다."}

    def reject_document(self, doc_id: int, user_id: int, group_id: int, feedback: str):
        """반려"""
        doc = self.repository.get_review_target(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        approval = getattr(doc, "approval", None)

        if not approval or approval.status != ReviewStatus.PENDING_REVIEW:
            raise AppException(ErrorCode.DOC_NOT_PENDING_REVIEW)

        self.repository.update_document_approval(
            approval=approval,
            status=ReviewStatus.REJECTED,
            reviewer_user_id=user_id,
            feedback=feedback,
            reviewed_at=utc_now_naive(),
        )

        self.repository.db.commit()

        return {"message": "문서가 반려되었습니다."}

    def get_approved_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        reviewer_user_id: int,
    ) -> tuple[list[ReviewedDocumentListItemResponse], int]:
        """그룹 내 내가 승인한 문서 조회"""
        limit = min(limit, 50)

        documents, total = self.repository.get_approved_list(
            skip,
            limit,
            keyword,
            group_id,
            reviewer_user_id,
        )

        results: list[ReviewedDocumentListItemResponse] = []

        for doc in documents:
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
                    document_type=get_summary_field(summary, "document_type")
                    if summary
                    else None,
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    assignee_user_id=approval.assignee_user_id if approval else None,
                    assignee_username=assignee.username if assignee else None,
                    reviewed_at=approval.reviewed_at if approval else None,
                    reviewer_username=reviewer.username if reviewer else None,
                    feedback=approval.feedback if approval else None,
                )
            )

        return results, total

    def get_rejected_list(
        self,
        skip: int,
        limit: int,
        keyword: str,
        group_id: int,
        reviewer_user_id: int,
    ) -> tuple[list[ReviewedDocumentListItemResponse], int]:
        """그룹 내 내가 반려한 문서 조회"""
        limit = min(limit, 50)

        documents, total = self.repository.get_rejected_list(
            skip,
            limit,
            keyword,
            group_id,
            reviewer_user_id,
        )

        results: list[ReviewedDocumentListItemResponse] = []

        for doc in documents:
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
                    document_type=get_summary_field(summary, "document_type")
                    if summary
                    else None,
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    assignee_user_id=approval.assignee_user_id if approval else None,
                    assignee_username=assignee.username if assignee else None,
                    reviewed_at=approval.reviewed_at if approval else None,
                    reviewer_username=reviewer.username if reviewer else None,
                    feedback=approval.feedback if approval else None,
                )
            )

        return results, total
