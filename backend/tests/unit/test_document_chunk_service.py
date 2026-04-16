"""
tests/unit/test_document_chunk_service.py

DocumentChunkService 단위 테스트.

검증 목표:
1. DocumentSchema -> GroupDocumentChunk 흐름
2. body/table chunk 분리
3. chunk payload 계약 (_GROUP_DOC_PAYLOAD_FIELDS) 호환
4. 빈 body / 표만 / body만 케이스 안전성
5. sections 기반 section-aware chunking
   - table chunk section_title이 실제 heading인지 (버그 수정 검증)
6. sections 없을 때 body_text fallback 동작
7. 전략 override (section / page / text / auto)
8. page 전략 downgrade 규칙
"""

import pytest

from domains.document.document_schema import (
    DocumentPage,
    DocumentSchema,
    DocumentSection,
    DocumentTableBlock,
)
from domains.rag.document_chunk_service import DocumentChunkService

_GROUP_DOC_PAYLOAD_FIELDS = (
    "chunk_id",
    "document_id",
    "group_id",
    "file_name",
    "source_type",
    "chunk_type",
    "section_title",
    "page_start",
    "page_end",
    "order_index",
    "text",
)


@pytest.fixture
def svc():
    return DocumentChunkService()


def _doc(
    body: str = "",
    tables: list[str] | None = None,
    sections: list[DocumentSection] | None = None,
    pages: list[DocumentPage] | None = None,
) -> DocumentSchema:
    blocks = [
        DocumentTableBlock(table_id=f"table:{i}", text=t)
        for i, t in enumerate(tables or [])
    ]
    return DocumentSchema(
        source_type="odl",
        body_text=body,
        table_blocks=blocks,
        sections=sections or [],
        pages=pages or [],
    )


def _build(svc, doc, document_id=1, group_id=10, file_name="test.pdf", strategy=None):
    return svc.build_group_document_chunks(
        doc,
        document_id=document_id,
        group_id=group_id,
        file_name=file_name,
        strategy_override=strategy,
    )


# ── payload 계약 호환 ─────────────────────────────────────────────────────────


class TestPayloadCompat:
    def test_all_required_fields_present(self, svc):
        doc = _doc(body="본문 텍스트입니다.")
        chunks = _build(svc, doc)
        assert chunks
        for chunk in chunks:
            for f in _GROUP_DOC_PAYLOAD_FIELDS:
                assert f in chunk, f"필드 누락: {f}"

    def test_chunk_id_format(self, svc):
        doc = _doc(body="본문")
        chunks = _build(svc, doc, document_id=42)
        assert chunks[0]["chunk_id"].startswith("gdoc:42:chunk:")

    def test_metadata_values(self, svc):
        doc = _doc(body="본문")
        chunks = _build(svc, doc, document_id=7, group_id=3, file_name="doc.pdf")
        c = chunks[0]
        assert c["document_id"] == 7
        assert c["group_id"] == 3
        assert c["file_name"] == "doc.pdf"
        assert c["source_type"] == "pdf"

    def test_page_start_end_present(self, svc):
        """page_start / page_end 필드가 항상 존재해야 한다 (None 허용)."""
        doc = _doc(body="본문")
        chunks = _build(svc, doc)
        for chunk in chunks:
            assert "page_start" in chunk
            assert "page_end" in chunk


# ── body / table chunk 분리 ───────────────────────────────────────────────────


class TestChunkTypes:
    def test_body_chunk_type(self, svc):
        doc = _doc(body="본문 내용입니다.")
        chunks = _build(svc, doc)
        types = {c["chunk_type"] for c in chunks}
        assert "body" in types

    def test_table_chunk_type(self, svc):
        doc = _doc(body="본문", tables=["[표 1]\ncol1 | col2"])
        chunks = _build(svc, doc)
        types = {c["chunk_type"] for c in chunks}
        assert "table" in types

    def test_table_text_preserved(self, svc):
        doc = _doc(body="본문", tables=["[표 1]\ncol1 | col2\nval1 | val2"])
        chunks = _build(svc, doc)
        table_chunks = [c for c in chunks if c["chunk_type"] == "table"]
        assert table_chunks
        assert "col1" in table_chunks[0]["text"]
        assert "val1" in table_chunks[0]["text"]

    def test_multiple_tables_each_become_chunk(self, svc):
        doc = _doc(body="본문", tables=["[표 1]\na | b", "[표 2]\nc | d"])
        chunks = _build(svc, doc)
        table_chunks = [c for c in chunks if c["chunk_type"] == "table"]
        assert len(table_chunks) >= 2


# ── 빈값 / edge case ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_body_no_tables_returns_empty(self, svc):
        doc = _doc(body="", tables=[])
        chunks = _build(svc, doc)
        assert chunks == []

    def test_body_only_no_table_chunks(self, svc):
        doc = _doc(body="본문만 있는 문서입니다.")
        chunks = _build(svc, doc)
        assert all(c["chunk_type"] == "body" for c in chunks)

    def test_table_only_no_body_chunks(self, svc):
        doc = _doc(body="", tables=["[표 1]\ncol | val"])
        chunks = _build(svc, doc)
        assert all(c["chunk_type"] == "table" for c in chunks)

    def test_order_index_sequential(self, svc):
        doc = _doc(body="본문", tables=["[표 1]\na | b"])
        chunks = _build(svc, doc)
        indices = [c["order_index"] for c in chunks]
        assert indices == sorted(indices)

    def test_no_empty_text_chunks(self, svc):
        doc = _doc(body="본문\n\n\n\n본문2", tables=["[표 1]\na | b"])
        chunks = _build(svc, doc)
        assert all(c["text"].strip() for c in chunks)


# ── section-aware chunking ────────────────────────────────────────────────────


class TestSectionAwareChunking:
    def test_section_title_propagated_to_body_chunk(self, svc):
        """섹션 제목이 body chunk의 section_title로 전달되어야 한다."""
        sections = [
            DocumentSection(
                heading="계약 당사자",
                paragraphs=["갑은 A주식회사이며, 을은 B주식회사이다."],
                table_ids=[],
                page_start=1,
                page_end=1,
            )
        ]
        doc = _doc(body="갑은 A주식회사이며, 을은 B주식회사이다.", sections=sections)
        chunks = _build(svc, doc)
        body_chunks = [c for c in chunks if c["chunk_type"] == "body"]
        assert body_chunks
        assert body_chunks[0]["section_title"] == "계약 당사자"

    def test_table_section_title_is_heading_not_literal(self, svc):
        """
        table chunk의 section_title이 literal 'table'이 아니라
        실제 섹션 heading이어야 한다. (_split_table 버그 수정 검증)
        """
        sections = [
            DocumentSection(
                heading="계약 금액",
                paragraphs=[],
                table_ids=["table:0"],
                page_start=2,
                page_end=2,
            )
        ]
        doc = _doc(
            body="",
            tables=["[표 1]\n항목 | 금액\n용역비 | 100만원"],
            sections=sections,
        )
        chunks = _build(svc, doc)
        table_chunks = [c for c in chunks if c["chunk_type"] == "table"]
        assert table_chunks
        # "table" literal이 아니라 실제 heading이어야 함
        assert table_chunks[0]["section_title"] == "계약 금액"
        assert table_chunks[0]["section_title"] != "table"

    def test_page_metadata_from_section(self, svc):
        """page_start / page_end가 섹션 정보에서 채워져야 한다."""
        sections = [
            DocumentSection(
                heading="제1조",
                paragraphs=["계약 내용"],
                table_ids=[],
                page_start=2,
                page_end=3,
            )
        ]
        doc = _doc(body="계약 내용", sections=sections)
        chunks = _build(svc, doc)
        assert chunks[0]["page_start"] == 2
        assert chunks[0]["page_end"] == 3

    def test_table_in_section_gets_section_title(self, svc):
        """섹션 내 표 chunk에도 section_title이 전달되어야 한다."""
        sections = [
            DocumentSection(
                heading="계약 금액",
                paragraphs=[],
                table_ids=["table:0"],
                page_start=2,
                page_end=2,
            )
        ]
        doc = _doc(
            body="",
            tables=["[표 1]\n항목 | 금액\n용역비 | 100만원"],
            sections=sections,
        )
        chunks = _build(svc, doc)
        table_chunks = [c for c in chunks if c["chunk_type"] == "table"]
        assert table_chunks
        assert table_chunks[0]["section_title"] == "계약 금액"

    def test_multiple_sections_produce_separate_chunks(self, svc):
        """여러 섹션이 각각의 body chunk로 분리되어야 한다."""
        sections = [
            DocumentSection(heading="제1조", paragraphs=["내용1"], table_ids=[]),
            DocumentSection(heading="제2조", paragraphs=["내용2"], table_ids=[]),
        ]
        doc = _doc(body="내용1\n\n내용2", sections=sections)
        chunks = _build(svc, doc)
        titles = [c["section_title"] for c in chunks if c["chunk_type"] == "body"]
        assert "제1조" in titles
        assert "제2조" in titles

    def test_paragraphs_merged_within_target(self, svc):
        """같은 섹션의 짧은 문단들은 TARGET 범위 내에서 병합되어야 한다."""
        short_paras = ["짧은 문단입니다."] * 5
        sections = [
            DocumentSection(heading="서론", paragraphs=short_paras, table_ids=[])
        ]
        doc = _doc(body="\n\n".join(short_paras), sections=sections)
        chunks = _build(svc, doc)
        body_chunks = [c for c in chunks if c["chunk_type"] == "body"]
        assert len(body_chunks) == 1

    def test_section_none_heading_allowed(self, svc):
        """heading이 None인 섹션(서문 등)도 정상 처리되어야 한다."""
        sections = [
            DocumentSection(heading=None, paragraphs=["이 계약서는..."], table_ids=[])
        ]
        doc = _doc(body="이 계약서는...", sections=sections)
        chunks = _build(svc, doc)
        assert chunks
        assert chunks[0]["section_title"] is None


# ── fallback: sections 없을 때 body_text 경로 ─────────────────────────────────


class TestFallbackChunking:
    def test_no_sections_uses_body_text(self, svc):
        """sections=[] 이면 body_text 기반 fallback chunking이 동작해야 한다."""
        doc = _doc(body="문단1\n\n문단2\n\n문단3")
        chunks = _build(svc, doc)
        assert chunks
        assert all(c["chunk_type"] == "body" for c in chunks)

    def test_fallback_page_fields_are_none(self, svc):
        """fallback 경로에서는 page_start / page_end가 None이어야 한다."""
        doc = _doc(body="본문")
        chunks = _build(svc, doc)
        assert all(c["page_start"] is None for c in chunks)
        assert all(c["page_end"] is None for c in chunks)

    def test_fallback_table_separate_from_body(self, svc):
        """fallback 경로에서도 표가 별도 chunk로 생성되어야 한다."""
        doc = _doc(body="본문", tables=["[표 1]\na | b"])
        chunks = _build(svc, doc)
        types = {c["chunk_type"] for c in chunks}
        assert "body" in types
        assert "table" in types


# ── 전략 override ─────────────────────────────────────────────────────────────


class TestStrategyOverride:
    def test_override_text_ignores_sections(self, svc):
        """strategy=text이면 sections가 있어도 text fallback을 사용해야 한다."""
        sections = [DocumentSection(heading="제1조", paragraphs=["내용"], table_ids=[])]
        doc = _doc(body="내용", sections=sections)
        chunks = _build(svc, doc, strategy="text")
        # text 전략: page_start/page_end가 None
        assert all(c["page_start"] is None for c in chunks)
        assert all(c["page_end"] is None for c in chunks)

    def test_override_section_uses_sections(self, svc):
        """strategy=section이면 sections 경로를 사용해야 한다."""
        sections = [
            DocumentSection(
                heading="조항1",
                paragraphs=["내용1"],
                table_ids=[],
                page_start=1,
                page_end=1,
            )
        ]
        doc = _doc(body="내용1", sections=sections)
        chunks = _build(svc, doc, strategy="section")
        body_chunks = [c for c in chunks if c["chunk_type"] == "body"]
        assert body_chunks[0]["section_title"] == "조항1"
        assert body_chunks[0]["page_start"] == 1

    def test_override_section_without_sections_falls_to_text(self, svc):
        """strategy=section인데 sections=[]이면 text fallback이어야 한다."""
        doc = _doc(body="본문", sections=[])
        chunks = _build(svc, doc, strategy="section")
        assert chunks
        assert all(c["page_start"] is None for c in chunks)

    def test_override_auto_prefers_section(self, svc):
        """strategy=auto이고 sections가 있으면 section 전략을 선택해야 한다."""
        sections = [
            DocumentSection(
                heading="제목",
                paragraphs=["내용"],
                table_ids=[],
                page_start=1,
                page_end=1,
            )
        ]
        doc = _doc(body="내용", sections=sections)
        chunks = _build(svc, doc, strategy="auto")
        body_chunks = [c for c in chunks if c["chunk_type"] == "body"]
        assert body_chunks[0]["section_title"] == "제목"

    def test_override_page_with_real_pages(self, svc):
        """strategy=page이고 실제 page 정보가 있으면 page 전략을 사용해야 한다."""
        pages = [
            DocumentPage(
                page_number=1,
                text="1페이지 본문",
                table_ids=[],
                metadata={},  # estimated 없음 → 실제 page
            )
        ]
        doc = _doc(body="1페이지 본문", pages=pages)
        chunks = _build(svc, doc, strategy="page")
        body_chunks = [c for c in chunks if c["chunk_type"] == "body"]
        assert body_chunks
        assert body_chunks[0]["page_start"] == 1
        assert body_chunks[0]["page_end"] == 1

    def test_override_page_without_real_pages_downgrades_to_text(self, svc):
        """
        strategy=page인데 pages가 estimated=True(page 1 단순화)이면
        text fallback으로 downgrade되어야 한다.
        page 전략이 있는 척만 하지 않기 위한 downgrade 규칙 검증.
        """
        pages = [
            DocumentPage(
                page_number=1,
                text="본문",
                table_ids=[],
                metadata={"estimated": True},  # page 1 단순화 상태
            )
        ]
        doc = _doc(body="본문", pages=pages)
        chunks = _build(svc, doc, strategy="page")
        # downgrade → text fallback: page_start None
        assert all(c["page_start"] is None for c in chunks)

    def test_override_page_empty_pages_downgrades_to_text(self, svc):
        """pages=[]이면 page 전략이 text로 downgrade되어야 한다."""
        doc = _doc(body="본문", pages=[])
        chunks = _build(svc, doc, strategy="page")
        assert all(c["page_start"] is None for c in chunks)


# ── auto: sections 없고 estimated pages → text fallback ──────────────────────


class TestAutoStrategy:
    def test_auto_no_sections_no_real_pages_uses_text(self, svc):
        """auto에서 sections도 없고 real pages도 없으면 text fallback이어야 한다."""
        doc = _doc(body="본문\n\n문단2")
        chunks = _build(svc, doc, strategy="auto")
        assert chunks
        assert all(c["page_start"] is None for c in chunks)

    def test_auto_with_sections_skips_page_check(self, svc):
        """auto에서 sections가 있으면 page 여부와 무관하게 section 전략이어야 한다."""
        sections = [DocumentSection(heading="조항", paragraphs=["내용"], table_ids=[])]
        pages = [DocumentPage(page_number=1, text="내용", metadata={"estimated": True})]
        doc = _doc(body="내용", sections=sections, pages=pages)
        chunks = _build(svc, doc, strategy="auto")
        body_chunks = [c for c in chunks if c["chunk_type"] == "body"]
        assert body_chunks[0]["section_title"] == "조항"
