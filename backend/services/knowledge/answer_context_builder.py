"""
services/knowledge/answer_context_builder.py

RetrievedKnowledgeItem 리스트를 LLM prompt 친화적인 context 문자열로 조립한다.

책임:
    - knowledge_type 기준으로 결과를 분류
    - source별 블록 생성 ([플랫폼 지식] / [워크스페이스 문서] / [임시 문서])
    - source별 item 개수 제한 및 chunk_text 길이 제한
    - 빈 블록 생략

비책임:
    - retrieval 검색
    - score 재조정 / rerank
    - ChatProcessor 로직

출력 블록 순서 (고정):
    1. [플랫폼 지식]
    2. [워크스페이스 문서]
    3. [임시 문서]

길이 제한 정책 (v1):
    - platform/workspace: item당 chunk_text 최대 1500자
    - session:            item당 chunk_text 최대 3000자
    - platform: 상위 3개, workspace: 상위 3개, session: 상위 1개
"""

from __future__ import annotations

from schemas.knowledge import RetrievedKnowledgeItem
from settings.knowledge import (
    ANSWER_CONTEXT_PLATFORM_TEXT_MAX,
    ANSWER_CONTEXT_PLATFORM_TOP_K,
    ANSWER_CONTEXT_SESSION_TEXT_MAX,
    ANSWER_CONTEXT_SESSION_TOP_K,
    ANSWER_CONTEXT_WORKSPACE_TEXT_MAX,
    ANSWER_CONTEXT_WORKSPACE_TOP_K,
)


class AnswerContextBuilder:
    def build(self, items: list[RetrievedKnowledgeItem]) -> str:
        """
        RetrievedKnowledgeItem 리스트를 source별 블록으로 조립해 반환한다.
        빈 블록은 생략한다.
        """
        grouped = _group_by_knowledge_type(items)

        blocks: list[str] = []

        platform_block = self._build_platform_block(grouped.get("platform", []))
        if platform_block:
            blocks.append(platform_block)

        workspace_block = self._build_workspace_block(grouped.get("workspace", []))
        if workspace_block:
            blocks.append(workspace_block)

        session_block = self._build_session_block(grouped.get("session", []))
        if session_block:
            blocks.append(session_block)

        return "\n\n".join(blocks)

    # ── 블록 생성 ─────────────────────────────────────────────────────────────

    def _build_platform_block(self, items: list[RetrievedKnowledgeItem]) -> str:
        if not items:
            return ""

        entries: list[str] = []
        for item in items[:ANSWER_CONTEXT_PLATFORM_TOP_K]:
            lines = [f"- 제목: {item.title}"]
            if item.metadata.get("source_url"):
                lines.append(f"- 출처: {item.metadata['source_url']}")
            if item.metadata.get("case_number"):
                lines.append(f"- 사건번호: {item.metadata['case_number']}")
            text = _trim_text(item.chunk_text, ANSWER_CONTEXT_PLATFORM_TEXT_MAX)
            lines.append(f"- 내용:\n{text}")
            entries.append("\n".join(lines))

        body = "\n\n".join(entries)
        return f"[플랫폼 지식]\n{body}"

    def _build_workspace_block(self, items: list[RetrievedKnowledgeItem]) -> str:
        if not items:
            return ""

        entries: list[str] = []
        for item in items[:ANSWER_CONTEXT_WORKSPACE_TOP_K]:
            lines = [f"- 문서: {item.metadata.get('file_name') or item.title}"]
            if item.metadata.get("chunk_type"):
                lines.append(f"- 유형: {item.metadata['chunk_type']}")
            text = _trim_text(item.chunk_text, ANSWER_CONTEXT_WORKSPACE_TEXT_MAX)
            lines.append(f"- 내용:\n{text}")
            entries.append("\n".join(lines))

        body = "\n\n".join(entries)
        return f"[워크스페이스 문서]\n{body}"

    def _build_session_block(self, items: list[RetrievedKnowledgeItem]) -> str:
        if not items:
            return ""

        entries: list[str] = []
        for item in items[:ANSWER_CONTEXT_SESSION_TOP_K]:
            title = item.metadata.get("session_title") or item.title
            lines = [f"- 제목: {title}"]
            text = _trim_text(item.chunk_text, ANSWER_CONTEXT_SESSION_TEXT_MAX)
            lines.append(f"- 내용:\n{text}")
            entries.append("\n".join(lines))

        body = "\n\n".join(entries)
        return f"[임시 문서]\n{body}"


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────


def _group_by_knowledge_type(
    items: list[RetrievedKnowledgeItem],
) -> dict[str, list[RetrievedKnowledgeItem]]:
    grouped: dict[str, list[RetrievedKnowledgeItem]] = {
        "platform": [],
        "workspace": [],
        "session": [],
    }
    for item in items:
        grouped.setdefault(item.knowledge_type, []).append(item)
    return grouped


def _trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"
