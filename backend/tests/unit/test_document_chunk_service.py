"""
tests/unit/test_document_chunk_service.py

DocumentChunkService 단위 테스트.

검증 목표:
1. DocumentSchema -> GroupDocumentChunk 흐름
2. body/table chunk 분리
3. chunk payload 계약 (_GROUP_DOC_PAYLOAD_FIELDS) 호환
4. 빈 body / 표만 / body만 케이스 안전성
"""

import pytest

from domains.document.document_schema import DocumentSchema, DocumentTableBlock
from domains.rag.document_chunk_service import DocumentChunkService

_GROUP_DOC_PAYLOAD_FIELDS = (
    "chunk_id",
    "document_id",
    "group_id",
    "file_name",
    "source_type",
    "chunk_type",
    "section_title",
    "order_index",
    "text",
)


@pytest.fixture
def svc():
    return DocumentChunkService()


def _doc(body: str = "", tables: list[str] | None = None) -> DocumentSchema:
    blocks = [
        DocumentTableBlock(table_id=f"table:{i}", text=t)
        for i, t in enumerate(tables or [])
    ]
    return DocumentSchema(source_type="odl", body_text=body, table_blocks=blocks)


def _build(svc, doc, document_id=1, group_id=10, file_name="test.pdf"):
    return svc.build_group_document_chunks(
        doc,
        document_id=document_id,
        group_id=group_id,
        file_name=file_name,
    )


# ── payload 계약 호환 ─────────────────────────────────────────────────────────


class TestPayloadCompat:
    def test_all_required_fields_present(self, svc):
        doc = _doc(body="본문 텍스트입니다.")
        chunks = _build(svc, doc)
        assert chunks
        for chunk in chunks:
            for field in _GROUP_DOC_PAYLOAD_FIELDS:
                assert field in chunk, f"필드 누락: {field}"

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
