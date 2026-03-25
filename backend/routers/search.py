from fastapi import APIRouter, Depends

from models.model import User
from routers.auth import get_current_user
from schemas.search import SearchRequest, SearchResponse, SearchResult
from schemas.search_answer import SearchAnswerRequest, SearchAnswerResponse
from services.rag import bm25_store, vector_store
from services.rag.answer_service import RagAnswerService
from services.rag.retrieval_service import retrieve_precedents

router = APIRouter(prefix="/search", tags=["search"])


def _grouped_to_search_result(item: dict) -> SearchResult:
    """
    grouping_service 결과(precedent-level dict) → SearchResult 스키마 변환.

    text / section_title / element_type: top chunk 기준.
    메타 필드(case_number 등)는 precedent-level에서 직접 읽는다.
    """
    top_chunk = item.get("chunks", [{}])[0] if item.get("chunks") else {}
    return SearchResult(
        precedent_id=item["precedent_id"],
        score=item["score"],
        title=item.get("title"),
        case_number=item.get("case_number"),
        case_name=item.get("case_name"),
        court_name=item.get("court_name"),
        judgment_date=item.get("judgment_date"),
        source_url=item.get("source_url"),
        text=top_chunk.get("text"),
        section_title=top_chunk.get("section_title"),
        element_type=top_chunk.get("element_type"),
        dense_score=None,
        bm25_score=None,
    )


@router.post("", response_model=SearchResponse)
def search_precedents(
    payload: SearchRequest,
    _: User = Depends(get_current_user),
):
    grouped = retrieve_precedents(
        query=payload.query,
        top_k=payload.top_k,
        search_mode=payload.search_mode,
    )
    results = [_grouped_to_search_result(item) for item in grouped]
    return SearchResponse(
        query=payload.query,
        search_mode=payload.search_mode,
        results=results,
    )

@router.post("/answer", response_model=SearchAnswerResponse)
def answer_precedent_search(
    payload: SearchAnswerRequest,
    _: User = Depends(get_current_user),
):
    grouped = retrieve_precedents(
        query=payload.query,
        top_k=payload.top_k,
        search_mode=payload.search_mode,
    )

    answer_payload = RagAnswerService().generate_answer(
        query=payload.query,
        results=grouped,
    )

    results = [_grouped_to_search_result(item) for item in grouped]
    return SearchAnswerResponse(
        query=payload.query,
        search_mode=payload.search_mode,
        answer=answer_payload["answer"],
        citations=answer_payload["citations"],
        results=results,
    )

@router.get("/count")
def get_index_count(_: User = Depends(get_current_user)):
    return {
        "dense_count": vector_store.count(),
        "bm25_count": bm25_store.count(),
    }
