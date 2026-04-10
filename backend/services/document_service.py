import os

from errors import AppException, ErrorCode
from models.model import (
    DocumentLifecycleStatus,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
)
from repositories.document_repository import DocumentRepository
from schemas.document import (
    DocumentDetailResponse,
    DocumentListItemResponse,
)
from services.document_preview_service import DocumentPreviewService
from services.summary.summary_mapper import (
    SUMMARY_METADATA_FIELDS,
    build_document_title,
    build_summary_preview,
    get_key_points,
    get_summary_field,
    parse_summary_metadata,
)

# SUMMARY_METADATA_FIELDS 중 Document 모델이 source of truth인 필드
# summary 루프에서 이 필드들은 건너뛴다
_CLASSIFICATION_FIELDS = frozenset({"document_type"})


class DocumentService:
    def __init__(self, repository: DocumentRepository):
        self.repository = repository
        self.preview_service = DocumentPreviewService(repository)

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
        """
        문서 목록 응답
        목록 카드에서 바로 사용할 수 있도록 댓글 수를 함께 전달
        """
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

        owner_ids = [
            doc.owner.id for doc, _ in documents if getattr(doc, "owner", None)
        ]

        member_status_map = (
            self.repository.get_member_status_map(
                group_id=group_id,
                user_ids=owner_ids,
            )
            if group_id is not None
            else {}
        )

        results: list[DocumentListItemResponse] = []

        for doc, comment_count in documents:
            summary = getattr(doc, "summary", None)
            approval = getattr(doc, "approval", None)
            title = self._build_document_title(doc, summary)
            preview = self._build_preview(summary)

            owner_status = (
                member_status_map.get(doc.owner.id)
                if getattr(doc, "owner", None)
                else None
            )

            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=title,
                    preview=preview,
                    status=doc.processing_status.value,
                    approval_status=approval.status.value if approval else None,
                    document_type=doc.document_type,
                    category=doc.category,
                    created_at=doc.created_at,
                    uploader=self._build_user_display_name(doc.owner, owner_status),
                    comment_count=comment_count,
                    delete_requested_at=None,
                    delete_scheduled_at=None,
                    deleted_by=None,
                )
            )

        return results, total

    def get_document_in_group_with_permission(
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
        doc = self.get_document_in_group_with_permission(
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

        users_for_display = [
            user.id
            for user in [doc.owner, assignee, doc.deleted_by]
            if user is not None
        ]
        member_status_map = self.repository.get_member_status_map(
            group_id=doc.group_id,
            user_ids=users_for_display,
        )

        preview_path = (getattr(doc, "preview_pdf_path", None) or "").strip()

        response_data = {
            "id": doc.id,
            "uploader": self._build_user_display_name(
                doc.owner,
                member_status_map.get(doc.owner.id) if doc.owner else None,
            ),
            "summary_id": summary.id if summary else None,
            "title": title,
            "status": doc.processing_status.value,
            "approval_status": approval.status.value if approval else None,
            "assignee_user_id": approval.assignee_user_id if approval else None,
            "assignee_username": self._build_user_display_name(
                assignee,
                member_status_map.get(assignee.id) if assignee else None,
            ),
            "feedback": approval.feedback
            if approval and approval.status == ReviewStatus.REJECTED
            else None,
            "created_at": doc.created_at,
            "can_delete": is_uploader or is_owner_or_admin,
            "delete_requested_at": doc.delete_requested_at,
            "delete_scheduled_at": doc.delete_scheduled_at,
            "deleted_by": doc.deleted_by_user_id,
            "deleted_by_username": self._build_user_display_name(
                doc.deleted_by,
                member_status_map.get(doc.deleted_by.id) if doc.deleted_by else None,
            ),
            # source of truth: Document 모델 — summary 루프보다 먼저, 덮어쓰지 않음
            "document_type": doc.document_type,
            "category": doc.category,
            "original_filename": doc.original_filename,
            "original_content_type": getattr(doc, "original_content_type", None),
            "preview_status": (
                doc.preview_status.value
                if getattr(doc, "preview_status", None)
                else None
            ),
            "preview_available": bool(preview_path and os.path.exists(preview_path)),
        }

        if summary:
            response_data["summary_text"] = get_summary_field(summary, "summary_text")
            response_data["key_points"] = get_key_points(summary)
            response_data["metadata"] = parse_summary_metadata(summary)

            # _CLASSIFICATION_FIELDS에 속한 필드는 Document 모델이 source of truth이므로
            # summary metadata 루프에서 제외한다
            for field in SUMMARY_METADATA_FIELDS:
                if field in _CLASSIFICATION_FIELDS:
                    continue
                response_data[field] = get_summary_field(summary, field)

        return DocumentDetailResponse(**response_data)

    def get_original_file_in_group(
        self,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> tuple[str, str]:
        """그룹 문서의 원본 파일 경로와 파일명을 반환"""
        doc = self.get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        if not doc.stored_path or not os.path.exists(doc.stored_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        return doc.stored_path, doc.original_filename

    def update_classification(
        self,
        doc_id: int,
        group_id: int,
        *,
        document_type: str,
        category: str,
    ) -> None:
        """
        분류값 수동 수정.
        승인된 문서인 경우 Qdrant payload 동기화를 위해 재인덱싱 태스크를 큐에 넣는다.
        이력 저장은 1차에서 하지 않는다.
        """
        doc = self.repository.get_by_id(doc_id)
        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)
        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        self.repository.update_classification(
            doc_id,
            document_type=document_type,
            category=category,
        )
        self.repository.db.commit()

        # 승인된 문서는 Qdrant에 이전 분류값이 남아 있으므로 재인덱싱으로 동기화
        approval = getattr(doc, "approval", None)
        if approval and approval.status == ReviewStatus.APPROVED:
            from tasks.group_document_task import index_approved_document

            index_approved_document.delay(doc_id)

    def get_unclassified_list(
        self,
        group_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[DocumentListItemResponse], int]:
        """
        미분류 문서 목록 반환.
        운영에서 재처리 대상 식별 및 수동 수정 진입점으로 사용한다.
        """
        documents, total = self.repository.get_unclassified_list(group_id, skip, limit)

        owner_ids = [doc.owner.id for doc in documents if getattr(doc, "owner", None)]
        member_status_map = self.repository.get_member_status_map(
            group_id=group_id,
            user_ids=owner_ids,
        )

        results = []
        for doc in documents:
            summary = getattr(doc, "summary", None)
            owner_status = (
                member_status_map.get(doc.owner.id)
                if getattr(doc, "owner", None)
                else None
            )
            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=self._build_document_title(doc, summary),
                    preview=self._build_preview(summary),
                    status=doc.processing_status.value,
                    document_type=doc.document_type,
                    category=doc.category,
                    created_at=doc.created_at,
                    uploader=self._build_user_display_name(doc.owner, owner_status),
                    delete_requested_at=None,
                    delete_scheduled_at=None,
                    deleted_by=None,
                )
            )

        return results, total

    def get_preview_file_in_group(
        self,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> tuple[str, str]:
        """
        그룹 문서의 preview PDF 경로와 브라우저 표시용 파일명을 반환
        """
        doc = self.get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        preview_path = self.preview_service.ensure_preview_pdf(doc)

        download_name = os.path.splitext(doc.original_filename or f"document_{doc.id}")[
            0
        ]
        preview_filename = f"{download_name}.pdf"
        return preview_path, preview_filename

    def delete_document(self, doc_id: int, user_id: int, group_id: int) -> None:
        """문서를 삭제 대기 상태로 전환하고 필요 시 RAG 제거를 큐에 적재한다."""
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

        approval_status = getattr(doc.approval, "status", None)

        self.repository.delete_document(doc, user_id)

        if approval_status == ReviewStatus.APPROVED:
            from tasks.group_document_task import deindex_document

            deindex_document.delay(doc.id)

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
        """삭제 대기 문서를 복구하고 필요 시 재인덱싱을 큐에 적재한다."""
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

        approval_status = getattr(doc.approval, "status", None)

        self.repository.restore_document(doc)

        if approval_status == ReviewStatus.APPROVED:
            from tasks.group_document_task import index_approved_document

            index_approved_document.delay(doc.id)

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

        owner_ids = [doc.owner.id for doc in documents if getattr(doc, "owner", None)]
        member_status_map = (
            self.repository.get_member_status_map(
                group_id=group_id,
                user_ids=owner_ids,
            )
            if group_id is not None
            else {}
        )

        results = []

        for doc in documents:
            summary = getattr(doc, "summary", None)
            owner_status = (
                member_status_map.get(doc.owner.id)
                if getattr(doc, "owner", None)
                else None
            )

            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=self._build_document_title(doc, summary),
                    preview=self._build_preview(summary),
                    status=doc.processing_status.value,
                    category=doc.category,
                    approval_status=getattr(doc.approval, "status", None).value
                    if getattr(doc, "approval", None)
                    else None,
                    document_type=get_summary_field(summary, "document_type")
                    if summary
                    else None,
                    created_at=doc.created_at,
                    uploader=self._build_user_display_name(doc.owner, owner_status),
                    comment_count=0,
                    delete_requested_at=doc.delete_requested_at,
                    delete_scheduled_at=doc.delete_scheduled_at,
                    deleted_by=doc.deleted_by_user_id,
                )
            )

        return results, total
