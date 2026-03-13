from errors import AppException, ErrorCode
from repositories.document_repository import DocumentRepository
from schemas.document import DocumentDetailResponse, DocumentListItemResponse


class DocumentService:
    def __init__(self, repository: DocumentRepository):
        self.repository = repository

    def get_list(
        self,
        skip,
        limit,
        keyword,
        status,
        user_id,
        user_role,
        view_type="all",
        category="전체",
    ):
        limit = min(limit, 50)
        documents, total = self.repository.get_list(
            skip, limit, keyword, status, user_id, user_role, view_type, category
        )

        results: list[DocumentListItemResponse] = []

        for doc in documents:
            summary = getattr(doc, "summary", None)
            title = doc.document_url or "요약 대기중"
            preview = ""

            if summary:
                case_number = getattr(summary, "case_number", None)
                case_name = getattr(summary, "case_name", None)

                if case_number and case_name:
                    title = f"{case_number} {case_name}"
                elif case_name:
                    title = case_name
                elif case_number:
                    title = case_number
                else:
                    title = getattr(summary, "summary_title", None) or title

                main_text = getattr(summary, "summary_main", "")
                if main_text:
                    preview = (
                        (main_text[:200] + "...") if len(main_text) > 200 else main_text
                    )

            results.append(
                DocumentListItemResponse(
                    id=doc.id,
                    summary_id=summary.id if summary else None,
                    title=title,
                    preview=preview,
                    status=doc.status.value,
                    created_at=doc.created_at,
                    court_name=getattr(summary, "court_name", None)
                    if summary
                    else None,
                    judgment_date=getattr(summary, "judgment_date", None)
                    if summary
                    else None,
                    uploader=doc.owner.username if doc.owner else None,
                )
            )

        return results, total

    def get_detail(self, doc_id: int) -> DocumentDetailResponse:
        doc = self.repository.get_detail(doc_id)

        if not doc:
            raise AppException(ErrorCode.DOC_NOT_FOUND)

        summary = getattr(doc, "summary", None)

        response_data = {
            "id": doc.id,
            "uploader": doc.owner.username if doc.owner else None,
            "summary_id": summary.id if summary else None,
            "status": doc.status.value,
            "created_at": doc.created_at,
        }

        if summary:
            summary_fields = [
                "case_number",
                "case_name",
                "court_name",
                "judgment_date",
                "summary_title",
                "summary_main",
                "plaintiff",
                "defendant",
                "facts",
                "judgment_order",
                "judgment_reason",
                "related_laws",
            ]
            for field in summary_fields:
                response_data[field] = getattr(summary, field, None)

        return DocumentDetailResponse(**response_data)

    def delete_document(self, doc_id: int, user_id: int, user_role: str) -> None:
        self.repository.delete_document(doc_id, user_id, user_role)
