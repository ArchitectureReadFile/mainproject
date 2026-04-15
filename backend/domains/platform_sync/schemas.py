"""
domains/platform_sync/schemas.py

Platform Knowledge ingestion 전용 공통 계약.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PlatformDocumentSchema:
    source_type: str
    external_id: str
    title: str | None
    body_text: str
    display_title: str | None = None
    source_url: str | None = None
    issued_at: datetime | None = None
    agency: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload_ref: int | None = None


@dataclass
class PlatformChunkSchema:
    source_type: str
    external_id: str
    chunk_type: str
    chunk_order: int
    chunk_text: str
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
