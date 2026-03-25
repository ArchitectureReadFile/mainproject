from errors import AppException, ErrorCode
from models.model import (
    DocumentLifecycleStatus,
)
from repositories.document_repository import DocumentRepository
from schemas.document import DocumentDetailResponse, DocumentListItemResponse
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
            title = self._build_document_title(doc, summary)
            preview = self._build_preview(summary)

            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=title,
                    preview=preview,
                    status=doc.processing_status.value,
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    delete_requested_at=None,
                    delete_scheduled_at=None,
                    deleted_by=None,
                )
            )

        return results, total

    def get_detail_in_group(self, doc_id: int, group_id: int) -> DocumentDetailResponse:
        doc = self.repository.get_detail(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.group_id != group_id:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        if doc.lifecycle_status != DocumentLifecycleStatus.ACTIVE:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        summary = getattr(doc, "summary", None)

        response_data = {
            "id": doc.id,
            "uploader": doc.owner.username if doc.owner else None,
            "summary_id": summary.id if summary else None,
            "status": doc.processing_status.value,
            "created_at": doc.created_at,
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
                    created_at=doc.created_at,
                    uploader=doc.owner.username if doc.owner else None,
                    delete_requested_at=doc.delete_requested_at,
                    delete_scheduled_at=doc.delete_scheduled_at,
                    deleted_by=doc.deleted_by_user_id,
                )
            )

        return results, total
