# schemas/document_schema.py
"""
추출 후 공통 소비 계약. ExtractedDocument(raw)를 정규화한 결과.

raw 영역      : 추출기 원본 그대로 보존 (소비처가 직접 읽지 않음)
normalized    : 소비처(summary / rag / chat)가 실제로 쓰는 정규화 결과
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentTableBlock:
    """
    표 1개 단위.

    table_id   : chunk_id / citation 추적 기준 ("table:0", "table:1")
    text       : 소비처가 직접 쓰는 직렬화된 표 텍스트 ("[표 1]\\ncol1 | col2")
    page_number: OCR 경로일 때 채워질 수 있음. ODL 경로는 None
    row_count  : 선택. retrieval 필터링 등에 활용 가능
    metadata   : 이후 확장 허용 (confidence, bbox summary 등)
    """

    table_id: str
    text: str
    page_number: int | None = None
    row_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentPage:
    """
    페이지 단위 정보.

    ODL 경로에서는 pages=[]로 두면 됨 (강제하지 않음).
    OCR 경로에서 page_number / text / table_ids 를 채운다.

    page_number: 1-indexed
    text       : 해당 페이지의 텍스트 (bbox/line 단위 상세 미포함)
    table_ids  : 이 페이지에 속하는 DocumentTableBlock.table_id 목록
    metadata   : 이후 확장 허용
    """

    page_number: int
    text: str
    table_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentSchema:
    """
    추출 후 공통 소비 계약.

    ┌──────────────────────────────────────────────┐
    │ raw 영역    : 추출기 원본 보존 (소비처 직접 X) │
    │ normalized  : 소비처가 실제로 쓰는 정규화 필드 │
    └──────────────────────────────────────────────┘

    source_type:
        "odl" - opendataloader-pdf 경로 (raw_markdown + raw_json 있음)
        "ocr" - OCR fallback 경로 (raw_text만 있음)

    분류(document_type / category)는 DocumentClassificationService가
    DocumentSchema와 별개로 Document 모델에 직접 저장한다.
    """

    # ── 출처 구분 ─────────────────────────────────────────────────────────────
    source_type: str  # "odl" | "ocr"

    # ── raw 영역 (추출기 원본, NormalizeService 내부에서만 읽음) ──────────────
    raw_markdown: str | None = None  # ODL 경로: .md 원본
    raw_json: dict | list | None = None  # ODL 경로: .json 원본
    raw_text: str | None = None  # OCR 경로: plain text 원본

    # ── normalized 영역 (소비처가 실제로 쓰는 필드) ───────────────────────────
    body_text: str = ""
    table_blocks: list[DocumentTableBlock] = field(default_factory=list)
    pages: list[DocumentPage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
