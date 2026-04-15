"""
domains/admin/platform_service.py

어드민 공공 데이터 source 전체 최신화 서비스.

정책:
    - source_type별 목록 API를 page 순회
    - source_type + external_id 기준 create_only
    - Celery task에서 long-running sync를 수행
    - PlatformSyncRun + metadata_json에 진행 상태를 누적 저장
    - item 단위 실패는 PlatformSyncFailure에 별도 저장

실패 분류 (error_type):
    fetch_error     detail_link 추출 실패 / 상세 API 호출 실패
    normalize_error normalize / chunk 생성 실패 (PlatformNormalizeError)
    index_error     DB/BM25/Qdrant 저장 단계에서 발생한 실패

precedent 정책:
    - 목록 item을 기준으로 list_only 기본 문서를 먼저 만든다.
    - 상세 조회가 성공하면 같은 external_id 문서를 enrich 한다.
    - unsupported detail은 failure가 아니라 list_only 유지 경로로 처리한다.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from domains.admin.schemas import (
    AdminPlatformFailureItem,
    AdminPlatformFailuresResponse,
    AdminPlatformRecentItem,
    AdminPlatformSourceSummary,
    AdminPlatformStopResponse,
    AdminPlatformSummaryResponse,
    AdminPlatformSyncResponse,
)
from domains.platform_sync.korea_law_open_api_client import (
    KoreaLawOpenApiClient,
    UnsupportedDetailError,
)
from domains.platform_sync.platform_knowledge_ingestion_service import (
    PlatformKnowledgeIngestionService,
    PlatformNormalizeError,
)
from models.platform_knowledge import (
    PlatformDocument,
    PlatformDocumentChunk,
    PlatformSyncFailure,
    PlatformSyncRun,
)
from settings.platform import KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE

logger = logging.getLogger(__name__)

_SOURCE_LABEL_MAP = {
    "law": "현행 법령",
    "precedent": "판례",
    "interpretation": "법령해석례",
    "admin_rule": "행정규칙",
}

_RUNNING_STATUSES = {"queued", "running"}

_PAYLOAD_SNIPPET_MAX = 500


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load_run_meta(run: PlatformSyncRun | None) -> dict:
    if run is None or not run.metadata_json:
        return {}
    try:
        data = json.loads(run.metadata_json)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _dump_run_meta(run: PlatformSyncRun, meta: dict) -> None:
    run.metadata_json = json.dumps(meta, ensure_ascii=False)


def _load_document_meta(doc: PlatformDocument | None) -> dict:
    if doc is None or not doc.metadata_json:
        return {}
    try:
        data = json.loads(doc.metadata_json)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _build_run_message(*, counts: dict[str, int], page: int | None = None) -> str:
    prefix = f"{page}페이지 처리 중 · " if page else ""
    return (
        f"{prefix}조회 {counts['fetched']}건 · 신규 {counts['created']}건 · "
        f"스킵 {counts['skipped']}건 · 실패 {counts['failed']}건"
    )


def _serialize_run(run: PlatformSyncRun) -> AdminPlatformSyncResponse:
    return AdminPlatformSyncResponse(
        run_id=run.id,
        source_type=run.source_type,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        fetched=run.fetched_count,
        created=run.created_count,
        skipped=run.skipped_count,
        failed=run.failed_count,
        message=run.message or "",
    )


def _latest_runs_by_source(db: Session) -> dict[str, PlatformSyncRun]:
    latest_run_subquery = (
        db.query(
            PlatformSyncRun.source_type,
            func.max(PlatformSyncRun.started_at).label("max_started_at"),
        )
        .group_by(PlatformSyncRun.source_type)
        .subquery()
    )

    latest_runs = (
        db.query(PlatformSyncRun)
        .join(
            latest_run_subquery,
            (PlatformSyncRun.source_type == latest_run_subquery.c.source_type)
            & (PlatformSyncRun.started_at == latest_run_subquery.c.max_started_at),
        )
        .all()
    )
    return {run.source_type: run for run in latest_runs}


def _snippet(obj: object) -> str | None:
    """dict 또는 임의 객체를 JSON 직렬화 후 앞 500자로 잘라 반환한다."""
    if obj is None:
        return None
    try:
        return json.dumps(obj, ensure_ascii=False)[:_PAYLOAD_SNIPPET_MAX]
    except Exception:
        return str(obj)[:_PAYLOAD_SNIPPET_MAX]


def _save_failure(
    db: Session,
    *,
    run: PlatformSyncRun,
    external_id: str | None,
    display_title: str | None,
    detail_link: str | None,
    page: int | None,
    error_type: str,
    exc: Exception,
    snippet_obj: object = None,
) -> None:
    """PlatformSyncFailure row를 추가한다. 호출측에서 commit해야 한다."""
    failure = PlatformSyncFailure(
        sync_run_id=run.id,
        source_type=run.source_type,
        external_id=external_id,
        display_title=display_title,
        detail_link=detail_link,
        page=page,
        error_type=error_type,
        error_message=str(exc)[:1024],
        payload_snippet=_snippet(snippet_obj),
    )
    db.add(failure)


def get_admin_platform_summary(db: Session) -> AdminPlatformSummaryResponse:
    doc_rows = (
        db.query(PlatformDocument.source_type, func.count(PlatformDocument.id))
        .group_by(PlatformDocument.source_type)
        .all()
    )
    chunk_rows = (
        db.query(
            PlatformDocumentChunk.source_type, func.count(PlatformDocumentChunk.id)
        )
        .group_by(PlatformDocumentChunk.source_type)
        .all()
    )

    doc_map = {source_type: count for source_type, count in doc_rows}
    chunk_map = {source_type: count for source_type, count in chunk_rows}
    run_map = _latest_runs_by_source(db)

    sources = []
    for source_type, label in _SOURCE_LABEL_MAP.items():
        run = run_map.get(source_type)
        meta = _load_run_meta(run)
        sources.append(
            AdminPlatformSourceSummary(
                source_type=source_type,
                label=label,
                document_count=doc_map.get(source_type, 0),
                chunk_count=chunk_map.get(source_type, 0),
                last_synced_at=run.finished_at if run else None,
                last_sync_status=run.status if run else None,
                last_sync_message=run.message if run else None,
                fetched_count=run.fetched_count if run else 0,
                created_count=run.created_count if run else 0,
                skipped_count=run.skipped_count if run else 0,
                failed_count=run.failed_count if run else 0,
                current_page=meta.get("current_page"),
                total_count=meta.get("total_count"),
                last_external_id=meta.get("last_external_id"),
                last_display_title=meta.get("last_display_title"),
            )
        )

    recent_docs = (
        db.query(PlatformDocument)
        .order_by(PlatformDocument.updated_at.desc())
        .limit(10)
        .all()
    )

    return AdminPlatformSummaryResponse(
        total_documents=sum(doc_map.values()),
        total_chunks=sum(chunk_map.values()),
        sources=sources,
        recent_items=[
            AdminPlatformRecentItem.model_validate(doc) for doc in recent_docs
        ],
    )


def get_admin_platform_failures(
    db: Session,
    *,
    source_type: str | None = None,
    run_id: int | None = None,
    limit: int = 20,
) -> AdminPlatformFailuresResponse:
    query = db.query(PlatformSyncFailure)
    if source_type:
        query = query.filter(PlatformSyncFailure.source_type == source_type)
    if run_id is not None:
        query = query.filter(PlatformSyncFailure.sync_run_id == run_id)
    total = query.count()
    items = query.order_by(PlatformSyncFailure.created_at.desc()).limit(limit).all()
    return AdminPlatformFailuresResponse(
        items=[AdminPlatformFailureItem.model_validate(f) for f in items],
        total=total,
    )


def enqueue_platform_source_sync(
    db: Session,
    *,
    source_type: str,
) -> AdminPlatformSyncResponse:
    existing_run = (
        db.query(PlatformSyncRun)
        .filter(
            PlatformSyncRun.source_type == source_type,
            PlatformSyncRun.status.in_(_RUNNING_STATUSES),
        )
        .order_by(PlatformSyncRun.started_at.desc())
        .first()
    )
    if existing_run:
        return _serialize_run(existing_run)

    run = PlatformSyncRun(
        source_type=source_type,
        status="queued",
        started_at=_utc_now(),
        message="동기화 대기 중입니다.",
        fetched_count=0,
        created_count=0,
        skipped_count=0,
        failed_count=0,
    )
    _dump_run_meta(
        run,
        {
            "current_page": 0,
            "total_count": None,
            "last_external_id": None,
            "last_display_title": None,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    from domains.platform_sync.sync_task import run_platform_source_sync

    task = run_platform_source_sync.delay(run.id)

    meta = _load_run_meta(run)
    meta["task_id"] = task.id
    _dump_run_meta(run, meta)
    db.commit()
    db.refresh(run)

    return _serialize_run(run)


def stop_platform_source_sync(
    db: Session,
    *,
    source_type: str,
) -> AdminPlatformStopResponse:
    run = (
        db.query(PlatformSyncRun)
        .filter(
            PlatformSyncRun.source_type == source_type,
            PlatformSyncRun.status.in_(_RUNNING_STATUSES),
        )
        .order_by(PlatformSyncRun.started_at.desc())
        .first()
    )
    if run is None:
        return AdminPlatformStopResponse(
            run_id=-1,
            source_type=source_type,
            status="not_found",
            message="진행 중인 작업이 없습니다.",
        )

    # Celery task revoke
    meta = _load_run_meta(run)
    task_id = meta.get("task_id")
    if task_id:
        try:
            from celery_app import celery_app

            celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    run.status = "cancelled"
    run.finished_at = _utc_now()
    run.message = "중지됨"
    db.commit()

    return AdminPlatformStopResponse(
        run_id=run.id,
        source_type=source_type,
        status="cancelled",
        message="중지됨",
    )


def _update_run_progress(
    db: Session,
    run: PlatformSyncRun,
    *,
    counts: dict[str, int],
    current_page: int,
    total_count: int | None,
    last_external_id: str | None = None,
    last_display_title: str | None = None,
    message: str | None = None,
) -> None:
    # cancelled 상태는 덮어쓰지 않는다
    if run.status == "cancelled":
        return

    run.fetched_count = counts["fetched"]
    run.created_count = counts["created"]
    run.skipped_count = counts["skipped"]
    run.failed_count = counts["failed"]
    run.status = "running"
    run.message = message or _build_run_message(counts=counts, page=current_page)

    meta = _load_run_meta(run)
    meta.update(
        {
            "current_page": current_page,
            "total_count": total_count,
            "last_external_id": last_external_id,
            "last_display_title": last_display_title,
        }
    )
    _dump_run_meta(run, meta)
    db.commit()
    db.refresh(run)


def _record_item_failure(
    db: Session,
    run_id: int,
    *,
    external_id: str | None,
    display_title: str | None,
    detail_link: str | None,
    page: int,
    error_type: str,
    exc: Exception,
    snippet_obj: object = None,
) -> PlatformSyncRun | None:
    """
    실패를 PlatformSyncFailure에 기록하고 최신 run을 반환한다.
    cancelled이거나 run이 없으면 None 반환 (호출측에서 즉시 return).
    """
    db.rollback()
    run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
    if run is None or run.status == "cancelled":
        return None

    _save_failure(
        db,
        run=run,
        external_id=external_id,
        display_title=display_title,
        detail_link=detail_link,
        page=page,
        error_type=error_type,
        exc=exc,
        snippet_obj=snippet_obj,
    )
    db.commit()
    return run


def execute_platform_source_sync(run_id: int) -> None:
    db = SessionLocal()
    client = KoreaLawOpenApiClient()
    ingestion_service = PlatformKnowledgeIngestionService()

    try:
        run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
        if run is None:
            return

        # task 시작 직후 — cancelled 체크 (stop이 enqueue 직후 호출된 경우)
        if run.status == "cancelled":
            return

        counts = defaultdict(int)
        counts.update(
            {
                "fetched": run.fetched_count,
                "created": run.created_count,
                "skipped": run.skipped_count,
                "failed": run.failed_count,
            }
        )

        # queued → running 전환 전 재확인
        run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
        if run is None or run.status == "cancelled":
            return

        run.status = "running"
        run.message = "동기화 작업을 시작했습니다."
        meta = _load_run_meta(run)
        meta.setdefault("current_page", 0)
        meta.setdefault("total_count", None)
        meta.setdefault("last_external_id", None)
        meta.setdefault("last_display_title", None)
        _dump_run_meta(run, meta)
        db.commit()
        db.refresh(run)

        page = 1
        total_count = None
        seen_external_ids: set[str] = set()

        while True:
            # cancelled 체크 — 페이지 루프 진입 전
            run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
            if run is None or run.status == "cancelled":
                return

            items, page_total_count = client.search_page(
                source_type=run.source_type,
                page=page,
                display=KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE,
            )

            if total_count is None:
                total_count = page_total_count

            if not items:
                break

            for item in items:
                # cancelled 체크 — 아이템 루프 내
                run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
                if run is None or run.status == "cancelled":
                    return

                external_id = client.extract_external_id(run.source_type, item)
                display_title = client.extract_display_title(run.source_type, item)

                # ── external_id 추출 실패 ─────────────────────────────────
                if not external_id:
                    counts["failed"] += 1
                    run = _record_item_failure(
                        db,
                        run_id,
                        external_id=None,
                        display_title=display_title,
                        detail_link=None,
                        page=page,
                        error_type="fetch_error",
                        exc=ValueError("external_id 추출 실패"),
                        snippet_obj=item if isinstance(item, dict) else None,
                    )
                    if run is None:
                        return
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_display_title=display_title,
                    )
                    continue

                if external_id in seen_external_ids:
                    continue

                seen_external_ids.add(external_id)
                counts["fetched"] += 1

                existing = (
                    db.query(PlatformDocument)
                    .filter_by(source_type=run.source_type, external_id=external_id)
                    .first()
                )
                existing_meta = _load_document_meta(existing)
                existing_detail_mode = existing_meta.get("detail_mode")

                if run.source_type != "precedent" and existing:
                    counts["skipped"] += 1
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_external_id=external_id,
                        last_display_title=existing.display_title or display_title,
                    )
                    continue

                created_list_only = False

                if run.source_type == "precedent":
                    if existing and existing_detail_mode == "enriched":
                        counts["skipped"] += 1
                        _update_run_progress(
                            db,
                            run,
                            counts=counts,
                            current_page=page,
                            total_count=total_count,
                            last_external_id=external_id,
                            last_display_title=existing.display_title or display_title,
                        )
                        continue

                    if existing is None:
                        try:
                            ingestion_service.ingest_list_only(
                                db,
                                source_type="precedent",
                                external_id=external_id,
                                list_item=item,
                                data_source_name=str(
                                    item.get("데이터출처명") or ""
                                ).strip()
                                or None,
                            )
                            db.commit()
                            counts["created"] += 1
                            created_list_only = True
                        except PlatformNormalizeError as exc:
                            counts["failed"] += 1
                            run = _record_item_failure(
                                db,
                                run_id,
                                external_id=external_id,
                                display_title=display_title,
                                detail_link=None,
                                page=page,
                                error_type="normalize_error",
                                exc=exc,
                                snippet_obj=item if isinstance(item, dict) else None,
                            )
                            if run is None:
                                return
                            _update_run_progress(
                                db,
                                run,
                                counts=counts,
                                current_page=page,
                                total_count=total_count,
                                last_external_id=external_id,
                                last_display_title=display_title,
                            )
                            continue
                        except Exception as exc:
                            counts["failed"] += 1
                            run = _record_item_failure(
                                db,
                                run_id,
                                external_id=external_id,
                                display_title=display_title,
                                detail_link=None,
                                page=page,
                                error_type="index_error",
                                exc=exc,
                                snippet_obj=item if isinstance(item, dict) else None,
                            )
                            if run is None:
                                return
                            _update_run_progress(
                                db,
                                run,
                                counts=counts,
                                current_page=page,
                                total_count=total_count,
                                last_external_id=external_id,
                                last_display_title=display_title,
                            )
                            continue

                detail_link: str | None = None
                raw_payload: dict | None = None

                # ── Step A: detail_link 추출 ──────────────────────────────
                try:
                    detail_link = client.extract_detail_link(run.source_type, item)
                except Exception as exc:
                    if run.source_type == "precedent":
                        if not created_list_only:
                            counts["skipped"] += 1
                        _update_run_progress(
                            db,
                            run,
                            counts=counts,
                            current_page=page,
                            total_count=total_count,
                            last_external_id=external_id,
                            last_display_title=display_title,
                        )
                        continue
                    counts["failed"] += 1
                    run = _record_item_failure(
                        db,
                        run_id,
                        external_id=external_id,
                        display_title=display_title,
                        detail_link=None,
                        page=page,
                        error_type="fetch_error",
                        exc=exc,
                        snippet_obj=item if isinstance(item, dict) else None,
                    )
                    if run is None:
                        return
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_external_id=external_id,
                        last_display_title=display_title,
                    )
                    continue

                # ── Step B: 상세 API 호출 ─────────────────────────────────
                try:
                    raw_payload = client.fetch_detail_from_link(
                        run.source_type, detail_link
                    )
                except UnsupportedDetailError:
                    if run.source_type == "precedent":
                        if not created_list_only:
                            counts["skipped"] += 1
                        _update_run_progress(
                            db,
                            run,
                            counts=counts,
                            current_page=page,
                            total_count=total_count,
                            last_external_id=external_id,
                            last_display_title=display_title,
                        )
                        continue
                    counts["failed"] += 1
                    run = _record_item_failure(
                        db,
                        run_id,
                        external_id=external_id,
                        display_title=display_title,
                        detail_link=detail_link,
                        page=page,
                        error_type="fetch_error",
                        exc=ValueError("unsupported detail 응답"),
                        snippet_obj=item if isinstance(item, dict) else None,
                    )
                    if run is None:
                        return
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_external_id=external_id,
                        last_display_title=display_title,
                    )
                    continue
                except Exception as exc:
                    counts["failed"] += 1
                    run = _record_item_failure(
                        db,
                        run_id,
                        external_id=external_id,
                        display_title=display_title,
                        detail_link=detail_link,
                        page=page,
                        error_type="fetch_error",
                        exc=exc,
                        snippet_obj=item if isinstance(item, dict) else None,
                    )
                    if run is None:
                        return
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_external_id=external_id,
                        last_display_title=display_title,
                    )
                    continue

                # ── Step C: ingest (normalize + index) ───────────────────
                try:
                    ingestion_service.ingest_from_payload(
                        db,
                        source_type=run.source_type,
                        external_id=external_id,
                        raw_payload=raw_payload,
                        raw_format="json",
                    )
                    db.commit()
                    if created_list_only:
                        # same external_id 문서를 list_only → enriched로 보강한 경우
                        pass
                    elif run.source_type == "precedent" and existing is not None:
                        counts["skipped"] += 1
                    else:
                        counts["created"] += 1
                except PlatformNormalizeError as exc:
                    counts["failed"] += 1
                    run = _record_item_failure(
                        db,
                        run_id,
                        external_id=external_id,
                        display_title=display_title,
                        detail_link=detail_link,
                        page=page,
                        error_type="normalize_error",
                        exc=exc,
                        snippet_obj=raw_payload,
                    )
                    if run is None:
                        return
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_external_id=external_id,
                        last_display_title=display_title,
                    )
                    continue
                except Exception as exc:
                    counts["failed"] += 1
                    # normalize 이후 indexing 단계 실패로 간주
                    run = _record_item_failure(
                        db,
                        run_id,
                        external_id=external_id,
                        display_title=display_title,
                        detail_link=detail_link,
                        page=page,
                        error_type="index_error",
                        exc=exc,
                        snippet_obj=raw_payload,
                    )
                    if run is None:
                        return
                    _update_run_progress(
                        db,
                        run,
                        counts=counts,
                        current_page=page,
                        total_count=total_count,
                        last_external_id=external_id,
                        last_display_title=display_title,
                    )
                    continue

                # ── progress update (성공 경로) ───────────────────────────
                run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
                if run is None or run.status == "cancelled":
                    return
                _update_run_progress(
                    db,
                    run,
                    counts=counts,
                    current_page=page,
                    total_count=total_count,
                    last_external_id=external_id,
                    last_display_title=display_title,
                )

            if len(items) < KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE:
                break
            if total_count and counts["fetched"] >= total_count:
                break

            page += 1

        run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
        if run is None or run.status == "cancelled":
            return

        run.fetched_count = counts["fetched"]
        run.created_count = counts["created"]
        run.skipped_count = counts["skipped"]
        run.failed_count = counts["failed"]
        run.finished_at = _utc_now()

        meta = _load_run_meta(run)
        meta["current_page"] = page
        meta["total_count"] = total_count
        _dump_run_meta(run, meta)

        if counts["failed"] and not counts["created"] and not counts["skipped"]:
            run.status = "failed"
            run.message = "동기화 중 오류가 발생했습니다."
        elif counts["created"] == 0 and counts["failed"] == 0:
            run.status = "no_changes"
            run.message = "이미 최신 상태입니다."
        else:
            run.status = "success"
            run.message = f"신규 {counts['created']}건, 스킵 {counts['skipped']}건, 실패 {counts['failed']}건"

        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.query(PlatformSyncRun).filter_by(id=run_id).first()
        if run and run.status != "cancelled":
            run.status = "failed"
            run.finished_at = _utc_now()
            run.failed_count = max(run.failed_count, 1)
            run.message = str(exc)
            db.commit()
        raise
    finally:
        db.close()
