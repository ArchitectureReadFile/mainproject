from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from errors import AppException, ErrorCode
from models.model import User
from repositories.document_repository import DocumentRepository
from routers.auth import get_current_user
from routers.group import get_group_service
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

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise AppException(ErrorCode.DOC_FILE_TOO_LARGE)

    group_service.assert_upload_permission(current_user.id, group_id)

    service = UploadService(DocumentRepository(db))
    return service.handle_upload([file], user_id=current_user.id, group_id=group_id)
