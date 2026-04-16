"""
domains/chat/workspace_selection_parser.py

chat API에서 받은 workspace_selection_json 문자열을
WorkspaceSelection 또는 None으로 변환한다.

validation 정책 (fail-closed):
    - 미전송 / null / 빈 문자열:          → None (include_workspace=False)
    - mode="all":                          → WorkspaceSelection(mode="all")
    - mode="documents" + non-empty ids:    → WorkspaceSelection(mode="documents", ...)
    - mode="documents" + empty ids:        → ValueError (422 upstream에서 잡힘)
    - invalid JSON:                        → ValueError (422)
    - group_id 없이 selection 있음:        → ValueError (호출자가 검사)
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from domains.chat.schemas import ChatWorkspaceSelectionInput
from domains.knowledge.schemas import WorkspaceSelection


def parse_workspace_selection(
    workspace_selection_json: str | None,
) -> WorkspaceSelection | None:
    """
    API 입력 문자열 → WorkspaceSelection | None.

    Returns:
        WorkspaceSelection: valid selection
        None:               선택 없음 (include_workspace=False 처리)

    Raises:
        ValueError: invalid JSON, invalid mode, mode='documents' + empty ids
    """
    if not workspace_selection_json or not workspace_selection_json.strip():
        return None

    try:
        raw = json.loads(workspace_selection_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"workspace_selection_json JSON 파싱 실패: {e}") from e

    try:
        validated = ChatWorkspaceSelectionInput.model_validate(raw)
    except ValidationError as e:
        raise ValueError(str(e)) from e

    return WorkspaceSelection(
        mode=validated.mode,  # type: ignore[arg-type]
        document_ids=validated.document_ids,
    )
