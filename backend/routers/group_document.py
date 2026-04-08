import mimetypes
from typing import Literal, Optional
import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from errors import AppException, ErrorCode
from models.model import User
from repositories.document_comment_repository import DocumentCommentRepository
from repositories.document_repository import DocumentRepository
from repositories.document_review_repository import DocumentReviewRepository
from repositories.group_repository import GroupRepository
from routers.auth import get_current_user
from routers.group import get_group_service
from schemas.comment import (
    DocumentCommentCreateRequest,
    DocumentCommentListResponse,
    DocumentCommentResponse,
)
from schemas.document import DocumentDetailResponse, DocumentRejectRequest
from services.document_comment_service import DocumentCommentService
from services.document_review_service import DocumentReviewService
from services.document_service import DocumentService
from services.group_service import GroupService
from services.upload.service import UploadService

router = APIRouter(prefix="/groups", tags=["group-documents"])

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
}


def _is_allowed_upload_file(file: UploadFile) -> bool:
    """
    업로드 허용 문서인지 검사

    content_type은 브라우저/OS 환경에 따라 비어 있거나 다르게 올 수 있으므로
    확장자와 함께 느슨하게 검사
    """
    filename = (file.filename or "").lower()
    ext = os.path.splitext(filename)[1]
    content_type = (file.content_type or "").lower()

    return content_type in ALLOWED_CONTENT_TYPES or ext in ALLOWED_EXTENSIONS

DocumentTypeLiteral = Literal[
    "계약서",
    "신청서",
    "준비서면",
    "의견서",
    "내용증명",
    "소장",
    "고소장",
    "기타",
    "미분류",
]
DocumentCategoryLiteral = Literal[
    "민사", "계약", "회사", "행정", "형사", "노동", "기타", "미분류"
]


class ClassificationUpdateRequest(BaseModel):
    document_type: DocumentTypeLiteral
    category: DocumentCategoryLiteral


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(DocumentRepository(db))


def get_document_review_service(
    db: Session = Depends(get_db),
) -> DocumentReviewService:
    return DocumentReviewService(DocumentReviewRepository(db))


def get_document_comment_service(
    db: Session = Depends(get_db),
) -> DocumentCommentService:
    document_repository = DocumentRepository(db)

    return DocumentCommentService(
        comment_repository=DocumentCommentRepository(db),
        document_service=DocumentService(document_repository),
        group_repository=GroupRepository(db),
    )


@router.post("/{group_id}/documents/upload")
def upload_group_document(
    group_id: int,
    file: UploadFile = File(...),
    assignee_user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    if not _is_allowed_upload_file(file):
        raise AppException(ErrorCode.DOC_INVALID_FILE_TYPE)

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise AppException(ErrorCode.DOC_FILE_TOO_LARGE)

    _, role = group_service.assert_upload_permission(current_user.id, group_id)

    service = UploadService(DocumentRepository(db), group_service)
    return service.handle_upload(
        [file],
        user_id=current_user.id,
        group_id=group_id,
        uploader_role=role,
        assignee_user_id=assignee_user_id,
    )


@router.get("/{group_id}/documents")
def list_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 5,
    keyword: str = "",
    status: str = "",
    view_type: str = "all",
    category: str = "전체",
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_view_permission(current_user.id, group_id)

    items, total = service.get_list(
        skip,
        limit,
        keyword,
        status,
        user_id=current_user.id,
        view_type=view_type,
        category=category,
        group_id=group_id,
    )
    return {"items": items, "total": total}


@router.get("/{group_id}/documents/unclassified")
def list_unclassified_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 50,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    """미분류 문서 목록. 운영에서 재처리 대상 식별 및 수동 수정 진입점."""
    group_service.assert_review_view_permission(current_user.id, group_id)

    items, total = service.get_unclassified_list(group_id, skip, limit)
    return {"items": items, "total": total}


@router.get("/{group_id}/documents/pending")
def list_pending_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 5,
    keyword: str = "",
    uploader: str = "",
    assignee_type: str = "all",
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_view_permission(current_user.id, group_id)
    items, total = service.get_pending_list(
        skip,
        limit,
        keyword,
        group_id,
        uploader,
        assignee_type,
        current_user.id,
    )

    return {"items": items, "total": total}


@router.get("/{group_id}/documents/pending/uploaders")
def list_pending_uploaders(
    group_id: int,
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_view_permission(current_user.id, group_id)
    items = service.get_pending_uploaders(group_id)

    return {"items": items}


@router.get("/{group_id}/documents/approved")
def list_approved_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 10,
    keyword: str = "",
    uploader: str = "",
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_view_permission(current_user.id, group_id)
    items, total = service.get_approved_list(
        skip,
        limit,
        keyword,
        group_id,
        current_user.id,
        uploader,
    )

    return {"items": items, "total": total}


@router.get("/{group_id}/documents/approved/uploaders")
def list_approved_uploaders(
    group_id: int,
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_view_permission(current_user.id, group_id)
    items = service.get_approved_uploaders(group_id, current_user.id)

    return {"items": items}


@router.get("/{group_id}/documents/rejected")
def list_rejected_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 10,
    keyword: str = "",
    uploader: str = "",
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_view_permission(current_user.id, group_id)
    items, total = service.get_rejected_list(
        skip,
        limit,
        keyword,
        group_id,
        current_user.id,
        uploader,
    )

    return {"items": items, "total": total}


@router.get("/{group_id}/documents/rejected/uploaders")
def list_rejected_uploaders(
    group_id: int,
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_view_permission(current_user.id, group_id)
    items = service.get_rejected_uploaders(group_id, current_user.id)

    return {"items": items}


@router.get("/{group_id}/documents/deleted")
def list_deleted_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 5,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    group_service.assert_view_permission(current_user.id, group_id)

    items, total = service.get_deleted_list(
        skip,
        limit,
        user_id=current_user.id,
        group_id=group_id,
    )

    return {"items": items, "total": total}


@router.get("/{group_id}/documents/{doc_id}", response_model=DocumentDetailResponse)
def get_detail_document(
    group_id: int,
    doc_id: int,
    group_service: GroupService = Depends(get_group_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    _, role = group_service.assert_view_permission(current_user.id, group_id)

    return document_service.get_detail_in_group(
        doc_id=doc_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
    )


@router.patch("/{group_id}/documents/{doc_id}/classification")
def update_document_classification(
    group_id: int,
    doc_id: int,
    payload: ClassificationUpdateRequest,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    """
    분류값 수동 수정 (OWNER/ADMIN 전용).
    허용값 외 입력은 422로 거부된다.
    승인된 문서는 Qdrant 재인덱싱 태스크를 큐에 넣어 분류 동기화한다.
    이력 저장은 1차에서 하지 않는다.
    """
    group_service.assert_review_permission(current_user.id, group_id)
    service.update_classification(
        doc_id,
        group_id,
        document_type=payload.document_type,
        category=payload.category,
    )
    return {"message": "분류가 수정되었습니다."}



@router.get("/{group_id}/documents/{doc_id}/preview")
def view_preview_document(
    group_id: int,
    doc_id: int,
    group_service: GroupService = Depends(get_group_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    _, role = group_service.assert_view_permission(current_user.id, group_id)
    file_path, preview_filename = document_service.get_preview_file_in_group(
        doc_id=doc_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
    )

    encoded_filename = quote(preview_filename)

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"},
    )


@router.delete("/{group_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    group_id: int,
    doc_id: int,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group, _ = group_service.assert_view_permission(current_user.id, group_id)
    group_service.assert_group_writable(group)
    service.delete_document(doc_id, current_user.id, group_id)


@router.get("/{group_id}/documents/{doc_id}/download")
def download_original_document(
    group_id: int,
    doc_id: int,
    group_service: GroupService = Depends(get_group_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    _, role = group_service.assert_view_permission(current_user.id, group_id)
    file_path, original_filename = document_service.get_original_file_in_group(
        doc_id=doc_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
    )

    encoded_filename = quote(original_filename)
    media_type, _ = mimetypes.guess_type(original_filename)

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        headers={
            "Content-Disposition": (f"attachment; filename*=UTF-8''{encoded_filename}")
        },
    )


@router.get(
    "/{group_id}/documents/{doc_id}/comments",
    response_model=DocumentCommentListResponse,
)
def list_document_comments(
    group_id: int,
    doc_id: int,
    scope: str = Query("GENERAL", pattern="^(GENERAL|REVIEW)$"),
    service: DocumentCommentService = Depends(get_document_comment_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    _, role = group_service.assert_view_permission(current_user.id, group_id)

    return service.list_comments(
        doc_id=doc_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
        scope=scope,
    )


@router.post(
    "/{group_id}/documents/{doc_id}/comments",
    response_model=DocumentCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_comment(
    group_id: int,
    doc_id: int,
    payload: DocumentCommentCreateRequest,
    service: DocumentCommentService = Depends(get_document_comment_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group, role = group_service.assert_view_permission(current_user.id, group_id)
    group_service.assert_group_writable(group)

    return service.create_comment(
        doc_id=doc_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
        content=payload.content,
        parent_id=payload.parent_id,
        page=payload.page,
        x=payload.x,
        y=payload.y,
        scope=payload.scope,
        mentions=payload.mentions,
    )


@router.delete(
    "/{group_id}/comments/{comment_id}",
    response_model=DocumentCommentResponse,
)
def delete_document_comment(
    group_id: int,
    comment_id: int,
    service: DocumentCommentService = Depends(get_document_comment_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group, role = group_service.assert_view_permission(current_user.id, group_id)
    group_service.assert_group_writable(group)

    return service.delete_comment(
        comment_id=comment_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
    )


@router.post(
    "/{group_id}/documents/{doc_id}/restore", status_code=status.HTTP_204_NO_CONTENT
)
def restore_document(
    group_id: int,
    doc_id: int,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_view_permission(current_user.id, group_id)
    service.restore_document(doc_id, current_user.id, group_id)


@router.post("/{group_id}/documents/{doc_id}/approve")
def approve_document(
    group_id: int,
    doc_id: int,
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_permission(current_user.id, group_id)
    return service.approve_document(doc_id, current_user.id, group_id)


@router.post("/{group_id}/documents/{doc_id}/reject")
def reject_document(
    group_id: int,
    doc_id: int,
    payload: DocumentRejectRequest,
    service: DocumentReviewService = Depends(get_document_review_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_permission(current_user.id, group_id)
    return service.reject_document(doc_id, current_user.id, group_id, payload.feedback)
