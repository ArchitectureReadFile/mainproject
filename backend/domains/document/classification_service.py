"""
domains/document/classification_service.py

document_type / category 단일값 분류.

입력: title (str | None), body_text (str)
출력: {"document_type": str, "category": str}
분류 실패 시 두 필드 모두 "미분류" 반환.
"""

from __future__ import annotations

import logging
import os

from infra.llm.client import LLMClient
from prompts.classify_prompt import CLASSIFY_PROMPT

logger = logging.getLogger(__name__)

_ALLOWED_DOCUMENT_TYPES = {
    "계약서",
    "신청서",
    "준비서면",
    "의견서",
    "내용증명",
    "소장",
    "고소장",
    "기타",
    "미분류",
}
_ALLOWED_CATEGORIES = {"민사", "계약", "회사", "행정", "형사", "노동", "기타", "미분류"}
_FALLBACK = {"document_type": "미분류", "category": "미분류"}


class DocumentClassificationService:
    def __init__(self):
        self.client = LLMClient()

    def classify(self, *, title: str | None, body_text: str) -> dict[str, str]:
        max_chars = int(os.environ.get("CLASSIFY_MAX_TEXT_CHARS", "3000"))

        header = f"제목: {title}\n\n" if title else ""
        snippet = (header + body_text)[:max_chars]

        if not snippet.strip():
            logger.warning("[분류 스킵] 입력 텍스트 없음 → 미분류 반환")
            return _FALLBACK

        prompt = CLASSIFY_PROMPT.replace("{text}", snippet)

        try:
            raw = self.client.call_json(prompt, num_predict=128)
        except Exception as e:
            logger.error("[분류 실패] LLM 호출 오류: %s", e, exc_info=True)
            return _FALLBACK

        document_type = str(raw.get("document_type") or "").strip()
        category = str(raw.get("category") or "").strip()

        if document_type not in _ALLOWED_DOCUMENT_TYPES:
            logger.warning("[분류 이상값] document_type=%r → 미분류", document_type)
            document_type = "미분류"

        if category not in _ALLOWED_CATEGORIES:
            logger.warning("[분류 이상값] category=%r → 미분류", category)
            category = "미분류"

        return {"document_type": document_type, "category": category}
