from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ExportJobCreateRequest(BaseModel):
    """전체 다운로드 export job 생성 요청"""

    group_id: int


class ExportJobResponse(BaseModel):
    """export job 생성/조회 응답"""

    id: int
    group_id: int
    status: str
    export_file_name: Optional[str] = None
    error_message: Optional[str] = None
    total_file_count: int = 0
    exported_file_count: int = 0
    missing_file_count: int = 0
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reused: bool = False
