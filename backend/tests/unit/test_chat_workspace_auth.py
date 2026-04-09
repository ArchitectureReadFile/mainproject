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

구현 계약 메모:
    _require_group_membership 내부 흐름:
        1. get_group_with_role(user_id, group_id) → 멤버이면 (group, role) 반환
        2. None이면 get_group_by_id(group_id) → 그룹 존재 여부 확인
        3. 그룹 없으면 → GROUP_NOT_FOUND
        4. 그룹 있는데 멤버 아니면 → AUTH_FORBIDDEN

    non-member + group 존재 케이스 → AUTH_FORBIDDEN (GROUP_NOT_FOUND 아님)

    mock 전략:
        ChatService._require_group_membership 자체를 patch.
        GroupRepository/GroupService 내부 체인이 복잡하므로
        단위 테스트 목적상 서비스 경계(send_message 진입점)에서 mock한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from schemas.knowledge import WorkspaceSelection

_PATCH_REQUIRE = "services.chat.chat_service.ChatService._require_group_membership"


def _make_mock_task():
    """process_chat_message mock 빌더. task.id를 string으로 고정해 Redis DataError 방지."""
    mock_task = MagicMock()
    mock_result = MagicMock()
    mock_result.id = "test-task-id"
    mock_task.delay.return_value = mock_result
    return mock_task


def _make_db(session_exists=True):
    """최소 DB mock: ChatSession 조회만 처리."""
    from models.model import ChatSession

    db = MagicMock()
    mock_session = MagicMock()
    mock_session.user_id = 10
    mock_session.reference_group_id = None

    def _query_side_effect(*models):
        primary = models[0] if models else None
        mock_q = MagicMock()
        mock_q.join.return_value = mock_q
        mock_q.options.return_value = mock_q
        mock_q.filter.return_value.first.return_value = (
            mock_session if (primary is ChatSession and session_exists) else None
        )
        return mock_q

    db.query.side_effect = _query_side_effect
    return db


@pytest.fixture
def svc():
    from services.chat.chat_service import ChatService

    return ChatService()


# ── selection 없음 → 기존 흐름 ────────────────────────────────────────────────


class TestNoSelection:
    def test_no_selection_skips_group_check(self, svc):
        """workspace_selection=None이면 _require_group_membership 호출 안 함."""
        db = _make_db()
        with (
            patch(_PATCH_REQUIRE) as mock_require,
            patch("tasks.chat_task.process_chat_message", _make_mock_task()),
        ):
            result = svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=None,
                workspace_selection=None,
            )
        assert result["status"] == "success"
        mock_require.assert_not_called()

    def test_no_selection_with_group_id_skips_check(self, svc):
        """group_id가 있어도 selection이 없으면 권한 검사 안 함."""
        db = _make_db()
        with (
            patch(_PATCH_REQUIRE) as mock_require,
            patch("tasks.chat_task.process_chat_message", _make_mock_task()),
        ):
            result = svc.send_message(
                db=db,
                user_id=10,
                session_id=1,
                text="질문",
                group_id=99,
                workspace_selection=None,
            )
        assert result["status"] == "success"
        mock_require.assert_not_called()


# ── selection 있음 + 권한 검증 ────────────────────────────────────────────────


class TestWithSelection:
    def test_valid_member_succeeds(self, svc):
        """_require_group_membership가 정상 통과하면 task가 enqueue된다."""
        db = _make_db()
        with (
            patch(_PATCH_REQUIRE),  # 예외 없이 통과
            patch("tasks.chat_task.process_chat_message", _make_mock_task()),
        ):
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
        """
        멤버십 없는 유저 + 존재하는 그룹 → AUTH_FORBIDDEN.
        구현: get_group_with_role → None → get_group_by_id → group 있음
              → _assert_group_readable 통과 → AUTH_FORBIDDEN 발생
        """
        db = _make_db()
        with patch(
            _PATCH_REQUIRE,
            side_effect=AppException(ErrorCode.AUTH_FORBIDDEN),
        ):
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
        """존재하지 않는 group_id → GROUP_NOT_FOUND."""
        db = _make_db()
        with patch(
            _PATCH_REQUIRE,
            side_effect=AppException(ErrorCode.GROUP_NOT_FOUND),
        ):
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
        """비활성(BLOCKED 등) 그룹 → GROUP_NOT_FOUND."""
        db = _make_db()
        with patch(
            _PATCH_REQUIRE,
            side_effect=AppException(ErrorCode.GROUP_NOT_FOUND),
        ):
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
        db = _make_db()
        mock_task = _make_mock_task()
        with (
            patch(
                _PATCH_REQUIRE,
                side_effect=AppException(ErrorCode.AUTH_FORBIDDEN),
            ),
            patch("tasks.chat_task.process_chat_message", mock_task),
        ):
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
