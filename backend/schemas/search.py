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
    """
    검색 결과 카드 단위 스키마. grouping_service 반환값 기준.

    메타 필드 출처:
        chunk_builder.PrecedentChunk payload
        → vector_store._RETRIEVAL_PAYLOAD_FIELDS
        → grouping_service._PRECEDENT_META_FIELDS
        → 여기까지 일관되게 전달됨.

    text:          top chunk 본문 미리보기
    section_title: top chunk의 섹션 (meta / 주문 / 이유 등)
    element_type:  top chunk의 타입 (meta / section / paragraph)
    """

    precedent_id: int
    score: float
    title: str | None = None
    case_number: str | None = None
    case_name: str | None = None
    court_name: str | None = None
    judgment_date: str | None = None
    source_url: str | None = None
    text: str | None = None
    section_title: str | None = None
    element_type: str | None = None
    dense_score: float | None = None
    bm25_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    results: list[SearchResult]
