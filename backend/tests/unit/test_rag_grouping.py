"""tests/unit/test_rag_grouping.py"""

import pytest

from domains.rag.grouping_service import (
    TOP_CHUNKS_PER_PRECEDENT,
    group_chunks_by_precedent,
)


def _make_hit(
    chunk_id: str, precedent_id: int, score: float, section: str = "이유"
) -> dict:
    return {
        "chunk_id": chunk_id,
        "precedent_id": precedent_id,
        "score": score,
        "title": f"판례_{precedent_id}",
        "source_url": f"http://example.com/{precedent_id}",
        "text": f"{section} 본문 {chunk_id}",
        "section_title": section,
        "element_type": "section",
        "order_index": 0,
    }


def test_groups_by_precedent_id():
    hits = [
        _make_hit("p:1:chunk:0", 1, 0.9),
        _make_hit("p:1:chunk:1", 1, 0.8),
        _make_hit("p:2:chunk:0", 2, 0.7),
    ]
    result = group_chunks_by_precedent(hits)
    assert len(result) == 2
    pids = [g["precedent_id"] for g in result]
    assert 1 in pids and 2 in pids


def test_representative_score_is_max():
    hits = [
        _make_hit("p:1:chunk:0", 1, 0.9),
        _make_hit("p:1:chunk:1", 1, 0.5),
    ]
    result = group_chunks_by_precedent(hits)
    assert result[0]["score"] == pytest.approx(0.9)


def test_top_chunks_per_precedent_limit():
    hits = [_make_hit(f"p:1:chunk:{i}", 1, 0.9 - i * 0.1) for i in range(5)]
    result = group_chunks_by_precedent(hits)
    assert len(result[0]["chunks"]) <= TOP_CHUNKS_PER_PRECEDENT


def test_sorted_by_score_descending():
    hits = [
        _make_hit("p:2:chunk:0", 2, 0.6),
        _make_hit("p:1:chunk:0", 1, 0.9),
    ]
    result = group_chunks_by_precedent(hits)
    assert result[0]["precedent_id"] == 1


def test_empty_input():
    assert group_chunks_by_precedent([]) == []


def test_citation_ids_are_precedent_ids():
    hits = [
        _make_hit("p:1:chunk:0", 1, 0.9),
        _make_hit("p:2:chunk:0", 2, 0.7),
    ]
    grouped = group_chunks_by_precedent(hits)
    pids = {g["precedent_id"] for g in grouped}
    assert pids == {1, 2}
