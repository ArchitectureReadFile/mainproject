from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DocumentCommentMentionRequest(BaseModel):
    """
    댓글 본문에서 실제 멘션으로 확정된 구간을 전달
    snapshot_username은 저장 시점의 본문 문자열 검증에 사용
    """

    user_id: int
    snapshot_username: str = Field(..., min_length=1, max_length=20)
    start: int = Field(..., ge=0)
    end: int = Field(..., gt=0)

    @field_validator("snapshot_username")
    @classmethod
    def validate_snapshot_username(cls, value: str) -> str:
        """
        멘션 snapshot username 형식을 검증
        """
        if value != value.strip():
            raise ValueError("멘션 username 앞뒤 공백은 허용되지 않습니다.")
        if not value:
            raise ValueError("멘션 username은 비어 있을 수 없습니다.")
        return value

    @model_validator(mode="after")
    def validate_span(self):
        """
        멘션 범위 시작/끝 인덱스를 검증
        """
        if self.start >= self.end:
            raise ValueError("멘션 범위가 올바르지 않습니다.")
        return self


class DocumentCommentCreateRequest(BaseModel):
    """
    문서 댓글/대댓글 생성 요청 스키마
    parent_id가 없으면 루트 댓글, 있으면 대댓글
    """

    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: Optional[int] = None
    page: Optional[int] = Field(None, ge=1)
    x: Optional[float] = Field(None, ge=0.0, le=1.0)
    y: Optional[float] = Field(None, ge=0.0, le=1.0)
    mentions: list[DocumentCommentMentionRequest] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """
        댓글 본문이 공백만으로 구성되는지 검증
        멘션 span 정합성을 위해 원본 문자열은 변경하지 않음
        """
        if not value.strip():
            raise ValueError("댓글 내용은 공백만 입력할 수 없습니다.")
        return value

    @model_validator(mode="after")
    def validate_anchor_fields(self):
        """
        루트 댓글은 위치 좌표를 함께 받아야 하고,
        대댓글은 위치 좌표를 직접 받지 않음
        """
        has_anchor = self.page is not None or self.x is not None or self.y is not None

        if self.parent_id is None:
            if self.page is None or self.x is None or self.y is None:
                raise ValueError("루트 댓글은 page, x, y 좌표가 필요합니다.")
        else:
            if has_anchor:
                raise ValueError("대댓글은 위치 좌표를 직접 받을 수 없습니다.")

        return self


class DocumentCommentAuthorResponse(BaseModel):
    """
    댓글 작성자 표시용 최소 정보
    탈퇴/비활성 등으로 작성자 정보가 없을 수 있어 nullable을 허용
    """

    id: Optional[int] = None
    username: Optional[str] = None


class DocumentCommentMentionResponse(BaseModel):
    """
    댓글 멘션 응답 스키마
    snapshot_username은 원본 content 검증 기준,
    current_username은 화면 렌더링 시 최신 username 표시용
    """

    user_id: Optional[int] = None
    snapshot_username: str
    current_username: Optional[str] = None
    start: int
    end: int

    class Config:
        from_attributes = True


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

    page: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None

    author: Optional[DocumentCommentAuthorResponse] = None
    can_delete: bool = False

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    mentions: list[DocumentCommentMentionResponse] = Field(default_factory=list)
    replies: list["DocumentCommentResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DocumentCommentListResponse(BaseModel):
    """
    문서 상세 패널에 표시할 루트 댓글 목록 응답 스키마
    """

    items: list[DocumentCommentResponse] = Field(default_factory=list)
