"""
schemas/chat.py
"""

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


class ChatSessionRequest(BaseModel):
    title: str


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    title: str
    reference_document_title: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatWorkspaceSelectionInput(BaseModel):
    """
    send_message API의 workspace_selection_json 파싱 결과.

    validation 정책:
        - mode="all":                          valid (include_workspace=True)
        - mode="documents" + non-empty ids:    valid (include_workspace=True)
        - mode="documents" + empty ids:        422 validation error (fail-closed)
        - 미전송 / null:                        selection 없음 (include_workspace=False)
    """

    mode: str
    document_ids: list[int] = []

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        if v not in ("all", "documents"):
            raise ValueError(
                f"mode는 'all' 또는 'documents' 여야 합니다. 받은 값: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def documents_mode_requires_ids(self) -> "ChatWorkspaceSelectionInput":
        if self.mode == "documents" and not self.document_ids:
            raise ValueError(
                "mode='documents'일 때 document_ids는 비어 있으면 안 됩니다. "
                "전체 검색은 mode='all'을 사용하세요."
            )
        return self
