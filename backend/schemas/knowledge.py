"""
schemas/knowledge.py

지식원 계약 정의.

세 지식원:
    platform  - 플랫폼 기본 지식 (판례 RAG). 항상 사용.
    workspace - 사용자가 선택한 워크스페이스/그룹 문서. 선택형.
    session   - 챗봇 임시 업로드 문서. 있을 때만 추가 사용.

공통 retrieval 결과 스키마:
    RetrievedKnowledgeItem — 지식원 종류에 무관하게 통일된 결과 단위.

현재 서비스 매핑:
    platform  ← retrieve_precedents() / retrieval_service.py
    workspace ← retrieve_group_documents() / group_document_retrieval_service.py
    session   ← ChatSession.reference_document_text (직접 주입 → 이후 교체 대상)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from settings.knowledge import DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K

# ── 지식원 종류 ───────────────────────────────────────────────────────────────

KnowledgeType = Literal["platform", "workspace", "session"]

# ── workspace selection 계약 ──────────────────────────────────────────────────


@dataclass
class WorkspaceSelection:
    """
    워크스페이스 검색 범위 선택 계약.

    mode:
        "all"       - workspace/group 전체 범위 검색
        "documents" - 사용자가 선택한 document_ids 범위만 검색

    향후 확장 가능:
        - folders, categories, tags
    """

    mode: Literal["all", "documents"] = "all"
    document_ids: list[int] = field(default_factory=list)


# ── retrieval 요청 계약 ───────────────────────────────────────────────────────


@dataclass
class KnowledgeRetrievalRequest:
    """
    KnowledgeRetrievalService 입력 계약.

    include_platform:  판례 RAG 사용 여부 (기본 True)
    include_workspace: 그룹 문서 RAG 사용 여부 (그룹 선택 시 True)
    include_session:   세션 임시 문서 사용 여부 (문서 첨부 시 True)
    """

    query: str
    user_id: int | None = None
    group_id: int | None = None
    session_id: int | None = None
    include_platform: bool = True
    include_workspace: bool = False
    include_session: bool = False
    workspace_selection: WorkspaceSelection = field(default_factory=WorkspaceSelection)
    top_k: int = DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K


# ── 공통 retrieval 결과 스키마 ────────────────────────────────────────────────


@dataclass
class RetrievedKnowledgeItem:
    """
    지식원 종류에 무관한 공통 retrieval 결과 단위.

    knowledge_type:
        "platform"  - 판례
        "workspace" - 그룹 문서
        "session"   - 세션 임시 문서

    source_type:
        "precedent"          - 판례
        "workspace_document" - 그룹 문서
        "session_document"   - 세션 임시 문서

    source_id:
        판례:    precedent_id (int)
        문서:    document_id (int)
        세션:    session_id 기반 식별자 (str)

    chunk_text:
        answer context로 들어갈 실제 텍스트

    metadata:
        출처별 부가 정보.
        platform  예: source_url, case_number, court_name, judgment_date
        workspace 예: group_id, file_name, chunk_type, page_number, table_id
        session   예: session_title, file_name

    score:
        retrieval score.
        session처럼 score 개념이 약한 경우 1.0 기본값 허용.
    """

    knowledge_type: KnowledgeType
    source_type: str
    source_id: str | int
    title: str
    chunk_text: str
    score: float = 1.0
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
