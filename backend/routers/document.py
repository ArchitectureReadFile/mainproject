from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from errors import AppException, ErrorCode
from models.model import User
from repositories.document_repository import DocumentRepository
from routers.auth import get_current_user
from schemas.document import DocumentDetailResponse
from schemas.upload_session import UploadSessionCreateRequest, UploadSessionResponse
from services.document_service import DocumentService
from services.upload_service import UploadService
from services.upload_session_service import UploadSessionService

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(DocumentRepository(db))


def _to_upload_session_response(payload: dict) -> dict:
    items = payload.get("items", [])
    return {
        "items": items,
        "is_running": any(item["status"] == "processing" for item in items),
        "started_at": payload.get("started_at"),
        "abandoned_at": payload.get("abandoned_at"),
    }


@router.post("/upload-session", response_model=UploadSessionResponse)
def create_upload_session(
    payload: UploadSessionCreateRequest,
    current_user: User = Depends(get_current_user),
):
    service = UploadSessionService()
    session = service.create_session(current_user.id, payload.file_names)
    return _to_upload_session_response(session)


@router.get("/upload-session", response_model=UploadSessionResponse)
def get_upload_session(current_user: User = Depends(get_current_user)):
    service = UploadSessionService()
    session = service.get_session(current_user.id)
    return _to_upload_session_response(session)


@router.post("/upload-session/abandon", response_model=UploadSessionResponse)
def abandon_upload_session(current_user: User = Depends(get_current_user)):
    service = UploadSessionService()
    session = service.abandon_session(current_user.id)
    return _to_upload_session_response(session)


@router.delete("/upload-session", status_code=status.HTTP_204_NO_CONTENT)
def clear_upload_session(current_user: User = Depends(get_current_user)):
    service = UploadSessionService()
    service.clear_session(current_user.id)


@router.post("/upload")
def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise AppException(ErrorCode.DOC_INVALID_FILE_TYPE)

    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise AppException(ErrorCode.DOC_FILE_TOO_LARGE)
    file.file.seek(0)

    service = UploadService(DocumentRepository(db))
    return service.handle_upload([file], background_tasks, user_id=current_user.id)


@router.get("")
def list_documents(
    skip: int = 0,
    limit: int = 5,
    keyword: str = "",
    status: str = "",
    view_type: str = "my",
    category: str = "전체",
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    items, total = service.get_list(
        skip,
        limit,
        keyword,
        status,
        user_id=current_user.id,
        user_role=current_user.role.value,
        view_type=view_type,
        category=category,
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
