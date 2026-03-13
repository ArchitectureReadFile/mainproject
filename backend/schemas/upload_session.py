from typing import List, Optional

from pydantic import BaseModel


class UploadSessionCreateRequest(BaseModel):
    file_names: List[str]


class UploadSessionItemResponse(BaseModel):
    file_name: str
    status: str
    doc_id: Optional[int] = None
    summary: Optional[dict] = None
    error: Optional[str] = None
    updated_at: str


class UploadSessionResponse(BaseModel):
    items: List[UploadSessionItemResponse]
    is_running: bool
    started_at: Optional[str] = None
    abandoned_at: Optional[str] = None
