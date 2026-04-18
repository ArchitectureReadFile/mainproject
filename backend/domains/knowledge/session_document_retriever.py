from domains.knowledge.mappers.session_item_mapper import session_text_to_item
from domains.knowledge.schemas import KnowledgeRetrievalRequest, RetrievedKnowledgeItem
from domains.knowledge.session_chunking import (
    SessionTextChunk,
    rank_session_chunks,
    split_session_text,
)
from settings.knowledge import SESSION_RETRIEVAL_TOP_K


class SessionDocumentRetriever:
    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        stored_chunks: list[object] | None = None,
        session_reference_text: str,
        session_title: str | None = None,
    ) -> list[RetrievedKnowledgeItem]:
        if not request.include_session or (
            not stored_chunks and not session_reference_text.strip()
        ):
            return []

        chunks = (
            _load_stored_chunks(stored_chunks)
            if stored_chunks
            else split_session_text(session_reference_text)
        )
        ranked_chunks = rank_session_chunks(request.query, chunks)[
            :SESSION_RETRIEVAL_TOP_K
        ]

        return [
            session_text_to_item(
                session_id=request.session_id,
                chunk_text=chunk.chunk_text,
                session_title=session_title,
                chunk_id=(
                    f"session:{request.session_id}:chunk:{chunk.chunk_id}"
                    if chunk.chunk_id is not None
                    else f"session:{request.session_id}:chunk:{chunk.chunk_order}"
                ),
                chunk_order=chunk.chunk_order,
                score=score,
            )
            for chunk, score in ranked_chunks
        ]

    def retrieve_from_text(
        self,
        request: KnowledgeRetrievalRequest,
        *,
        session_reference_text: str,
        session_title: str | None = None,
    ) -> list[RetrievedKnowledgeItem]:
        return self.retrieve(
            request,
            stored_chunks=None,
            session_reference_text=session_reference_text,
            session_title=session_title,
        )


def _load_stored_chunks(stored_chunks: list[object]) -> list[SessionTextChunk]:
    normalized: list[SessionTextChunk] = []
    for chunk in stored_chunks:
        chunk_text = getattr(chunk, "chunk_text", None)
        chunk_order = getattr(chunk, "chunk_order", None)
        if not isinstance(chunk_text, str) or chunk_order is None:
            continue
        normalized.append(
            SessionTextChunk(
                chunk_order=int(chunk_order),
                chunk_text=chunk_text,
                chunk_id=getattr(chunk, "id", None),
            )
        )
    return normalized
