from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DocumentCommentCreateRequest(BaseModel):
    """
    문서 댓글/대댓글 생성 요청 스키마
    parent_id가 없으면 루트 댓글, 있으면 대댓글
    """

    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: Optional[int] = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        """
        댓글 본문 앞뒤 공백을 제거, 공백만 입력된 경우를 방지
        """
        value = value.strip()
        if not value:
            raise ValueError("댓글 내용은 공백만 입력할 수 없습니다.")
        return value


class DocumentCommentAuthorResponse(BaseModel):
    """
    댓글 작성자 표시용 최소 정보
    탈퇴/비활성 등으로 작성자 정보가 없을 수 있어 nullable을 허용
    """

    id: Optional[int] = None
    username: Optional[str] = None


class DocumentCommentResponse(BaseModel):
    """
    문서 댓글 응답 스키마
    replies 필드로 대댓글 트리를 함께 내려줌
    """

    id: int
    document_id: int
    parent_id: Optional[int] = None

    content: str
    is_deleted: bool = False

    author: Optional[DocumentCommentAuthorResponse] = None
    can_delete: bool = False

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    replies: list[DocumentCommentResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DocumentCommentListResponse(BaseModel):
    """
    문서 상세 패널에 표시할 루트 댓글 목록 응답 스키마
    """

    items: list[DocumentCommentResponse] = Field(default_factory=list)
