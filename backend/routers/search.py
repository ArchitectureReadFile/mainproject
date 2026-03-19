from fastapi import APIRouter, Depends

from models.model import User
from routers.auth import get_current_user
from schemas.search import SearchRequest, SearchResponse, SearchResult
from schemas.search_answer import SearchAnswerRequest, SearchAnswerResponse
from services.rag import bm25_store, vector_store
from services.rag.answer_service import RagAnswerService
from services.rag.retrieval_service import retrieve_precedents

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_precedents(
    payload: SearchRequest,
    _: User = Depends(get_current_user),
):
    """
    자연어 질문으로 유사 판례를 검색한다.

    search_mode=dense:
        임베딩 벡터 기반 코사인 유사도 검색.
        의미적으로 유사한 판례를 찾는 데 강함.

    search_mode=hybrid:
        BM25(키워드) + Dense(의미) 결합.
        정확한 법률 용어, 사건번호 검색에 강함.
        score = 0.8 × BM25 + 0.2 × Dense (HYBRID_ALPHA env로 조정 가능)
    """
    hits = retrieve_precedents(
        query=payload.query,
        top_k=payload.top_k,
        search_mode=payload.search_mode,
    )
    results = [SearchResult(**h) for h in hits]

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
    hits = retrieve_precedents(
        query=payload.query,
        top_k=payload.top_k,
        search_mode=payload.search_mode,
    )
    results = [SearchResult(**h) for h in hits]

    answer_payload = RagAnswerService().generate_answer(
        query=payload.query,
        results=[result.model_dump() for result in results],
    )

    return SearchAnswerResponse(
        query=payload.query,
        search_mode=payload.search_mode,
        answer=answer_payload["answer"],
        citations=answer_payload["citations"],
        results=results,
    )


@router.get("/count")
def get_index_count(_: User = Depends(get_current_user)):
    """Qdrant(Dense)와 BM25 인덱스에 저장된 문서 수를 반환한다."""
    return {
        "dense_count": vector_store.count(),
        "bm25_count": bm25_store.count(),
    }
