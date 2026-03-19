from pydantic import BaseModel, Field

from schemas.search import SearchMode, SearchResult


class SearchAnswerRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=10)
    search_mode: SearchMode = SearchMode.hybrid


class CitationItem(BaseModel):
    precedent_id: int
    title: str | None
    source_url: str | None
    score: float


class SearchAnswerResponse(BaseModel):
    query: str
    search_mode: str
    answer: str
    citations: list[CitationItem]
    results: list[SearchResult]
