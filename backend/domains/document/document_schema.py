# schemas/document_schema.py
"""
추출 후 공통 소비 계약. ExtractedDocument(raw)를 정규화한 결과.

raw 영역      : 추출기 원본 그대로 보존 (소비처가 직접 읽지 않음)
normalized    : 소비처(summary / rag / chat)가 실제로 쓰는 정규화 결과
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

_SCHEMA_VERSION = "v1"


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
class DocumentSection:
    """
    ODL raw_json 기반으로 추출한 구조 단위.

    heading     : 섹션 제목 (없으면 None)
    paragraphs  : 이 섹션에 속하는 문단 텍스트 리스트
    table_ids   : 이 섹션에 속하는 DocumentTableBlock.table_id 리스트
    page_start  : 시작 페이지 번호 (1-indexed, 알 수 없으면 None)
    page_end    : 끝 페이지 번호 (알 수 없으면 None)

    raw_json이 없거나 구조 파싱에 실패하면 sections=[] 로 두고
    chunker가 body_text fallback으로 내려간다.
    """

    heading: str | None
    paragraphs: list[str] = field(default_factory=list)
    table_ids: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class DocumentSchema:
    """
    추출 후 공통 소비 계약.

    ┌──────────────────────────────────────────────┐
    │ raw 영역    : 추출기 원본 보존 (소비처 직접 X) │
    │ normalized  : 소비처가 실제로 쓰는 정규화 필드 │
    └──────────────────────────────────────────────┘

    source_type:
        "odl" - 현재 기본 추출 경로 (opendataloader-pdf hybrid OCR 포함)
        "ocr" - 레거시/호환용 값. 신규 추출에서는 더 이상 기본 사용하지 않음

    sections:
        ODL raw_json 기반 구조 정보. chunker가 section-aware chunking에 사용.
        raw_json이 없거나 구조 파싱 실패 시 빈 리스트 → body_text fallback.

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
    sections: list[DocumentSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def schema_version(self) -> str:
        value = self.metadata.get("schema_version")
        if value is None:
            return _SCHEMA_VERSION
        return str(value)

    @property
    def normalization_version(self) -> str | None:
        value = self.metadata.get("normalization_version")
        if value is None:
            return None
        return str(value)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        data["normalization_version"] = self.normalization_version
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentSchema:
        table_blocks = [
            DocumentTableBlock(**item) for item in data.get("table_blocks", [])
        ]
        pages = [DocumentPage(**item) for item in data.get("pages", [])]
        sections = [DocumentSection(**item) for item in data.get("sections", [])]
        metadata = dict(data.get("metadata") or {})
        schema_version = data.get("schema_version")
        if schema_version is not None:
            metadata["schema_version"] = str(schema_version)
        elif "schema_version" not in metadata:
            metadata["schema_version"] = _SCHEMA_VERSION
        if data.get("normalization_version") is not None:
            metadata["normalization_version"] = str(data["normalization_version"])

        return cls(
            source_type=str(data.get("source_type", "")),
            raw_markdown=data.get("raw_markdown"),
            raw_json=data.get("raw_json"),
            raw_text=data.get("raw_text"),
            body_text=str(data.get("body_text", "")),
            table_blocks=table_blocks,
            pages=pages,
            sections=sections,
            metadata=dict(metadata),
        )
