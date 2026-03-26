from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentListItemResponse(BaseModel):
    id: int
    summary_id: int | None
    title: str
    preview: str
    status: str
    document_type: Optional[str] = None
    created_at: datetime
    uploader: str | None

    delete_requested_at: datetime | None = None
    delete_scheduled_at: datetime | None = None
    deleted_by: int | None = None


class DocumentDetailResponse(BaseModel):
    id: int
    uploader: Optional[str] = None
    summary_id: Optional[int] = None
    title: str | None = None
    status: str
    document_type: Optional[str] = None
    summary_text: Optional[str] = None
    key_points: list[str] = []
    metadata: dict = {}
    created_at: datetime

    class Config:
        from_attributes = True
