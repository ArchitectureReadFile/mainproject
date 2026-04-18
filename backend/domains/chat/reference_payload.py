"""
domains/chat/reference_payload.py

assistant message에 저장할 근거(reference) payload 직렬화.
"""

from __future__ import annotations

from domains.knowledge.schemas import RetrievedKnowledgeItem

MAX_CHAT_REFERENCE_ITEMS = 4


def build_chat_reference_payloads(
    items: list[RetrievedKnowledgeItem],
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    seen: set[tuple[str, str | int, str | None]] = set()

    for item in items:
        key = (item.knowledge_type, item.source_id, item.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        payloads.append(
            {
                "knowledge_type": item.knowledge_type,
                "source_type": item.source_type,
                "title": item.title,
                "chunk_id": item.chunk_id,
                "source_url": item.metadata.get("source_url"),
                "file_name": item.metadata.get("file_name"),
                "case_number": item.metadata.get("case_number"),
                "chunk_order": item.metadata.get("chunk_order"),
            }
        )
        if len(payloads) >= MAX_CHAT_REFERENCE_ITEMS:
            break

    return payloads
