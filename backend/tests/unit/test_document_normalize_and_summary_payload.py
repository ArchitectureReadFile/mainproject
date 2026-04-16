"""
tests/unit/test_document_normalize_and_summary_payload.py

DocumentNormalizeService + DocumentSummaryPayloadService 단위 테스트.
"""

import pytest

from domains.document.document_schema import (
    DocumentSchema,
    DocumentTableBlock,
)
from domains.document.extract_service import ExtractedDocument
from domains.document.normalize_service import DocumentNormalizeService
from domains.document.summary_payload import (
    DocumentSummaryPayloadService,
)

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def normalizer():
    return DocumentNormalizeService()


@pytest.fixture
def payload_service():
    return DocumentSummaryPayloadService()


def _odl(markdown: str = "", json_data=None) -> ExtractedDocument:
    return ExtractedDocument(
        markdown=markdown,
        json_data=json_data or {},
        source_type="odl",
    )


def _ocr(text: str) -> ExtractedDocument:
    return ExtractedDocument(markdown=text, json_data=None, source_type="ocr")


_SIMPLE_JSON = {
    "kids": [
        {"type": "paragraph", "content": "본문 내용입니다."},
        {
            "type": "table",
            "rows": [
                {
                    "type": "table row",
                    "cells": [
                        {
                            "type": "table cell",
                            "kids": [{"type": "paragraph", "content": "col1"}],
                        },
                        {
                            "type": "table cell",
                            "kids": [{"type": "paragraph", "content": "col2"}],
                        },
                    ],
                }
            ],
        },
    ]
}


# ── DocumentNormalizeService ──────────────────────────────────────────────────


class TestSourceTypeDetection:
    def test_odl_uses_extracted_source_type(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="본문", json_data={}))
        assert doc.source_type == "odl"

    def test_ocr_uses_extracted_source_type(self, normalizer):
        doc = normalizer.normalize(_ocr("OCR 본문"))
        assert doc.source_type == "ocr"

    def test_odl_markdown_only_does_not_fall_back_to_ocr(self, normalizer):
        extracted = ExtractedDocument(
            markdown="# 제목\n\n본문",
            json_data=None,
            source_type="odl",
        )
        doc = normalizer.normalize(extracted)
        assert doc.source_type == "odl"
        assert doc.raw_markdown == "# 제목\n\n본문"
        assert doc.raw_text is None


class TestRawFields:
    def test_odl_sets_raw_markdown_and_json(self, normalizer):
        extracted = _odl(markdown="# 제목", json_data={"kids": []})
        doc = normalizer.normalize(extracted)
        assert doc.raw_markdown == "# 제목"
        assert doc.raw_json == {"kids": []}
        assert doc.raw_text is None

    def test_ocr_sets_raw_text_only(self, normalizer):
        doc = normalizer.normalize(_ocr("OCR 원문"))
        assert doc.raw_text == "OCR 원문"
        assert doc.raw_markdown is None
        assert doc.raw_json is None


class TestBodyText:
    def test_odl_uses_markdown_body(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="# 제목\n\n본문", json_data={}))
        assert doc.body_text == "# 제목\n\n본문"

    def test_odl_falls_back_to_json_when_markdown_empty(self, normalizer):
        json_data = {"kids": [{"type": "paragraph", "content": "JSON 본문"}]}
        doc = normalizer.normalize(_odl(markdown="", json_data=json_data))
        assert "JSON 본문" in doc.body_text

    def test_ocr_uses_raw_text_as_body(self, normalizer):
        doc = normalizer.normalize(_ocr("OCR로 추출된 텍스트"))
        assert doc.body_text == "OCR로 추출된 텍스트"


class TestTableBlocks:
    def test_odl_extracts_table_blocks(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="본문", json_data=_SIMPLE_JSON))
        assert len(doc.table_blocks) == 1
        assert doc.table_blocks[0].table_id == "table:0"
        assert "col1" in doc.table_blocks[0].text
        assert "col2" in doc.table_blocks[0].text

    def test_ocr_has_no_table_blocks(self, normalizer):
        doc = normalizer.normalize(_ocr("OCR 본문"))
        assert doc.table_blocks == []

    def test_odl_no_tables_in_json(self, normalizer):
        json_data = {"kids": [{"type": "paragraph", "content": "본문만"}]}
        doc = normalizer.normalize(_odl(markdown="본문", json_data=json_data))
        assert doc.table_blocks == []


class TestPages:
    def test_page_created_when_body_exists(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="본문", json_data={}))
        assert len(doc.pages) == 1
        assert doc.pages[0].page_number == 1
        assert doc.pages[0].metadata.get("estimated") is True

    def test_page_table_ids_match_table_blocks(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="본문", json_data=_SIMPLE_JSON))
        assert doc.pages[0].table_ids == ["table:0"]

    def test_empty_document_has_no_pages(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="", json_data={}))
        assert doc.pages == []

    def test_real_pages_restored_from_odl_json(self, normalizer):
        json_data = {
            "type": "document",
            "kids": [
                {
                    "type": "page",
                    "page_no": 1,
                    "kids": [
                        {"type": "paragraph", "content": "1페이지 본문"},
                    ],
                },
                {
                    "type": "page",
                    "page_no": 2,
                    "kids": [
                        {"type": "paragraph", "content": "2페이지 본문"},
                    ],
                },
            ],
        }
        doc = normalizer.normalize(_odl(markdown="", json_data=json_data))
        assert [p.page_number for p in doc.pages] == [1, 2]
        assert doc.pages[0].text == "1페이지 본문"
        assert doc.pages[1].text == "2페이지 본문"
        assert doc.pages[0].metadata.get("estimated") is False
        assert doc.pages[1].metadata.get("estimated") is False

    def test_real_pages_attach_tables_by_page(self, normalizer):
        json_data = {
            "type": "document",
            "kids": [
                {
                    "type": "page",
                    "page_no": 1,
                    "kids": [
                        {
                            "type": "table",
                            "rows": [
                                {
                                    "cells": [
                                        {"kids": [{"content": "항목"}]},
                                        {"kids": [{"content": "금액"}]},
                                    ]
                                }
                            ],
                        }
                    ],
                },
                {
                    "type": "page",
                    "page_no": 2,
                    "kids": [
                        {"type": "paragraph", "content": "2페이지 본문"},
                    ],
                },
            ],
        }
        doc = normalizer.normalize(_odl(markdown="", json_data=json_data))
        assert [p.page_number for p in doc.pages] == [1, 2]
        assert doc.pages[0].table_ids == ["table:0"]
        assert doc.pages[1].table_ids == []


class TestMetadata:
    def test_metadata_fields_present(self, normalizer):
        doc = normalizer.normalize(_odl(markdown="본문", json_data=_SIMPLE_JSON))
        m = doc.metadata
        assert m["extraction_source"] == "odl"
        assert m["has_tables"] is True
        assert m["table_count"] == 1
        assert m["body_char_count"] == len(doc.body_text)
        assert m["normalization_version"] == "v2"

    def test_normalization_version_v2(self, normalizer):
        """normalization_version이 v2여야 한다."""
        doc = normalizer.normalize(_odl(markdown="본문", json_data={}))
        assert doc.metadata["normalization_version"] == "v2"
        assert doc.normalization_version == "v2"

    def test_ocr_metadata(self, normalizer):
        doc = normalizer.normalize(_ocr("텍스트"))
        assert doc.metadata["extraction_source"] == "ocr"
        assert doc.metadata["has_tables"] is False


# ── DocumentSummaryPayloadService ─────────────────────────────────────────────


class TestSummaryPayloadService:
    def _make_doc(self, body: str, tables: list[str]) -> DocumentSchema:
        blocks = [
            DocumentTableBlock(table_id=f"table:{i}", text=t)
            for i, t in enumerate(tables)
        ]
        return DocumentSchema(source_type="odl", body_text=body, table_blocks=blocks)

    def test_body_section_always_present(self, payload_service):
        doc = self._make_doc(body="본문 내용", tables=[])
        result = payload_service.build(doc)
        assert "[본문]" in result
        assert "본문 내용" in result

    def test_table_section_present_when_tables_exist(self, payload_service):
        doc = self._make_doc(body="본문", tables=["[표 1]\ncol1 | col2"])
        result = payload_service.build(doc)
        assert "[표]" in result
        assert "[표 1]" in result

    def test_table_section_omitted_when_no_tables(self, payload_service):
        doc = self._make_doc(body="본문", tables=[])
        result = payload_service.build(doc)
        assert "[표]" not in result

    def test_multiple_tables_joined(self, payload_service):
        doc = self._make_doc(body="본문", tables=["[표 1]\na", "[표 2]\nb"])
        result = payload_service.build(doc)
        assert "[표 1]" in result
        assert "[표 2]" in result

    def test_does_not_read_raw_fields(self, payload_service):
        """payload builder는 raw_* 필드를 읽지 않고 body_text/table_blocks만 읽는다."""
        doc = DocumentSchema(
            source_type="odl",
            raw_markdown="raw markdown",
            body_text="normalized body",
            table_blocks=[],
        )
        result = payload_service.build(doc)
        assert "raw markdown" not in result
        assert "normalized body" in result


# ── sections 파싱 테스트 ──────────────────────────────────────────────────────────────────


class TestNormalizeSections:
    def _norm(self, json_data):
        from domains.document.extract_service import ExtractedDocument

        ext = ExtractedDocument(markdown="", json_data=json_data, source_type="odl")
        return DocumentNormalizeService().normalize(ext)

    def test_heading_paragraph_creates_section(self):
        """heading + paragraph 구조가 섬션 1개로 파싱되어야 한다."""
        json_data = {
            "type": "document",
            "kids": [
                {"type": "heading", "content": "제1조 목적"},
                {"type": "paragraph", "content": "이 계약의 목적은..."},
            ],
        }
        doc = self._norm(json_data)
        assert len(doc.sections) == 1
        assert doc.sections[0].heading == "제1조 목적"
        assert "이 계약의 목적은..." in doc.sections[0].paragraphs

    def test_multiple_headings_create_multiple_sections(self):
        """heading이 여러 개면 각각 섬션으로 분리되어야 한다."""
        json_data = {
            "type": "document",
            "kids": [
                {"type": "heading", "content": "제1조"},
                {"type": "paragraph", "content": "내용1"},
                {"type": "heading", "content": "제2조"},
                {"type": "paragraph", "content": "내용2"},
            ],
        }
        doc = self._norm(json_data)
        assert len(doc.sections) == 2
        assert doc.sections[0].heading == "제1조"
        assert doc.sections[1].heading == "제2조"

    def test_content_before_first_heading_becomes_headingless_section(self):
        """heading 전 내용은 heading=None 인 섬션으로 생성되어야 한다."""
        json_data = {
            "type": "document",
            "kids": [
                {"type": "paragraph", "content": "서문 내용"},
                {"type": "heading", "content": "제1조"},
                {"type": "paragraph", "content": "본문"},
            ],
        }
        doc = self._norm(json_data)
        assert len(doc.sections) == 2
        assert doc.sections[0].heading is None
        assert "서문 내용" in doc.sections[0].paragraphs

    def test_table_in_section_has_table_id(self):
        """JSON에 table이 있으면 해당 섬션의 table_ids에 포함되어야 한다."""
        json_data = {
            "type": "document",
            "kids": [
                {"type": "heading", "content": "계약 금액"},
                {
                    "type": "table",
                    "rows": [
                        {
                            "cells": [
                                {"kids": [{"content": "항목"}]},
                                {"kids": [{"content": "금액"}]},
                            ]
                        }
                    ],
                },
            ],
        }
        doc = self._norm(json_data)
        assert doc.sections
        # table이 있는 섬션에 table_id 포함
        sections_with_tables = [s for s in doc.sections if s.table_ids]
        assert sections_with_tables

    def test_no_json_returns_empty_sections(self):
        """raw_json이 없으면 sections가 빈 리스트여야 한다."""
        from domains.document.extract_service import ExtractedDocument

        ext = ExtractedDocument(markdown="본문", json_data=None, source_type="odl")
        doc = DocumentNormalizeService().normalize(ext)
        assert doc.sections == []

    def test_section_count_in_metadata(self):
        """metadata에 section_count가 포함되어야 한다."""
        json_data = {
            "type": "document",
            "kids": [
                {"type": "heading", "content": "제1조"},
                {"type": "paragraph", "content": "본문"},
            ],
        }
        doc = self._norm(json_data)
        assert doc.metadata.get("section_count") == len(doc.sections)

    def test_sections_roundtrip_serialization(self):
        """sections가 to_dict/from_dict 라운드트립에서 보존되어야 한다."""
        json_data = {
            "type": "document",
            "kids": [
                {"type": "heading", "content": "제1조"},
                {"type": "paragraph", "content": "본문 내용"},
            ],
        }
        doc = self._norm(json_data)
        assert doc.sections

        d = doc.to_dict()
        restored = DocumentSchema.from_dict(d)

        assert len(restored.sections) == len(doc.sections)
        assert restored.sections[0].heading == doc.sections[0].heading
        assert restored.sections[0].paragraphs == doc.sections[0].paragraphs
        assert restored.sections[0].table_ids == doc.sections[0].table_ids
        assert restored.sections[0].page_start == doc.sections[0].page_start
        assert restored.sections[0].page_end == doc.sections[0].page_end
