from schemas.search import SearchMode
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_query
from services.rag.grouping_service import group_chunks_by_precedent


def retrieve_precedents(
    query: str,
    top_k: int,
    search_mode: SearchMode,
) -> list[dict]:
    """
    검색 → chunk hit → precedent 단위 그룹핑 후 반환.
    반환값은 grouping_service.group_chunks_by_precedent() 계약을 따른다.
    """
    query_vector = embed_query(query)
    fetch_k = top_k * 4  # chunk 단위라 더 많이 가져온 뒤 그룹핑

    if search_mode == SearchMode.dense:
        chunk_hits = vector_store.search(
            query_embedding=query_vector,
            top_k=fetch_k,
        )
    else:
        bm25_hits = bm25_store.search(
            query=query,
            top_k=fetch_k * 2,
        )
        chunk_hits = vector_store.hybrid_search(
            query_embedding=query_vector,
            bm25_results=bm25_hits,
            top_k=fetch_k,
        )

    grouped = group_chunks_by_precedent(chunk_hits)
    return grouped[:top_k]
