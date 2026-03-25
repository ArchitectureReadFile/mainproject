from pydantic import BaseModel, Field

from schemas.search import SearchMode, SearchResult


class SearchAnswerRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=10)
    search_mode: SearchMode = SearchMode.hybrid


class CitationItem(BaseModel):
    """
    LLM이 근거로 선택한 판례 citation 스키마.

    answer_service._build_citations() / _fallback_citations() 반환값과 계약 일치.
    precedent_id는 프론트에서 링크/식별용으로 사용하되 답변 본문에 노출하지 않는다.
    """

    precedent_id: int
    title: str | None = None
    case_number: str | None = None
    case_name: str | None = None
    court_name: str | None = None
    source_url: str | None = None
    score: float


class SearchAnswerResponse(BaseModel):
    query: str
    search_mode: str
    answer: str
    citations: list[CitationItem]
    results: list[SearchResult]
