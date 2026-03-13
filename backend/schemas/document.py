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
        orm_mode = True


class DocumentDetailResponse(BaseModel):
    id: int
    uploader: Optional[str] = None
    summary_id: Optional[int] = None
    status: str
    case_number: Optional[str] = None
    case_name: Optional[str] = None
    court_name: Optional[str] = None
    judgment_date: Optional[date] = None
    summary_title: Optional[str] = None
    summary_main: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    facts: Optional[str] = None
    judgment_order: Optional[str] = None
    judgment_reason: Optional[str] = None
    related_laws: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
