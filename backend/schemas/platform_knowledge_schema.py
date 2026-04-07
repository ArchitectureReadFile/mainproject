"""
schemas/platform_knowledge_schema.py

Platform Knowledge ingestion 전용 공통 계약.

━━━ 왜 DocumentSchema와 분리하는가 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DocumentSchema:         PDF/OCR 기반 업로드 문서. raw_markdown / raw_json / raw_text.
  PlatformDocumentSchema: 공공 API 기반 법률 문서. source_type 기반 정규화 결과.

  원천 구조가 다르므로 억지 통합하지 않는다.
  단, retrieval 결과로 올라갈 때는 기존 RetrievedKnowledgeItem으로 합쳐진다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

source_type 값:
    "law"            현행 법령
    "precedent"      판례
    "interpretation" 법령해석례
    "admin_rule"     행정규칙

chunk_type 값:
    law:            "article"
    precedent:      "holding" | "summary" | "body" | "meta"
    interpretation: "question" | "answer" | "reason"
    admin_rule:     "rule" | "addendum" | "annex"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PlatformDocumentSchema:
    """
    공공 API 원본 → 정규화 후 서비스가 다루는 공통 문서 단위.

    source_type:   "law" | "precedent" | "interpretation" | "admin_rule"
    external_id:   공공 API 원본 고유 식별자
    title:         원본 문서 제목
    display_title: 서비스 노출용 제목 (title + 약칭/번호 포함)
    body_text:     원문 기반 정규화 전문 (요약 아님)
    issued_at:     시행일 / 선고일 / 회신일 / 발령일 등 source_type별 기준일
    agency:        소관부처 / 법원명 / 회신기관 / 소관기관
    metadata:      source_type별 고유 부가 정보 + 관계 링크 딕셔너리

    metadata 권장 공통 필드:
        topic_tags                list[str]
        issue_tags                list[str]
        related_law_refs          list[str]
        related_case_refs         list[str]
        related_interpretation_refs list[str]

    metadata source_type별 권장 필드:
        law:
            promulgation_date     str
            promulgation_no       str
            law_name_short        str
        precedent:
            case_no               str
            case_type             str
            judgment_type         str
            detail_mode           "list_only" | "enriched"
        interpretation:
            agenda_no             str
            query_org             str
            responder_name        str
        admin_rule:
            rule_no               str
            effective_date        str
            promulgation_date     str

    raw_payload_ref:
        PlatformRawSource.id. normalize 후 역추적 기준.
        None 허용 (raw 저장 없이 직접 정규화 경로에서 사용 가능).
    """

    source_type: str
    external_id: str
    title: str | None
    body_text: str
    display_title: str | None = None
    source_url: str | None = None
    issued_at: datetime | None = None
    agency: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload_ref: int | None = None  # PlatformRawSource.id


@dataclass
class PlatformChunkSchema:
    """
    PlatformDocumentSchema → BM25 / Qdrant 적재 단위.

    source_type:   부모 문서와 동일
    external_id:   부모 문서와 동일 (chunk_id_str 생성 기준)
    chunk_type:    "article" | "holding" | "summary" | "body" | "meta"
                   | "question" | "answer" | "reason"
                   | "rule" | "addendum" | "annex"
    chunk_order:   문서 내 순서 (0-indexed)
    section_title: 섹션명 (조문제목 / 판시사항 / 질의요지 / 부칙 / 별표 등)
    chunk_text:    retrieval 및 answer context에 들어갈 실제 텍스트
    metadata:      chunk 단위 부가 정보

    metadata 권장 필드:
        article_no        str    (law, admin_rule)
        related_law_refs  list[str]
        related_case_refs list[str]
        source_url        str
        issued_at         str
        agency            str
    """

    source_type: str
    external_id: str
    chunk_type: str
    chunk_order: int
    chunk_text: str
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
