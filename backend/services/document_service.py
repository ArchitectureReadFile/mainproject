import os

from errors import AppException, ErrorCode
from models.model import (
    DocumentLifecycleStatus,
    MembershipRole,
    ReviewStatus,
)
from repositories.document_repository import DocumentRepository
from schemas.document import (
    DocumentDetailResponse,
    DocumentListItemResponse,
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

    def _get_document_in_group_with_permission(
        self,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ):
        """그룹 문서를 조회하고 상세/원문 열람 권한을 함께 검증"""
        doc = self.repository.get_detail(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        approval = getattr(doc, "approval", None)
        approval_status = approval.status if approval else None

        is_uploader = doc.uploader_user_id == current_user_id
        is_owner_or_admin = current_user_role in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )

        if doc.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING:
            if not (is_uploader or is_owner_or_admin):
                raise AppException(ErrorCode.AUTH_FORBIDDEN)
        elif doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)
        elif approval_status != ReviewStatus.APPROVED:
            if not (is_uploader or is_owner_or_admin):
                raise AppException(ErrorCode.AUTH_FORBIDDEN)

        return doc

    def get_detail_in_group(
        self,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> DocumentDetailResponse:
        """그룹 문서 상세 정보를 반환"""
        doc = self._get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        approval = getattr(doc, "approval", None)
        assignee = getattr(approval, "assignee", None) if approval else None
        is_uploader = doc.uploader_user_id == current_user_id
        is_owner_or_admin = current_user_role in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )

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
            "delete_requested_at": doc.delete_requested_at,
            "delete_scheduled_at": doc.delete_scheduled_at,
            "deleted_by": doc.deleted_by_user_id,
            "deleted_by_username": doc.deleted_by.username if doc.deleted_by else None,
        }

        if summary:
            response_data["summary_text"] = get_summary_field(summary, "summary_text")
            response_data["key_points"] = get_key_points(summary)
            response_data["metadata"] = parse_summary_metadata(summary)
            response_data["document_type"] = get_summary_field(summary, "document_type")

            for field in SUMMARY_METADATA_FIELDS:
                response_data[field] = get_summary_field(summary, field)

        return DocumentDetailResponse(**response_data)

    def get_original_file_in_group(
        self,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> tuple[str, str]:
        """그룹 문서의 원본 PDF 경로와 파일명을 반환"""
        doc = self._get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        if not doc.stored_path or not os.path.exists(doc.stored_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        return doc.stored_path, doc.original_filename

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

        if not is_uploader and doc.uploader_user_id:
            from models.model import NotificationType
            from repositories.notification_repository import NotificationRepository
            from services.notification_service import NotificationService

            notif_service = NotificationService()
            notif_repo = NotificationRepository(self.repository.db)
            notif_service.create_notification_sync(
                repository=notif_repo,
                user_id=doc.uploader_user_id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.DOCUMENT_DELETED,
                title="문서 삭제 알림",
                body=f"회원님의 문서 '{doc.original_filename}'이(가) 관리자에 의해 삭제되었습니다.",
                target_type="group",
                target_id=group_id,
            )

    def restore_document(self, doc_id: int, user_id: int, group_id: int) -> None:
        doc = self.repository.get_detail(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.DELETE_PENDING:
            raise AppException(ErrorCode.DOC_NOT_DELETE_PENDING)

        is_uploader = doc.uploader_user_id == user_id
        is_group_admin = self.repository.is_group_admin(user_id, group_id)

        if not (is_uploader or is_group_admin):
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        self.repository.restore_document(doc)

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
