"""
settings/chat.py

Chat 도메인 운영 파라미터.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


SESSION_DOCUMENT_BODY_MAX = _int_env("SESSION_DOCUMENT_BODY_MAX", 6000)
SESSION_DOCUMENT_TABLE_MAX = _int_env("SESSION_DOCUMENT_TABLE_MAX", 2000)
