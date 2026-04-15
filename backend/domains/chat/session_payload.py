"""
domains/chat/session_payload.py

DocumentSchema → 세션 저장용 단일 텍스트 조립.

역할:
    - chat 세션 임시 첨부 문서를 저장할 때 쓰는 단일 텍스트를 만든다.
    - [본문] / [표] 구성 + truncate 정책 적용.
    - retrieval/context build와는 별개 경로다.

비책임:
    - 추출 / normalize
    - answer prompt 조립
    - retrieval
    - 요약 payload (→ DocumentSummaryPayloadService)

truncate 정책:
    - body: 6000자
    - tables: 2000자
"""

from __future__ import annotations

from domains.document.document_schema import DocumentSchema
from settings.chat import SESSION_DOCUMENT_BODY_MAX, SESSION_DOCUMENT_TABLE_MAX


class SessionDocumentPayloadService:
    def build(self, document: DocumentSchema) -> str:
        """DocumentSchema → 세션 저장용 단일 텍스트."""
        body = document.body_text[:SESSION_DOCUMENT_BODY_MAX]
        parts = [f"[본문]\n{body}"]

        if document.table_blocks:
            table_text = "\n\n".join(tb.text for tb in document.table_blocks)
            parts.append(f"[표]\n{table_text[:SESSION_DOCUMENT_TABLE_MAX]}")

        return "\n\n".join(parts)
