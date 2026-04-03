"""
schemas/knowledge.py

지식원 계약 정의.

━━━ 3-layer 구조 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  platform  (상시)
      플랫폼 공통 법령/판례/유권해석/행정규칙 지식.
      include_platform=True이면 항상 검색 대상.
      source_type: "law", "precedent", "interpretation", "admin_rule"
      현재 두 corpus를 migration flag로 전환 관리:
        - legacy: precedent corpus (bm25:p:* / Qdrant precedent_id 기반)
        - 신규:   platform corpus  (bm25:pl:* / Qdrant platform_document_id 기반)
      NOTE: platform은 판례(precedent) 단독이 아니라 법령·유권해석·행정규칙 등
            플랫폼 전체 공용 지식을 포함한다.

  workspace (조건부)
      그룹/워크스페이스 단위 업로드 문서.
      include_workspace=True이고 group_id가 있을 때만 검색 대상.
      source_type: "workspace_document"

  session   (조건부 / 예외 경로)
      현재 채팅 세션의 첨부 파일.
      include_session=True이고 reference_document_text가 있을 때만 사용.
      NOTE: 현재 구현은 벡터 검색이 아닌 direct context injection 방식이다.
            SessionDocumentRetriever는 platform/workspace와 달리
            search service를 호출하지 않고 텍스트를 직접 wrapping한다.
            향후 session 문서가 벡터 검색 대상이 되면 이 layer는 재설계 대상이다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

현재 서비스 매핑:
    platform  ← PlatformKnowledgeRetriever
                  (retrieve_precedents / vector_store + bm25_store.search_platform)
    workspace ← WorkspaceKnowledgeRetriever
                  (retrieve_group_documents)
    session   ← SessionDocumentRetriever
                  (direct text wrapping — 검색 없음)

결과 매핑 위치:
    platform  → services/knowledge/mappers/platform_item_mapper.py
    workspace → services/knowledge/mappers/workspace_item_mapper.py
    session   → services/knowledge/mappers/session_item_mapper.py
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

    include_platform:  platform layer 사용 여부 (기본 True, 상시 사용)
    include_workspace: workspace layer 사용 여부 (group 선택 시 True)
    include_session:   session layer 사용 여부 (세션 첨부 시 True)

    group_id:   include_workspace=True일 때 필수.
    session_id: include_session=True일 때 source_id 생성에 사용.
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
        "platform"  - 플랫폼 공용 지식 (법령/판례/유권해석/행정규칙)
        "workspace" - 그룹/워크스페이스 문서
        "session"   - 세션 첨부 문서 (direct context injection)

    source_type:
        "law"                - 법령 (platform)
        "precedent"          - 판례 (platform)
        "interpretation"     - 유권해석 (platform)
        "admin_rule"         - 행정규칙 (platform)
        "workspace_document" - 그룹 문서 (workspace)
        "session_document"   - 세션 첨부 문서 (session)

    source_id:
        platform legacy:  precedent_id (int)
        platform corpus:  platform_document_id (str)
        workspace:        document_id (int)
        session:          "session:{session_id}" (str)

    chunk_text:
        answer context로 들어갈 실제 텍스트.

    metadata:
        출처별 부가 정보.
        platform  예: source_url, case_number, court_name, judgment_date,
                      issued_at, agency, chunk_type, section_title
        workspace 예: group_id, file_name, chunk_type
        session   예: session_id, session_title

    score:
        retrieval score.
        session처럼 score 개념이 없는 경우 1.0 고정값 사용.
    """

    knowledge_type: KnowledgeType
    source_type: str
    source_id: str | int
    title: str
    chunk_text: str
    score: float = 1.0
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
