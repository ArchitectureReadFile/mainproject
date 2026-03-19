from schemas.search import SearchMode
from services.rag import bm25_store, vector_store
from services.rag.embedding_service import embed_query


def retrieve_precedents(
    query: str,
    top_k: int,
    search_mode: SearchMode,
) -> list[dict]:
    query_vector = embed_query(query)

    if search_mode == SearchMode.dense:
        return vector_store.search(
            query_embedding=query_vector,
            top_k=top_k,
        )

    bm25_hits = bm25_store.search(
        query=query,
        top_k=top_k * 2,
    )
    return vector_store.hybrid_search(
        query_embedding=query_vector,
        bm25_results=bm25_hits,
        top_k=top_k,
    )
