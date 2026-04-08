from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DocumentListItemResponse(BaseModel):
    id: int
    summary_id: int | None
    title: str
    preview: str
    status: str
    approval_status: str | None = None
    document_type: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    uploader: str | None
    comment_count: int = 0

    delete_requested_at: datetime | None = None
    delete_scheduled_at: datetime | None = None
    deleted_by: int | None = None


class DocumentDetailResponse(BaseModel):
    id: int
    uploader: Optional[str] = None
    summary_id: Optional[int] = None
    title: str | None = None
    status: str
    approval_status: str | None = None
    assignee_user_id: Optional[int] = None
    assignee_username: Optional[str] = None
    feedback: Optional[str] = None
    can_delete: bool = False
    document_type: Optional[str] = None
    category: Optional[str] = None
    summary_text: Optional[str] = None
    key_points: list[str] = []
    metadata: dict = {}
    created_at: datetime
    delete_requested_at: Optional[datetime] = None
    delete_scheduled_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    deleted_by_username: Optional[str] = None

    class Config:
        from_attributes = True


class PendingDocumentListItemResponse(BaseModel):
    id: int
    summary_id: Optional[int] = None
    title: str
    preview: str
    status: str
    approval_status: str
    document_type: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    uploader: Optional[str] = None
    assignee_user_id: Optional[int] = None
    assignee_username: Optional[str] = None
    comment_count: int = 0


class DocumentRejectRequest(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=1000)

    @field_validator("feedback")
    @classmethod
    def strip_feedback(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("반려 사유는 공백만 입력할 수 없습니다.")
        return v


class ReviewedDocumentListItemResponse(BaseModel):
    id: int
    summary_id: Optional[int] = None
    title: str
    preview: str
    status: str
    approval_status: str
    document_type: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    uploader: Optional[str] = None
    assignee_user_id: Optional[int] = None
    assignee_username: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_username: Optional[str] = None
    feedback: Optional[str] = None
    comment_count: int = 0
