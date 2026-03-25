"""tests/unit/test_precedent_chunk_builder.py"""

from services.precedent.chunk_builder import MAX_CHUNK_CHARS, build_precedent_chunks

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


def test_sections_split_correctly():
    chunks = build_precedent_chunks(1, SAMPLE_TEXT)
    section_titles = [c["section_title"] for c in chunks]
    assert "주문" in section_titles
    assert "이유" in section_titles


def test_chunk_ids_are_unique():
    chunks = build_precedent_chunks(1, SAMPLE_TEXT)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_id_format():
    chunks = build_precedent_chunks(1, SAMPLE_TEXT)
    for chunk in chunks:
        assert chunk["chunk_id"].startswith("precedent:1:chunk:")


def test_order_index_sequential():
    chunks = build_precedent_chunks(1, SAMPLE_TEXT)
    for i, chunk in enumerate(chunks):
        assert chunk["order_index"] == i


def test_long_section_is_split():
    chunks = build_precedent_chunks(2, LONG_SECTION_TEXT)
    이유_chunks = [c for c in chunks if c["section_title"] == "이유"]
    assert len(이유_chunks) > 1
    for c in 이유_chunks:
        assert len(c["text"]) <= MAX_CHUNK_CHARS


def test_empty_text_returns_empty():
    assert build_precedent_chunks(1, "") == []
    assert build_precedent_chunks(1, "   ") == []


def test_precedent_id_in_all_chunks():
    chunks = build_precedent_chunks(42, SAMPLE_TEXT)
    for chunk in chunks:
        assert chunk["precedent_id"] == 42
