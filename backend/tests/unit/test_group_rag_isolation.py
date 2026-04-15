"""
tests/unit/test_group_rag_isolation.py

그룹 PDF RAG corpus isolation 테스트.

검증 목표:
1. group document hybrid 검색에서 precedent chunk가 섞이지 않음
2. 다른 group 문서 chunk도 섞이지 않음
3. precedent 검색에서 group document chunk가 섞이지 않음
4. APPROVED 아닌 문서 task 호출 시 skip 확인
"""

from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http import models as qmodels

from domains.rag import bm25_store
from domains.rag.vector_store import _passes_filter

# ── bm25_store corpus 분리 테스트 ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_bm25(fake_redis):
    """각 테스트 전 BM25 상태 초기화."""
    yield
    # fake_redis는 테스트마다 새로 생성되므로 별도 teardown 불필요


@pytest.fixture()
def fake_redis(monkeypatch):
    """실제 Redis 대신 fakeredis 사용."""
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("domains.rag.bm25_store._redis", r)
    return r


def test_precedent_corpus_does_not_contain_group_doc_chunks(fake_redis):
    """판례 corpus 검색 결과에 group document chunk가 없어야 한다."""
    bm25_store.upsert("p:1:chunk:0", precedent_id=1, text="원고 납세의무 취소 청구")
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0", document_id=10, group_id=1, text="원고 납세의무 취소 청구"
    )

    results = bm25_store.search("납세의무", top_k=10)
    chunk_ids = [r["chunk_id"] for r in results]

    assert all(cid.startswith("p:") for cid in chunk_ids), (
        f"판례 corpus에 group doc chunk가 섞임: {chunk_ids}"
    )


def test_group_doc_corpus_does_not_contain_precedent_chunks(fake_redis):
    """그룹 문서 corpus 검색 결과에 판례 chunk가 없어야 한다."""
    bm25_store.upsert("p:1:chunk:0", precedent_id=1, text="원고 납세의무 취소 청구")
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0", document_id=10, group_id=1, text="원고 납세의무 취소 청구"
    )

    results = bm25_store.search_documents("납세의무", group_id=1, top_k=10)
    chunk_ids = [r["chunk_id"] for r in results]

    assert all(cid.startswith("gdoc:") for cid in chunk_ids), (
        f"그룹문서 corpus에 판례 chunk가 섞임: {chunk_ids}"
    )


def test_group_search_isolated_by_group_id(fake_redis):
    """다른 group_id 문서 chunk는 검색 결과에 나오지 않아야 한다."""
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0", document_id=10, group_id=1, text="세금 납부 고지서"
    )
    bm25_store.upsert_document_chunk(
        "gdoc:20:chunk:0", document_id=20, group_id=2, text="세금 납부 고지서"
    )

    results_g1 = bm25_store.search_documents("세금 납부", group_id=1, top_k=10)
    chunk_ids_g1 = [r["chunk_id"] for r in results_g1]

    assert "gdoc:10:chunk:0" in chunk_ids_g1
    assert "gdoc:20:chunk:0" not in chunk_ids_g1, "다른 group chunk가 섞임"


def test_delete_document_cleans_group_index(fake_redis):
    """delete_document 후 해당 chunk가 group 역인덱스에서도 제거된다."""
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0", document_id=10, group_id=1, text="세금"
    )
    bm25_store.delete_document(document_id=10)

    results = bm25_store.search_documents("세금", group_id=1, top_k=10)
    assert results == []


# ── vector_store._passes_filter 테스트 ───────────────────────────────────────


def _make_filter(key: str, value) -> qmodels.Filter:
    return qmodels.Filter(
        must=[qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))]
    )


def test_passes_filter_match():
    payload = {"source_type": "pdf", "group_id": 1}
    f = _make_filter("group_id", 1)
    assert _passes_filter(payload, f) is True


def test_passes_filter_mismatch():
    payload = {"source_type": "pdf", "group_id": 2}
    f = _make_filter("group_id", 1)
    assert _passes_filter(payload, f) is False


def test_passes_filter_missing_field():
    payload = {"source_type": "pdf"}
    f = _make_filter("group_id", 1)
    assert _passes_filter(payload, f) is False


def test_passes_filter_none():
    assert _passes_filter({"anything": "value"}, None) is True


# ── group_document_task approval 검증 테스트 ─────────────────────────────────


def _make_document(approval_status=None, stored_path="/tmp/fake.pdf"):
    from models.model import DocumentLifecycleStatus, GroupStatus

    doc = MagicMock()
    doc.group_id = 1
    doc.original_filename = "test.pdf"
    doc.stored_path = stored_path
    doc.lifecycle_status = DocumentLifecycleStatus.ACTIVE
    doc.group = MagicMock()
    doc.group.status = GroupStatus.ACTIVE
    if approval_status is None:
        doc.approval = None
    else:
        doc.approval = MagicMock()
        doc.approval.status = approval_status
    return doc


@patch("domains.document.index_task.index_group_document")
@patch("domains.document.index_task.DocumentRepository")
@patch("domains.document.index_task.SessionLocal")
def test_task_skips_non_approved(mock_session, mock_repo_cls, mock_index):
    from domains.document.index_task import index_approved_document
    from models.model import ReviewStatus

    mock_repo = mock_repo_cls.return_value
    mock_repo.get_by_id.return_value = _make_document(ReviewStatus.PENDING_REVIEW)

    result = index_approved_document.run(document_id=99)

    assert result["indexed"] is False
    assert result["reason"] == "document_not_approved"
    mock_index.assert_not_called()


@patch("domains.document.index_task.index_group_document", return_value=5)
@patch("domains.document.index_task.DocumentRepository")
@patch("domains.document.index_task.SessionLocal")
@patch("os.path.exists", return_value=True)
def test_task_indexes_approved(mock_exists, mock_session, mock_repo_cls, mock_index):
    from domains.document.index_task import index_approved_document
    from models.model import ReviewStatus

    mock_repo = mock_repo_cls.return_value
    mock_repo.get_by_id.return_value = _make_document(ReviewStatus.APPROVED)

    result = index_approved_document.run(document_id=99)

    assert result["indexed"] is True
    assert result["chunks"] == 5
    mock_index.assert_called_once()


@patch("domains.document.index_task.index_group_document")
@patch("domains.document.index_task.DocumentRepository")
@patch("domains.document.index_task.SessionLocal")
def test_task_skips_missing_document(mock_session, mock_repo_cls, mock_index):
    from domains.document.index_task import index_approved_document

    mock_repo = mock_repo_cls.return_value
    mock_repo.get_by_id.return_value = None

    result = index_approved_document.run(document_id=999)

    assert result["indexed"] is False
    assert result["reason"] == "document_not_found"
    mock_index.assert_not_called()


# ── small-group lexical fallback 테스트 ──────────────────────────────────────


def test_fallback_triggers_when_bm25_all_zero(fake_redis):
    """
    단일 문서 그룹에서 BM25 idf=0 → score 전부 0 → lexical fallback이 결과를 반환해야 한다.
    """
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0",
        document_id=10,
        group_id=1,
        text="양도소득세 납부 고지서 이의신청",
    )

    results = bm25_store.search_documents("양도소득세", group_id=1, top_k=5)

    assert len(results) > 0, "fallback 결과가 비어 있음"
    assert results[0]["chunk_id"] == "gdoc:10:chunk:0"
    assert results[0]["score"] > 0


def test_fallback_isolation_maintained(fake_redis):
    """
    fallback 실행 시에도 다른 group_id chunk는 섞이지 않아야 한다.
    """
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0", document_id=10, group_id=1, text="양도소득세 납부"
    )
    bm25_store.upsert_document_chunk(
        "gdoc:20:chunk:0", document_id=20, group_id=2, text="양도소득세 납부"
    )

    results = bm25_store.search_documents("양도소득세", group_id=1, top_k=10)
    chunk_ids = [r["chunk_id"] for r in results]

    assert "gdoc:10:chunk:0" in chunk_ids
    assert "gdoc:20:chunk:0" not in chunk_ids, "fallback에서도 다른 group chunk가 섞임"


def test_fallback_no_match_returns_empty(fake_redis):
    """query token이 하나도 매칭되지 않으면 빈 리스트를 반환해야 한다."""
    bm25_store.upsert_document_chunk(
        "gdoc:10:chunk:0", document_id=10, group_id=1, text="양도소득세 납부"
    )

    results = bm25_store.search_documents("형사소송 피고인", group_id=1, top_k=5)
    assert results == []
