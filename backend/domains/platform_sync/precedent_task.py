"""
tasks/precedent_task.py

판례 임베딩 Celery task.
판례 등록/재처리 성공 후 백그라운드에서 벡터화 → Qdrant + BM25 저장.

━━━ Source of Truth / Fallback 계층 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1순위 원문:   detail_text   (taxlaw HTML 상세내용. 섹션 분리 정밀도 최고)
  2순위 fallback: precedent.text  (gist + detail_text 합본. 재인덱싱 경로 전용)
                  → index_precedent(detail_text=None) 시 자동 사용
                  → 섹션 분리 정밀도 낮지만 허용 가능
  메타 보강:    metadata_parser.parse_text(precedent.text)
                  → court_name / case_number 등 detail_table에 없는 값 보강
                  → 주 source 아님, 보조 fallback 역할
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging

from celery_app import celery_app
from database import SessionLocal
from domains.precedent.chunk_builder import (
    build_chunks_from_precedent_document,
    build_precedent_document,
)
from domains.precedent.metadata_parser import OptionalPrecedentMetadataParser
from domains.rag import bm25_store, vector_store
from domains.rag.embedding_service import embed_passage
from extractors.taxlaw_precedent import fetch_taxlaw_precedent
from models.model import DocumentStatus, Precedent

logger = logging.getLogger(__name__)
_metadata_parser = OptionalPrecedentMetadataParser()


def _resolve_precedent_title(raw_title: str | None, parsed_meta: dict) -> str | None:
    if raw_title and str(raw_title).strip():
        return str(raw_title).strip()

    case_number = parsed_meta.get("case_number")
    case_name = parsed_meta.get("case_name")
    court_name = parsed_meta.get("court_name")

    if case_number and case_name:
        return f"{case_number} {case_name}"
    if court_name and case_number:
        return f"{court_name} {case_number}"
    if case_name:
        return case_name
    if case_number:
        return case_number
    return raw_title


def _drop_stale_index(precedent_id: int) -> None:
    try:
        vector_store.delete(precedent_id)
        bm25_store.delete(precedent_id)
        logger.info("stale 인덱스 제거: precedent_id=%s", precedent_id)
    except Exception as exc:
        logger.error(
            "stale 인덱스 제거 실패: precedent_id=%s, error=%s", precedent_id, exc
        )


@celery_app.task(
    bind=True,
    name="tasks.precedent_task.process_next_pending_precedent",
)
def process_next_pending_precedent(self) -> dict:
    db = SessionLocal()
    claimed_precedent_id = None
    try:
        precedent = (
            db.query(Precedent)
            .filter(Precedent.processing_status == DocumentStatus.PENDING)
            .order_by(Precedent.created_at.asc(), Precedent.id.asc())
            .first()
        )
        if not precedent:
            logger.info("[precedent 태스크 종료] 처리할 PENDING 판례가 없습니다.")
            return {"status": "idle"}

        precedent.processing_status = DocumentStatus.PROCESSING
        db.commit()
        db.refresh(precedent)
        claimed_precedent_id = precedent.id

        extract_result: dict = {}
        try:
            extract_result = fetch_taxlaw_precedent(precedent.source_url)
            precedent.title = extract_result.get("title") or None
            # precedent.text: 하위호환 합본 저장 (gist + detail_text).
            # 주 원문은 detail_text이며, 이 컬럼은 재인덱싱 fallback 전용이다.
            precedent.text = extract_result.get("text") or None

            if not precedent.text:
                precedent.processing_status = DocumentStatus.FAILED
                precedent.error_message = "본문 텍스트를 추출할 수 없습니다."
                _drop_stale_index(precedent.id)
            else:
                parsed_meta = _metadata_parser.parse_text(precedent.text)
                precedent.title = _resolve_precedent_title(precedent.title, parsed_meta)
                precedent.processing_status = DocumentStatus.DONE
                precedent.error_message = None
        except Exception as exc:
            logger.error("판례 추출 실패: id=%s, error=%s", precedent.id, exc)
            precedent.processing_status = DocumentStatus.FAILED
            precedent.error_message = str(exc)
            _drop_stale_index(precedent.id)

        db.commit()
        db.refresh(precedent)

        if precedent.processing_status == DocumentStatus.DONE:
            # detail_text / detail_table / gist를 그대로 전달 — 1순위 원문 경로
            index_precedent.delay(
                precedent.id,
                gist=extract_result.get("gist"),
                detail_table=extract_result.get("detail_table"),
                detail_text=extract_result.get("detail_text"),
            )

        return {
            "status": precedent.processing_status.value.lower(),
            "precedent_id": precedent.id,
        }
    finally:
        db.close()
        if claimed_precedent_id is not None:
            process_next_pending_precedent.delay()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.precedent_task.index_precedent",
)
def index_precedent(
    self,
    precedent_id: int,
    gist: str | None = None,
    detail_table: dict | None = None,
    detail_text: str | None = None,
) -> dict:
    """
    판례 chunk를 벡터화해 Qdrant + BM25에 저장한다.

    원문 우선순위:
        detail_text (1순위): taxlaw HTML 원문. 섹션 분리 정밀도 최고.
        precedent.text (fallback): gist + detail_text 합본.
            admin reindex_precedents()가 detail_text 없이 호출할 때만 사용.
            섹션 분리 정밀도가 낮지만 재인덱싱 경로에서 허용 가능한 수준.

    메타 보강:
        metadata_parser.parse_text(precedent.text)로 court_name / case_number를
        보강한다. detail_table이 있으면 detail_table 값이 우선 적용된다.
    """
    db = SessionLocal()
    try:
        precedent = db.query(Precedent).filter(Precedent.id == precedent_id).first()
        if not precedent:
            logger.warning("index_precedent: precedent_id=%s 없음", precedent_id)
            return {"status": "skip", "reason": "not found"}

        if precedent.processing_status != DocumentStatus.DONE:
            logger.warning(
                "index_precedent: precedent_id=%s status=%s, 스킵",
                precedent_id,
                precedent.processing_status,
            )
            return {"status": "skip", "reason": "not DONE"}

        if not precedent.text:
            logger.warning("index_precedent: precedent_id=%s text 없음", precedent_id)
            return {"status": "skip", "reason": "empty text"}

        _drop_stale_index(precedent_id)

        # detail_text 없으면 합본 text로 fallback (재인덱싱 경로)
        effective_detail_text = detail_text or precedent.text
        if not detail_text:
            logger.info(
                "index_precedent: detail_text 없음, precedent.text fallback 사용 "
                "(재인덱싱 경로): precedent_id=%s",
                precedent_id,
            )

        precedent_doc = build_precedent_document(
            precedent_id=precedent.id,
            source_url=precedent.source_url or "",
            title=precedent.title,
            gist=gist,
            detail_table=detail_table,
            detail_text=effective_detail_text,
        )

        chunks = build_chunks_from_precedent_document(precedent_doc)
        if not chunks:
            logger.warning("index_precedent: chunk 없음 precedent_id=%s", precedent_id)
            return {"status": "skip", "reason": "no chunks"}

        # metadata_parser: court_name / case_number 보조 fallback
        # detail_table 값이 있으면 chunk 단계에서 이미 반영되므로
        # 여기서는 None인 필드만 채운다.
        parsed_meta = _metadata_parser.parse_text(precedent.text)

        logger.info(
            "임베딩 시작: precedent_id=%s, chunks=%d", precedent_id, len(chunks)
        )

        for chunk in chunks:
            vector = embed_passage(chunk["text"])
            vector_store.upsert(
                chunk_id=chunk["chunk_id"],
                embedding=vector,
                payload={
                    **chunk,
                    # chunk에 값이 있으면 유지, 없으면 metadata_parser 보강값 사용
                    "court_name": chunk.get("court_name")
                    or parsed_meta.get("court_name"),
                    "case_number": chunk.get("case_number")
                    or parsed_meta.get("case_number"),
                    "judgment_date": (
                        chunk.get("judgment_date")
                        or str(parsed_meta.get("judgment_date") or "")
                        or None
                    ),
                },
            )
            bm25_store.upsert(
                chunk_id=chunk["chunk_id"],
                precedent_id=precedent.id,
                text=chunk["text"],
            )

        logger.info(
            "임베딩 완료: precedent_id=%s, chunks=%d", precedent_id, len(chunks)
        )
        return {"status": "ok", "precedent_id": precedent_id, "chunks": len(chunks)}

    except Exception as exc:
        logger.error("임베딩 실패: precedent_id=%s, error=%s", precedent_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="tasks.precedent_task.delete_precedent_index")
def delete_precedent_index(precedent_id: int) -> dict:
    """Qdrant + BM25 인덱스에서 판례 chunk 전체를 삭제한다."""
    try:
        vector_store.delete(precedent_id)
        bm25_store.delete(precedent_id)
        return {"status": "ok", "precedent_id": precedent_id}
    except Exception as exc:
        logger.error("인덱스 삭제 실패: precedent_id=%s, error=%s", precedent_id, exc)
        return {"status": "error", "reason": str(exc)}
