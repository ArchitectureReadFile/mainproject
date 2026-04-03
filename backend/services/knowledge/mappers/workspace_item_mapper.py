"""
services/knowledge/mappers/workspace_item_mapper.py

Workspace 지식원 raw hit → RetrievedKnowledgeItem 변환.

입력 계약: group_document_retrieval_service.retrieve_group_documents() 반환값의 원소.
"""

from __future__ import annotations

from schemas.knowledge import RetrievedKnowledgeItem


def workspace_grouped_to_item(grouped: dict) -> RetrievedKnowledgeItem:
    """
    group_document_retrieval_service grouped dict → RetrievedKnowledgeItem.
    """
    chunks = grouped.get("chunks") or []
    chunk_text = "\n".join(c.get("text", "") for c in chunks).strip()
    chunk_id = chunks[0].get("chunk_id") if chunks else None
    top_chunk = chunks[0] if chunks else {}

    return RetrievedKnowledgeItem(
        knowledge_type="workspace",
        source_type="workspace_document",
        source_id=grouped.get("document_id", ""),
        title=grouped.get("file_name") or "문서",
        chunk_text=chunk_text,
        score=grouped.get("score", 0.0),
        chunk_id=chunk_id,
        metadata={
            "group_id": grouped.get("group_id"),
            "file_name": grouped.get("file_name"),
            "chunk_type": top_chunk.get("chunk_type"),
        },
    )
