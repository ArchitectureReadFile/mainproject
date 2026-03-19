from enum import Enum

from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    dense = "dense"
    hybrid = "hybrid"


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=10)
    search_mode: SearchMode = SearchMode.dense


class SearchResult(BaseModel):
    precedent_id: int
    score: float
    title: str | None
    source_url: str | None
    text: str | None
    dense_score: float | None = None
    bm25_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    results: list[SearchResult]
