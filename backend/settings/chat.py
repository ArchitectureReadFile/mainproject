"""
settings/chat.py

Chat 도메인 운영 파라미터.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))
