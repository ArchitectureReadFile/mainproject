"""
tests/unit/test_chat_workspace_auth.py

workspace retrieval 권한 검증 단위 테스트.

검증 목표:
1. selection 있음 + 유효한 group membership → 성공 (task enqueue)
2. selection 있음 + 권한 없는 group_id → AUTH_FORBIDDEN
3. selection 있음 + 존재하지 않는 group_id → GROUP_NOT_FOUND
4. selection 있음 + 비활성 group → GROUP_NOT_FOUND
5. selection 없음 → group 검증 불필요, 기존 흐름 유지
6. mode="documents" fail-closed: WorkspaceKnowledgeRetriever 빈 결과 반환

정책 메모:
    - mode="all":       지원 (group_id scope 검색)
    - mode="documents": backend 계약상 허용,
                        실제 document_ids 필터는 미구현 (fail-closed → 빈 결과)
                        추후 11단계에서 Qdrant/BM25 필터 구현 예정
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import GroupStatus, MembershipStatus
from schemas.knowledge import WorkspaceSelection


def _make_db(
    session_exists=True,
    group_exists=True,
    group_active=True,
    member_exists=True,
    member_active=True,
):
    """DB mock 빌더. 쿼리 체인을 단계별로 세팅한다."""
    db = MagicMock()

    mock_session = MagicMock()
    mock_session.user_id = 10

    if group_exists and group_active:
        mock_group = MagicMock()
        mock_group.id = 5
        mock_group.status = GroupStatus.ACTIVE
    else:
        mock_group = None

    if member_exists and member_active:
        mock_member = MagicMock()
        mock_member.status = MembershipStatus.ACTIVE
    else:
        mock_member = None

    def _query_side_effect(model):
        from models.model import ChatSession, Group, GroupMember

        mock_q = MagicMock()
        if model is ChatSession:
            mock_q.filter.return_value.first.return_value = (
                mock_session if session_exists else None
            )
        elif model is Group:
            mock_q.filter.return_value.first.return_value = mock_group
        elif model is GroupMember:
            mock_q.filter.return_value.first.return_value = mock_member
        else:
            mock_q.filter.return_value.first.return_value = None
            mock_q.filter.return_value.order_by.return_value.all.return_value = []
        return mock_q

    db.query.side_effect = _query_side_effect
    return db


@pytest.fixture
def svc():
    from services.chat.chat_service import ChatService

    return ChatService()


def _send(svc, db, group_id=None, workspace_selection=None):
    with patch("services.chat.chat_service.process_chat_message"):
        with patch("tasks.chat_task.process_chat_message") as mock_celery:
            mock_celery.delay = MagicMock()
            return svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=group_id,
                workspace_selection=workspace_selection,
            )


# ── selection 없음 → 기존 흐름 ────────────────────────────────────────────────


class TestNoSelection:
    def test_no_selection_skips_group_check(self, svc):
        db = _make_db(member_exists=False)
        with patch("tasks.chat_task.process_chat_message") as mock_task:
            mock_task.delay = MagicMock()
            result = svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=None,
                workspace_selection=None,
            )
        assert result["status"] == "success"

    def test_no_selection_with_group_id_skips_check(self, svc):
        """group_id가 있어도 selection이 없으면 권한 검사 안 함."""
        db = _make_db(member_exists=False)
        with patch("tasks.chat_task.process_chat_message") as mock_task:
            mock_task.delay = MagicMock()
            result = svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=99,
                workspace_selection=None,
            )
        assert result["status"] == "success"


# ── selection 있음 + 권한 검증 ────────────────────────────────────────────────


class TestWithSelection:
    def test_valid_member_succeeds(self, svc):
        db = _make_db(group_exists=True, group_active=True, member_exists=True)
        with patch("tasks.chat_task.process_chat_message") as mock_task:
            mock_task.delay = MagicMock()
            result = svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=5,
                workspace_selection=WorkspaceSelection(mode="all"),
            )
        assert result["status"] == "success"

    def test_non_member_raises_forbidden(self, svc):
        db = _make_db(group_exists=True, group_active=True, member_exists=False)
        with pytest.raises(AppException) as exc:
            svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=5,
                workspace_selection=WorkspaceSelection(mode="all"),
            )
        assert exc.value.error_code == ErrorCode.AUTH_FORBIDDEN

    def test_group_not_found_raises(self, svc):
        db = _make_db(group_exists=False)
        with pytest.raises(AppException) as exc:
            svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=999,
                workspace_selection=WorkspaceSelection(mode="all"),
            )
        assert exc.value.error_code == ErrorCode.GROUP_NOT_FOUND

    def test_inactive_group_raises_not_found(self, svc):
        db = _make_db(group_exists=True, group_active=False)
        with pytest.raises(AppException) as exc:
            svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=5,
                workspace_selection=WorkspaceSelection(mode="all"),
            )
        assert exc.value.error_code == ErrorCode.GROUP_NOT_FOUND

    def test_task_not_enqueued_on_auth_failure(self, svc):
        """권한 실패 시 task가 enqueue되지 않아야 한다."""
        db = _make_db(group_exists=True, group_active=True, member_exists=False)
        with patch("tasks.chat_task.process_chat_message") as mock_task:
            mock_task.delay = MagicMock()
            with pytest.raises(AppException):
                svc.send_message(
                    db=db,
                    user_id=10,
                    session_id=1,
                    text="질문",
                    group_id=5,
                    workspace_selection=WorkspaceSelection(mode="all"),
                )
            mock_task.delay.assert_not_called()


# ── mode="documents" fail-closed ─────────────────────────────────────────────


class TestDocumentsModeFailClosed:
    def test_documents_mode_retriever_returns_empty(self):
        """
        mode="documents"는 현재 WorkspaceKnowledgeRetriever에서 빈 결과 반환.
        전체 group 검색으로 fallback하지 않는다.
        """
        from schemas.knowledge import KnowledgeRetrievalRequest
        from services.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=WorkspaceSelection(
                mode="documents", document_ids=[10, 20]
            ),
        )

        with patch(
            "services.knowledge.workspace_knowledge_retriever.retrieve_group_documents"
        ) as mock_retrieve:
            result = retriever.retrieve(req)

        assert result == []
        mock_retrieve.assert_not_called()

    def test_all_mode_still_works(self):
        from schemas.knowledge import KnowledgeRetrievalRequest
        from services.knowledge.workspace_knowledge_retriever import (
            WorkspaceKnowledgeRetriever,
        )

        retriever = WorkspaceKnowledgeRetriever()
        req = KnowledgeRetrievalRequest(
            query="질문",
            include_workspace=True,
            group_id=1,
            workspace_selection=WorkspaceSelection(mode="all"),
        )

        with patch(
            "services.knowledge.workspace_knowledge_retriever.retrieve_group_documents",
            return_value=[],
        ) as mock_retrieve:
            retriever.retrieve(req)

        mock_retrieve.assert_called_once()
