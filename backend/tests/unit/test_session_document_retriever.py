from __future__ import annotations

from types import SimpleNamespace

from domains.knowledge.schemas import KnowledgeRetrievalRequest
from domains.knowledge.session_document_retriever import SessionDocumentRetriever


def test_session_document_retriever_prefers_relevant_chunk():
    retriever = SessionDocumentRetriever()
    long_intro = "회의 개요와 일반 안내 사항입니다. " * 80
    text = "\n\n".join(
        [
            long_intro,
            "개인정보 처리 위탁 시 수탁자 관리, 재위탁 통제, 안전조치 의무를 명시해야 합니다.",
            "부록입니다.",
        ]
    )
    request = KnowledgeRetrievalRequest(
        query="개인정보 처리 위탁 의무를 알려줘",
        session_id=7,
        include_session=True,
    )

    items = retriever.retrieve_from_text(
        request,
        session_reference_text=text,
        session_title="첨부 문서",
    )

    assert items
    assert "개인정보 처리 위탁" in items[0].chunk_text
    assert items[0].chunk_id != "session:7:chunk:0"


def test_session_document_retriever_splits_long_text_into_multiple_chunks():
    retriever = SessionDocumentRetriever()
    long_text = ("가" * 900) + "\n\n" + ("나" * 900) + "\n\n" + ("다" * 900)
    request = KnowledgeRetrievalRequest(
        query="나 관련 내용을 알려줘",
        session_id=3,
        include_session=True,
    )

    items = retriever.retrieve_from_text(
        request,
        session_reference_text=long_text,
        session_title="긴 문서",
    )

    assert len(items) >= 2
    assert len({item.chunk_id for item in items}) == len(items)
    assert any("나" * 100 in item.chunk_text for item in items)


def test_session_document_retriever_prefers_stored_chunks_when_present():
    retriever = SessionDocumentRetriever()
    request = KnowledgeRetrievalRequest(
        query="개인정보 처리 위탁 의무를 알려줘",
        session_id=8,
        include_session=True,
    )
    stored_chunks = [
        SimpleNamespace(
            id=101, chunk_order=0, chunk_text="회의 개요와 일반 안내 사항입니다."
        ),
        SimpleNamespace(
            id=102,
            chunk_order=1,
            chunk_text="개인정보 처리 위탁 시 수탁자 관리와 안전조치 의무를 명시해야 합니다.",
        ),
    ]

    items = retriever.retrieve(
        request,
        stored_chunks=stored_chunks,
        session_reference_text="원문 전체",
        session_title="첨부 문서",
    )

    assert items
    assert items[0].chunk_id == "session:8:chunk:102"
    assert "개인정보 처리 위탁" in items[0].chunk_text
