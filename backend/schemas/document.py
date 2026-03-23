from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DocumentListItemResponse(BaseModel):
    id: int
    summary_id: Optional[int] = None
    title: str
    preview: str
    status: str
    created_at: datetime
    court_name: Optional[str] = None
    judgment_date: Optional[date] = None
    uploader: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentDetailResponse(BaseModel):
    id: int
    uploader: Optional[str] = None
    summary_id: Optional[int] = None
    status: str
    document_type: Optional[str] = None
    summary_text: Optional[str] = None
    key_points: list[str] = []
    metadata: dict = {}
    case_number: Optional[str] = None
    case_name: Optional[str] = None
    court_name: Optional[str] = None
    judgment_date: Optional[date] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
