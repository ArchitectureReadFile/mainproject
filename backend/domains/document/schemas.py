from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ALLOWED_DOCUMENT_TYPES = (
    "계약서",
    "신청서",
    "준비서면",
    "의견서",
    "내용증명",
    "소장",
    "고소장",
    "기타",
    "미분류",
)

ALLOWED_DOCUMENT_CATEGORIES = (
    "민사",
    "계약",
    "회사",
    "행정",
    "형사",
    "노동",
    "기타",
    "미분류",
)


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

    original_filename: Optional[str] = None
    original_content_type: Optional[str] = None

    preview_status: Optional[str] = None
    preview_available: bool = False

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


class DocumentClassificationUpdateRequest(BaseModel):
    """
    문서 분류 수정 요청 본문
    문서 유형과 카테고리는 모두 필수이며 허용된 값만 받을 수 있다.
    """

    document_type: str = Field(..., min_length=1, max_length=50)
    category: str = Field(..., min_length=1, max_length=50)

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, value: str) -> str:
        """
        문서 유형 입력값을 정리하고 허용 목록 여부를 검증한다.
        """
        normalized = value.strip()
        if normalized not in ALLOWED_DOCUMENT_TYPES:
            raise ValueError("허용되지 않은 문서 유형입니다.")
        return normalized

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        """
        카테고리 입력값을 정리하고 허용 목록 여부를 검증한다.
        """
        normalized = value.strip()
        if normalized not in ALLOWED_DOCUMENT_CATEGORIES:
            raise ValueError("허용되지 않은 카테고리입니다.")
        return normalized


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
