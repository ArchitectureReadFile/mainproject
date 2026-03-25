"""tests/unit/test_precedent_chunk_builder.py"""

from services.precedent.chunk_builder import (
    MAX_CHUNK_CHARS,
    build_chunks_from_precedent_document,
    build_precedent_document,
)

SAMPLE_TEXT = """대법원 2023. 1. 1. 선고 2022두12345 판결
[양도소득세 부과처분 취소]

【사건】
2022두12345 양도소득세 부과처분 취소

【주문】
원심판결을 파기하고, 사건을 서울고등법원에 환송한다.

【이유】
1. 원심의 판단
원심은 이 사건 처분이 적법하다고 판단하였다.

2. 대법원의 판단
그러나 원심의 판단은 다음과 같은 이유로 수긍하기 어렵다.
가. 과세요건 해석
조세법률주의 원칙에 따라 과세요건은 엄격하게 해석하여야 한다.
나. 결론
원심판결에는 법리 오해의 위법이 있으므로 파기환송한다.
"""

LONG_SECTION_TEXT = """대법원 판결

【이유】
""" + ("이 사건 판결 이유는 다음과 같다. " * 100)


def _build(precedent_id: int, text: str, **kwargs):
    """build_precedent_document + build_chunks_from_precedent_document 조합 헬퍼."""
    doc = build_precedent_document(
        precedent_id=precedent_id,
        source_url="",
        title=kwargs.get("title"),
        gist=kwargs.get("gist"),
        detail_table=kwargs.get("detail_table"),
        detail_text=text,
    )
    return build_chunks_from_precedent_document(doc)


def test_sections_split_correctly():
    chunks = _build(1, SAMPLE_TEXT)
    section_titles = [c["section_title"] for c in chunks]
    assert "주문" in section_titles
    assert "이유" in section_titles


def test_chunk_ids_are_unique():
    chunks = _build(1, SAMPLE_TEXT)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_id_format():
    chunks = _build(1, SAMPLE_TEXT)
    for chunk in chunks:
        assert chunk["chunk_id"].startswith("precedent:1:chunk:")


def test_order_index_sequential():
    chunks = _build(1, SAMPLE_TEXT)
    for i, chunk in enumerate(chunks):
        assert chunk["order_index"] == i


def test_long_section_is_split():
    chunks = _build(2, LONG_SECTION_TEXT)
    이유_chunks = [c for c in chunks if c["section_title"] == "이유"]
    assert len(이유_chunks) > 1
    for c in 이유_chunks:
        assert len(c["text"]) <= MAX_CHUNK_CHARS


def test_empty_text_returns_empty():
    assert _build(1, "") == []
    assert _build(1, "   ") == []


def test_precedent_id_in_all_chunks():
    chunks = _build(42, SAMPLE_TEXT)
    for chunk in chunks:
        assert chunk["precedent_id"] == 42


def test_detail_table_parsed_into_meta_chunk():
    """detail_table의 사건/원고/피고가 meta chunk에 반영된다."""
    chunks = _build(
        1,
        SAMPLE_TEXT,
        detail_table={
            "사건": "2022두12345 양도소득세부과처분취소",
            "원고": "홍길동",
            "피고": "강남세무서장",
        },
    )
    meta_chunks = [c for c in chunks if c["element_type"] == "meta"]
    assert meta_chunks, "meta chunk가 생성되지 않음"
    meta_text = meta_chunks[0]["text"]
    assert "2022두12345" in meta_text
    assert "홍길동" in meta_text


def test_case_number_case_name_split():
    """detail_table['사건'] 파싱 — case_number / case_name 분리."""
    doc = build_precedent_document(
        precedent_id=1,
        source_url="",
        title=None,
        gist=None,
        detail_table={"사건": "2025두34754 종합소득세부과처분취소"},
        detail_text=SAMPLE_TEXT,
    )
    chunks = build_chunks_from_precedent_document(doc)
    assert chunks[0]["case_number"] == "2025두34754"
    assert chunks[0]["case_name"] == "종합소득세부과처분취소"
