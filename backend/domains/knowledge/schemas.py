"""
domains/knowledge/schemas.py

지식원 계약 정의.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from settings.knowledge import DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K

KnowledgeType = Literal["platform", "workspace", "session"]


@dataclass
class WorkspaceSelection:
    mode: Literal["all", "documents"] = "all"
    document_ids: list[int] = field(default_factory=list)


@dataclass
class KnowledgeRetrievalRequest:
    query: str
    user_id: int | None = None
    group_id: int | None = None
    session_id: int | None = None
    include_platform: bool = True
    include_workspace: bool = False
    include_session: bool = False
    workspace_selection: WorkspaceSelection = field(default_factory=WorkspaceSelection)
    top_k: int = DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K


@dataclass
class RetrievedKnowledgeItem:
    knowledge_type: KnowledgeType
    source_type: str
    source_id: str | int
    title: str
    chunk_text: str
    score: float = 1.0
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
