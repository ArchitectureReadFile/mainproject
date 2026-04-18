"""
domains/knowledge/answer_context_builder.py

RetrievedKnowledgeItem 리스트를 LLM prompt 친화적인 context 문자열로 조립한다.
"""

from __future__ import annotations

from domains.knowledge.schemas import RetrievedKnowledgeItem
from settings.knowledge import (
    ANSWER_CONTEXT_PLATFORM_TEXT_MAX,
    ANSWER_CONTEXT_PLATFORM_TOP_K,
    ANSWER_CONTEXT_SESSION_TOP_K,
    ANSWER_CONTEXT_WORKSPACE_TEXT_MAX,
    ANSWER_CONTEXT_WORKSPACE_TOP_K,
)


class AnswerContextBuilder:
    def build(self, items: list[RetrievedKnowledgeItem]) -> str:
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
            if item.chunk_id:
                lines.append(f"- 근거ID: {item.chunk_id}")
            if item.metadata.get("chunk_order") is not None:
                lines.append(f"- 청크순번: {int(item.metadata['chunk_order']) + 1}")
            lines.append(f"- 내용:\n{item.chunk_text}")
            entries.append("\n".join(lines))

        body = "\n\n".join(entries)
        return f"[임시 문서]\n{body}"


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
