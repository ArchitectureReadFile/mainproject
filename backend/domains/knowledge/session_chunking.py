"""
domains/knowledge/session_chunking.py

세션 첨부 문서의 chunk 분할/랭킹 공통 로직.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from settings.knowledge import (
    SESSION_RETRIEVAL_CHUNK_MAX_CHARS,
    SESSION_RETRIEVAL_CHUNK_OVERLAP,
    SESSION_RETRIEVAL_CHUNK_TARGET_CHARS,
)

_BLANK_LINE_RE = re.compile(r"\n{2,}")
_TERM_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")


@dataclass(frozen=True)
class SessionTextChunk:
    chunk_order: int
    chunk_text: str
    chunk_id: int | None = None


def split_session_text(text: str) -> list[SessionTextChunk]:
    paragraphs = [p.strip() for p in _BLANK_LINE_RE.split(text) if p.strip()]
    if not paragraphs:
        stripped = text.strip()
        return (
            [SessionTextChunk(chunk_order=0, chunk_text=stripped)] if stripped else []
        )

    chunks: list[str] = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > SESSION_RETRIEVAL_CHUNK_MAX_CHARS:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_split_long_text(paragraph))
            continue

        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= SESSION_RETRIEVAL_CHUNK_TARGET_CHARS:
            buffer = candidate
            continue

        if buffer:
            chunks.append(buffer)
        buffer = paragraph

    if buffer:
        chunks.append(buffer)

    return [
        SessionTextChunk(chunk_order=idx, chunk_text=chunk_text)
        for idx, chunk_text in enumerate(chunks)
    ]


def rank_session_chunks(
    query: str,
    chunks: Sequence[SessionTextChunk],
) -> list[tuple[SessionTextChunk, float]]:
    query_terms = _extract_terms(query)
    ranked = [
        (chunk, _score_chunk(query_terms, chunk.chunk_text, chunk.chunk_order))
        for chunk in chunks
    ]
    return sorted(ranked, key=lambda x: x[1], reverse=True)


def _split_long_text(text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + SESSION_RETRIEVAL_CHUNK_MAX_CHARS)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - SESSION_RETRIEVAL_CHUNK_OVERLAP, start + 1)
    return chunks


def _extract_terms(text: str) -> list[str]:
    seen: set[str] = set()
    ordered_terms: list[str] = []
    for raw in _TERM_RE.findall(text.lower()):
        if raw not in seen:
            seen.add(raw)
            ordered_terms.append(raw)
    return ordered_terms


def _score_chunk(query_terms: list[str], chunk_text: str, order_index: int) -> float:
    if not query_terms:
        return max(0.0, 0.2 - (order_index * 0.001))

    lowered = chunk_text.lower()
    matched = sum(1 for term in query_terms if term in lowered)
    ratio = matched / len(query_terms)
    order_bonus = max(0.0, 0.05 - (order_index * 0.001))
    return ratio + order_bonus
