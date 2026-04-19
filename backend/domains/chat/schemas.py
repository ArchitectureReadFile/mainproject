"""
schemas/chat.py
"""

import json
from datetime import datetime
from typing import List

from pydantic import BaseModel, field_validator, model_validator

from models.model import ChatSessionReferenceStatus


class ChatSessionRequest(BaseModel):
    title: str


class ChatSessionGroupResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    title: str
    reference: "ChatSessionReferenceResponse | None" = None
    group: ChatSessionGroupResponse | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionReferenceResponse(BaseModel):
    id: int
    session_id: int
    source_type: str
    title: str
    status: str
    failure_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def normalize_status(cls, data: any) -> any:
        if hasattr(data, "status") and isinstance(
            data.status, ChatSessionReferenceStatus
        ):
            return {
                "id": data.id,
                "session_id": data.session_id,
                "source_type": data.source_type,
                "title": data.title,
                "status": data.status.value,
                "failure_code": data.failure_code,
                "error_message": data.error_message,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        elif isinstance(data, dict) and isinstance(
            data.get("status"), ChatSessionReferenceStatus
        ):
            normalized = dict(data)
            normalized["status"] = normalized["status"].value
            return normalized
        return data

    class Config:
        from_attributes = True


class ChatMessageReferenceResponse(BaseModel):
    knowledge_type: str
    source_type: str
    title: str
    chunk_id: str | None = None
    source_url: str | None = None
    file_name: str | None = None
    case_number: str | None = None
    chunk_order: int | None = None


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    references: list[ChatMessageReferenceResponse] = []
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_references(cls, data: any) -> any:
        if hasattr(data, "metadata_json"):
            references = _parse_references(getattr(data, "metadata_json", None))
            return {
                "id": data.id,
                "session_id": data.session_id,
                "role": data.role,
                "content": data.content,
                "references": references,
                "created_at": data.created_at,
            }
        if isinstance(data, dict) and "references" not in data:
            normalized = dict(data)
            normalized["references"] = _parse_references(data.get("metadata_json"))
            return normalized
        return data

    class Config:
        from_attributes = True


class ChatMessagesResponse(BaseModel):
    messages: List[ChatMessageResponse]
    is_processing: bool


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


def _parse_references(raw_metadata: str | None) -> list[dict]:
    if not raw_metadata:
        return []
    try:
        parsed = json.loads(raw_metadata)
    except (TypeError, ValueError):
        return []
    references = parsed.get("references") if isinstance(parsed, dict) else None
    return references if isinstance(references, list) else []


ChatSessionResponse.model_rebuild()
