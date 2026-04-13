"""
models/platform_knowledge.py

Platform Knowledge 3-layer 모델.

━━━ Layer 구조 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Raw    : PlatformRawSource  — 공공 API 원본 보관
  Normal : PlatformDocument   — 서비스가 다루는 공통 문서 단위
  RAG    : PlatformDocumentChunk — BM25 / Qdrant 적재 기준 문서
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

source_type 값:
    "law"            현행 법령
    "precedent"      판례
    "interpretation" 법령해석례
    "admin_rule"     행정규칙

raw_payload / body_text 타입 노트:
    ORM 레벨은 SQLAlchemy 기본 Text를 사용한다.
    SQLite(테스트)에서는 TEXT, MySQL/MariaDB 프로덕션에서는
    Alembic migration에서 LONGTEXT로 ALTER한다.
    sqlalchemy.dialects.mysql.LONGTEXT는 SQLite dialect 컴파일 불가이므로
    ORM 모델에서는 사용하지 않는다.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Raw Layer ─────────────────────────────────────────────────────────────────


class PlatformRawSource(Base):
    """
    공공 API 원본 응답 보관.

    용도:
        - 재정규화 / 재색인 / 출처 검증
        - normalized layer가 실패해도 원본 재처리 가능

    checksum: SHA-256(raw_payload). 동일 external_id 재수집 시 변경 감지 기준.
    status:   "active" | "archived"
    """

    __tablename__ = "platform_raw_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(32), nullable=False)
    provider = Column(String(64), nullable=False)  # "korea_law_open_api"
    api_target = Column(
        String(64), nullable=False
    )  # "eflaw" | "prec" | "expc" | "admrul"
    external_id = Column(String(128), nullable=False)
    raw_format = Column(String(8), nullable=False)  # "json" | "xml"
    raw_payload = Column(Text, nullable=False)
    fetched_at = Column(DateTime, nullable=False)
    checksum = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="active")
    extra_meta = Column(Text, nullable=True)  # JSON 문자열, 선택적 부가 정보

    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    platform_document = relationship(
        "PlatformDocument",
        back_populates="raw_source",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("provider", "api_target", "external_id", name="uq_raw_source"),
        Index("ix_platform_raw_sources_source_type", "source_type"),
        Index("ix_platform_raw_sources_fetched_at", "fetched_at"),
    )


# ── Normalized Layer ──────────────────────────────────────────────────────────


class PlatformDocument(Base):
    """
    서비스가 공통으로 다루는 platform knowledge 문서 단위.

    body_text:
        원문 기반 정규화 텍스트. 요약 아님.
        소비처(chunk builder / summary / chat)가 실제로 읽는 텍스트.

    metadata_json:
        JSON 문자열. source_type별 부가 필드 + 관계 링크.

    status: "active" | "archived"
    """

    __tablename__ = "platform_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(32), nullable=False)
    external_id = Column(String(128), nullable=False)
    raw_source_id = Column(
        Integer,
        ForeignKey("platform_raw_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(512), nullable=True)
    display_title = Column(String(768), nullable=True)
    body_text = Column(Text, nullable=True)
    source_url = Column(String(2048), nullable=True)
    issued_at = Column(DateTime, nullable=True)
    agency = Column(String(255), nullable=True)
    status = Column(String(16), nullable=False, default="active")
    metadata_json = Column(Text, nullable=True)  # JSON 문자열

    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    raw_source = relationship("PlatformRawSource", back_populates="platform_document")
    chunks = relationship(
        "PlatformDocumentChunk",
        back_populates="platform_document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("source_type", "external_id", name="uq_platform_doc"),
        Index("ix_platform_documents_source_type", "source_type"),
        Index("ix_platform_documents_external_id", "external_id"),
        Index("ix_platform_documents_issued_at", "issued_at"),
    )


# ── RAG Layer ─────────────────────────────────────────────────────────────────


class PlatformDocumentChunk(Base):
    """
    Platform RAG 검색용 chunk source of truth.

    chunk_type:
        law:            "article"
        precedent:      "holding" | "summary" | "body" | "meta"
        interpretation: "question" | "answer" | "reason"
        admin_rule:     "rule" | "addendum" | "annex"

    chunk_id_str:
        BM25/Qdrant 저장 시 사용하는 외부 식별자.
        형식: "{source_type}:pd:{platform_document_id}:chunk:{chunk_order}"
    """

    __tablename__ = "platform_document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_document_id = Column(
        Integer,
        ForeignKey("platform_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type = Column(String(32), nullable=False)
    chunk_type = Column(String(32), nullable=True)
    chunk_order = Column(Integer, nullable=False, default=0)
    section_title = Column(String(255), nullable=True)
    chunk_text = Column(Text, nullable=False)
    chunk_id_str = Column(String(256), nullable=True, unique=True)
    metadata_json = Column(Text, nullable=True)  # JSON 문자열

    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    platform_document = relationship("PlatformDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_platform_doc_chunks_source_type", "source_type"),
        Index("ix_platform_doc_chunks_chunk_type", "chunk_type"),
    )


class PlatformSyncRun(Base):
    """
    source_type별 수동 전체 동기화 실행 기록.

    status:
        "queued" | "running" | "success" | "no_changes" | "failed" | "cancelled"
    """

    __tablename__ = "platform_sync_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    finished_at = Column(DateTime, nullable=True)
    fetched_count = Column(Integer, nullable=False, default=0)
    created_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    message = Column(String(512), nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    failures = relationship(
        "PlatformSyncFailure",
        back_populates="sync_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_platform_sync_runs_source_type", "source_type"),
        Index("ix_platform_sync_runs_started_at", "started_at"),
    )


class PlatformSyncFailure(Base):
    """
    platform sync 중 item 단위 실패 추적.

    error_type:
        "fetch_error" | "normalize_error" | "index_error" | "unknown"

    payload_snippet:
        raw_payload의 앞 500자. 디버깅용.
    """

    __tablename__ = "platform_sync_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_run_id = Column(
        Integer,
        ForeignKey("platform_sync_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = Column(String(32), nullable=False)
    external_id = Column(String(128), nullable=True)
    display_title = Column(String(512), nullable=True)
    detail_link = Column(String(2048), nullable=True)
    page = Column(Integer, nullable=True)
    error_type = Column(String(32), nullable=False, default="unknown")
    error_message = Column(String(1024), nullable=True)
    payload_snippet = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utc_now)
    retried_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    sync_run = relationship("PlatformSyncRun", back_populates="failures")

    __table_args__ = (
        Index("ix_platform_sync_failures_sync_run_id", "sync_run_id"),
        Index("ix_platform_sync_failures_source_type", "source_type"),
        Index("ix_platform_sync_failures_created_at", "created_at"),
    )
