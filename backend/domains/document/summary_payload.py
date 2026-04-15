"""
services/summary/document_summary_payload_service.py

DocumentSchema -> summary LLM 입력 문자열 조립.

책임:
    - [본문] 섹션 구성
    - [표] 섹션 구성 (table_blocks 없으면 생략)
    - 빈값 처리

비책임:
    - 추출 / normalize
    - truncate / 길이 정책
    - chunk 분할
    - document_type 분류
    - DB 저장
"""

from __future__ import annotations

from domains.document.document_schema import DocumentSchema


class DocumentSummaryPayloadService:
    def build(self, document: DocumentSchema) -> str:
        """DocumentSchema -> LLM 요약 입력 단일 문자열."""
        parts = [f"[본문]\n{document.body_text}"]

        if document.table_blocks:
            table_text = "\n\n".join(tb.text for tb in document.table_blocks)
            parts.append(f"[표]\n{table_text}")

        return "\n\n".join(parts)
