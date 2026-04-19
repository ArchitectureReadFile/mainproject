"""
tests/unit/test_answer_context_builder.py

AnswerContextBuilder 단위 테스트.
"""

from __future__ import annotations

import pytest

from domains.knowledge.answer_context_builder import AnswerContextBuilder
from domains.knowledge.schemas import RetrievedKnowledgeItem
from settings.knowledge import (
    ANSWER_CONTEXT_PLATFORM_TEXT_MAX,
    ANSWER_CONTEXT_PLATFORM_TOP_K,
    ANSWER_CONTEXT_SESSION_TOP_K,
    ANSWER_CONTEXT_WORKSPACE_TEXT_MAX,
    ANSWER_CONTEXT_WORKSPACE_TOP_K,
)


@pytest.fixture
def builder():
    return AnswerContextBuilder()


def _platform(
    title: str = "판례 제목",
    chunk_text: str = "판례 내용",
    score: float = 0.9,
    source_url: str | None = "https://example.com",
    case_number: str | None = "2024구합10997",
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type="platform",
        source_type="precedent",
        source_id=1,
        title=title,
        chunk_text=chunk_text,
        score=score,
        metadata={
            "source_url": source_url,
            "case_number": case_number,
        },
    )


def _workspace(
    title: str = "문서.pdf",
    chunk_text: str = "문서 내용",
    score: float = 0.7,
    chunk_type: str = "body",
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type="workspace",
        source_type="workspace_document",
        source_id=10,
        title=title,
        chunk_text=chunk_text,
        score=score,
        metadata={"file_name": title, "chunk_type": chunk_type},
    )


def _session(
    title: str = "첨부 문서",
    chunk_text: str = "세션 문서 내용",
    score: float = 1.0,
    chunk_id: str | None = "session:1:chunk:10",
    chunk_order: int | None = 2,
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type="session",
        source_type="session_document",
        source_id="session:1",
        title=title,
        chunk_text=chunk_text,
        score=score,
        chunk_id=chunk_id,
        metadata={"session_title": title, "chunk_order": chunk_order},
    )


# ── 블록 구분 ─────────────────────────────────────────────────────────────────


class TestBlockSeparation:
    def test_platform_block_header(self, builder):
        result = builder.build([_platform()])
        assert "[플랫폼 지식]" in result

    def test_workspace_block_header(self, builder):
        result = builder.build([_workspace()])
        assert "[워크스페이스 문서]" in result

    def test_session_block_header(self, builder):
        result = builder.build([_session()])
        assert "[임시 문서]" in result

    def test_all_blocks_present(self, builder):
        result = builder.build([_platform(), _workspace(), _session()])
        assert "[플랫폼 지식]" in result
        assert "[워크스페이스 문서]" in result
        assert "[임시 문서]" in result

    def test_block_order_fixed(self, builder):
        result = builder.build([_session(), _workspace(), _platform()])
        p_idx = result.index("[플랫폼 지식]")
        w_idx = result.index("[워크스페이스 문서]")
        s_idx = result.index("[임시 문서]")
        assert p_idx < w_idx < s_idx


# ── 빈 블록 생략 ──────────────────────────────────────────────────────────────


class TestEmptyBlockOmission:
    def test_empty_platform_omitted(self, builder):
        result = builder.build([_workspace()])
        assert "[플랫폼 지식]" not in result

    def test_empty_workspace_omitted(self, builder):
        result = builder.build([_platform()])
        assert "[워크스페이스 문서]" not in result

    def test_empty_session_omitted(self, builder):
        result = builder.build([_platform()])
        assert "[임시 문서]" not in result

    def test_empty_list_returns_empty_string(self, builder):
        result = builder.build([])
        assert result == ""


# ── source별 item 개수 제한 ───────────────────────────────────────────────────


class TestTopKLimit:
    def test_platform_top_k(self, builder):
        items = [_platform(title=f"판례{i}", chunk_text=f"내용{i}") for i in range(10)]
        result = builder.build(items)
        # 설정된 platform top-k개 초과 항목은 포함되지 않아야 함
        count = result.count("- 제목: 판례")
        assert count == ANSWER_CONTEXT_PLATFORM_TOP_K

    def test_workspace_top_k(self, builder):
        items = [
            _workspace(title=f"문서{i}.pdf", chunk_text=f"내용{i}") for i in range(10)
        ]
        result = builder.build(items)
        count = result.count("- 문서: 문서")
        assert count == ANSWER_CONTEXT_WORKSPACE_TOP_K

    def test_session_top_k(self, builder):
        items = [_session(title=f"첨부{i}", chunk_text=f"내용{i}") for i in range(5)]
        result = builder.build(items)
        count = result.count("- 제목: 첨부")
        assert count == ANSWER_CONTEXT_SESSION_TOP_K


# ── chunk_text 길이 제한 ──────────────────────────────────────────────────────


class TestTextTrim:
    def test_platform_text_trimmed(self, builder):
        long_text = "가" * (ANSWER_CONTEXT_PLATFORM_TEXT_MAX + 500)
        result = builder.build([_platform(chunk_text=long_text)])
        assert "…" in result
        # 원문 전체가 들어가지 않음
        assert long_text not in result

    def test_workspace_text_trimmed(self, builder):
        long_text = "나" * (ANSWER_CONTEXT_WORKSPACE_TEXT_MAX + 500)
        result = builder.build([_workspace(chunk_text=long_text)])
        assert "…" in result

    def test_session_text_trimmed(self, builder):
        long_text = "다" * 4000
        result = builder.build([_session(chunk_text=long_text)])
        assert long_text in result

    def test_short_text_not_trimmed(self, builder):
        result = builder.build([_platform(chunk_text="짧은 내용")])
        assert "…" not in result


# ── metadata 출처 정보 ────────────────────────────────────────────────────────


class TestMetadataFields:
    def test_platform_source_url(self, builder):
        result = builder.build([_platform(source_url="https://taxlaw.nts.go.kr")])
        assert "https://taxlaw.nts.go.kr" in result

    def test_platform_case_number(self, builder):
        result = builder.build([_platform(case_number="2024구합10997")])
        assert "2024구합10997" in result

    def test_platform_no_source_url_omitted(self, builder):
        result = builder.build([_platform(source_url=None)])
        assert "출처:" not in result

    def test_workspace_file_name(self, builder):
        result = builder.build([_workspace(title="계약서.pdf")])
        assert "계약서.pdf" in result

    def test_workspace_chunk_type(self, builder):
        result = builder.build([_workspace(chunk_type="table")])
        assert "table" in result

    def test_session_title(self, builder):
        result = builder.build([_session(title="이번 회의 자료")])
        assert "이번 회의 자료" in result

    def test_session_chunk_citation_id(self, builder):
        result = builder.build([_session(chunk_id="session:1:chunk:77")])
        assert "근거ID: session:1:chunk:77" in result

    def test_session_chunk_order(self, builder):
        result = builder.build([_session(chunk_order=4)])
        assert "청크순번: 5" in result
