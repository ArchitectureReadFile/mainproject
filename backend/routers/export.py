from urllib.parse import quote

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from repositories.export_repository import ExportRepository
from routers.auth import get_current_user
from routers.group import get_group_service
from schemas.export import ExportJobCreateRequest, ExportJobResponse
from services.export_service import ExportService
from services.group_service import GroupService

router = APIRouter(prefix="/exports", tags=["exports"])


def get_export_service(
    db: Session = Depends(get_db),
    group_service: GroupService = Depends(get_group_service),
) -> ExportService:
    return ExportService(
        repository=ExportRepository(db),
        group_service=group_service,
    )


@router.post("", response_model=ExportJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_export_job(
    payload: ExportJobCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
):
    """전체 다운로드 export job을 생성"""
    return service.create_job(
        user_id=current_user.id,
        group_id=payload.group_id,
    )


@router.get("/{job_id}", response_model=ExportJobResponse)
def get_export_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
):
    """export job 상태를 조회"""
    return service.get_job(
        job_id=job_id,
        user_id=current_user.id,
    )


@router.post("/{job_id}/cancel", response_model=ExportJobResponse)
def cancel_export_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
):
    """진행 중 export job을 취소"""
    return service.cancel_job(
        job_id=job_id,
        user_id=current_user.id,
    )


@router.get("/{job_id}/download")
def download_export_file(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
):
    """READY 상태 export ZIP 파일을 다운로드"""
    file_path, export_file_name = service.get_download_file(
        job_id=job_id,
        user_id=current_user.id,
    )

    encoded_file_name = quote(export_file_name)

    return FileResponse(
        path=file_path,
        media_type="application/zip",
        headers={
            "Content-Disposition": (f"attachment; filename*=UTF-8''{encoded_file_name}")
        },
    )
