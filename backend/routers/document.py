from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from errors import AppException, ErrorCode
from models.model import User
from repositories.document_repository import DocumentRepository
from routers.auth import get_current_user
from routers.group import get_group_service
from schemas.document import DocumentDetailResponse
from services.document_service import DocumentService
from services.group_service import GroupService
from services.upload.service import UploadService

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(DocumentRepository(db))


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
    group_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise AppException(ErrorCode.DOC_INVALID_FILE_TYPE)

    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise AppException(ErrorCode.DOC_FILE_TOO_LARGE)
    file.file.seek(0)

    group_service.assert_upload_permission(current_user.id, group_id)

    service = UploadService(DocumentRepository(db))
    return service.handle_upload([file], user_id=current_user.id, group_id=group_id)


@router.get("")
def list_documents(
    skip: int = 0,
    limit: int = 5,
    keyword: str = "",
    status: str = "",
    view_type: str = "my",
    category: str = "전체",
    group_id: int | None = None,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    if group_id is not None:
        group_service.assert_upload_permission(current_user.id, group_id)

    items, total = service.get_list(
        skip,
        limit,
        keyword,
        status,
        user_id=current_user.id,
        user_role=current_user.role.value,
        view_type=view_type,
        category=category,
        group_id=group_id,
    )
    return {"items": items, "total": total}


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
def get_detail_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DocumentService(DocumentRepository(db)).get_detail(doc_id)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: int,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    service.delete_document(doc_id, current_user.id, current_user.role.value)
