"""
settings/knowledge.py

Knowledge retrieval / context builder 운영 파라미터.
하드코딩을 줄이고 한 곳에서 튜닝 가능하게 유지한다.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K = _int_env("KNOWLEDGE_RETRIEVAL_TOP_K", 3)
KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN = _int_env("KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN", 100)

ANSWER_CONTEXT_PLATFORM_TOP_K = _int_env("ANSWER_CONTEXT_PLATFORM_TOP_K", 3)
ANSWER_CONTEXT_WORKSPACE_TOP_K = _int_env("ANSWER_CONTEXT_WORKSPACE_TOP_K", 3)
ANSWER_CONTEXT_SESSION_TOP_K = _int_env("ANSWER_CONTEXT_SESSION_TOP_K", 1)

ANSWER_CONTEXT_PLATFORM_TEXT_MAX = _int_env("ANSWER_CONTEXT_PLATFORM_TEXT_MAX", 1500)
ANSWER_CONTEXT_WORKSPACE_TEXT_MAX = _int_env("ANSWER_CONTEXT_WORKSPACE_TEXT_MAX", 1500)
ANSWER_CONTEXT_SESSION_TEXT_MAX = _int_env("ANSWER_CONTEXT_SESSION_TEXT_MAX", 3000)
