import logging
import os
import re
import sys
import zipfile
from datetime import timedelta

sys.path.insert(0, "/app")

from celery_app import celery_app
from database import SessionLocal
from domains.export.repository import ExportRepository
from errors import ErrorCode, FailureStage, build_failure_payload
from models.model import DocumentLifecycleStatus, ExportJobStatus, utc_now_naive

logger = logging.getLogger(__name__)

EXPORT_BASE_DIR = os.getenv("EXPORT_BASE_DIR", "runtime/exports")
EXPORT_RETENTION_HOURS = int(os.getenv("EXPORT_RETENTION_HOURS", "24"))


class ExportJobCancelledError(Exception):
    """취소된 export job 처리를 중단하기 위한 내부 예외"""


def _delete_file_if_exists(file_path: str | None) -> None:
    """파일이 존재하면 삭제"""
    if file_path and os.path.exists(file_path):
        os.remove(file_path)


def _sanitize_file_name(file_name: str) -> str:
    """ZIP 경로와 파일명에 사용할 안전한 파일명을 생성"""
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", (file_name or "").strip())
    safe_name = re.sub(r"\s+", "_", safe_name)
    return safe_name or "document"


def _normalize_category(category: str | None) -> str:
    """카테고리 값을 ZIP 경로용 이름으로 정규화"""
    normalized = (category or "").strip()
    return normalized or "미분류"


def _normalize_approval_status(document) -> str:
    """승인 상태를 ZIP 상위 폴더명으로 정규화"""
    approval = getattr(document, "approval", None)
    if not approval or not getattr(approval, "status", None):
        return "UNKNOWN"
    return approval.status.value


def _build_document_entry_name(document) -> str:
    """ZIP 내부 파일명을 {문서ID}_{원본파일명} 형식으로 생성"""
    original_file_name = document.original_filename or f"document_{document.id}"
    safe_file_name = _sanitize_file_name(original_file_name)
    return f"{document.id}_{safe_file_name}"


def _build_document_arcname(document) -> str:
    """ZIP 내부 경로를 승인상태/카테고리/파일명 구조로 생성"""
    approval_status = _normalize_approval_status(document)
    category = _normalize_category(getattr(document, "category", None))
    entry_name = _build_document_entry_name(document)

    if document.lifecycle_status == DocumentLifecycleStatus.DELETE_PENDING:
        return f"휴지통/{approval_status}/{category}/{entry_name}"

    return f"{approval_status}/{category}/{entry_name}"


def _build_missing_files_content(
    *,
    group_id: int,
    missing_files: list[str],
    total_candidates: int,
    exported_file_count: int,
) -> str:
    """ZIP 루트에 넣을 missing_files.txt 내용을 생성"""
    lines = [
        "전체 다운로드 결과",
        "",
        f"group_id: {group_id}",
        f"total_file_count: {total_candidates}",
        f"exported_file_count: {exported_file_count}",
        f"missing_file_count: {len(missing_files)}",
        "",
    ]

    if missing_files:
        lines.append("누락 파일 목록")
        lines.append("")
        lines.extend(f"- {file_name}" for file_name in missing_files)
    else:
        lines.append("누락 파일 없음")

    lines.append("")
    return "\n".join(lines)


def _build_export_file_name(job) -> str:
    """사용자 다운로드용 ZIP 파일명을 생성"""
    group_name = getattr(job.group, "name", None) or f"group_{job.group_id}"
    safe_group_name = _sanitize_file_name(group_name)
    return f"{safe_group_name}_documents.zip"


def run_group_export_job(export_job_id: int) -> dict:
    """그룹 전체 다운로드 ZIP 생성 로직을 수행"""
    db = SessionLocal()
    repository = ExportRepository(db)

    job = None
    temp_zip_path = None
    final_zip_path = None

    try:
        job = repository.get_by_id(export_job_id)
        if not job:
            return {
                "ready": False,
                "reason": "export_job_not_found",
                "export_job_id": export_job_id,
            }

        if job.status == ExportJobStatus.CANCELLED:
            return {
                "ready": False,
                "cancelled": True,
                "export_job_id": export_job_id,
            }

        processing_job = repository.mark_processing(job.id)
        if not processing_job:
            db.rollback()
            return {
                "ready": False,
                "cancelled": True,
                "export_job_id": export_job_id,
            }

        db.commit()
        job = processing_job
        db.refresh(job)

        export_dir = os.path.join(EXPORT_BASE_DIR, f"group_{job.group_id}")
        os.makedirs(export_dir, exist_ok=True)

        final_zip_path = os.path.join(export_dir, f"export_{job.id}.zip")
        temp_zip_path = os.path.join(export_dir, f"export_{job.id}.tmp")

        _delete_file_if_exists(temp_zip_path)

        documents = repository.get_group_documents_for_export(group_id=job.group_id)

        missing_files: list[str] = []
        exported_file_count = 0

        with zipfile.ZipFile(
            temp_zip_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for document in documents:
                db.refresh(job)
                if job.status == ExportJobStatus.CANCELLED:
                    raise ExportJobCancelledError()

                stored_path = (document.stored_path or "").strip()
                entry_name = _build_document_entry_name(document)

                if not stored_path or not os.path.exists(stored_path):
                    missing_files.append(entry_name)
                    continue

                archive.write(
                    stored_path,
                    arcname=_build_document_arcname(document),
                )
                exported_file_count += 1

            archive.writestr(
                "missing_files.txt",
                _build_missing_files_content(
                    group_id=job.group_id,
                    missing_files=missing_files,
                    total_candidates=len(documents),
                    exported_file_count=exported_file_count,
                ),
            )

        db.refresh(job)
        if job.status == ExportJobStatus.CANCELLED:
            raise ExportJobCancelledError()

        _delete_file_if_exists(final_zip_path)
        os.replace(temp_zip_path, final_zip_path)

        repository.mark_ready(
            job.id,
            file_path=final_zip_path,
            export_file_name=_build_export_file_name(job),
            total_file_count=len(documents),
            exported_file_count=exported_file_count,
            missing_file_count=len(missing_files),
            expires_at=utc_now_naive() + timedelta(hours=EXPORT_RETENTION_HOURS),
        )
        db.commit()

        return {
            "ready": True,
            "export_job_id": job.id,
            "total_file_count": len(documents),
            "exported_file_count": exported_file_count,
            "missing_file_count": len(missing_files),
        }

    except ExportJobCancelledError:
        _delete_file_if_exists(temp_zip_path)
        _delete_file_if_exists(final_zip_path)

        if job is not None:
            repository.mark_cancelled(job.id)
            db.commit()

        return {
            "ready": False,
            "cancelled": True,
            "export_job_id": export_job_id,
        }

    except Exception as e:
        logger.error(
            "[export job 실패] export_job_id=%s, error=%s",
            export_job_id,
            e,
            exc_info=True,
        )

        _delete_file_if_exists(temp_zip_path)
        _delete_file_if_exists(final_zip_path)

        if job is not None:
            repository.mark_failed(
                job.id,
                failure_stage=FailureStage.ZIP_BUILD.value,
                failure_code=ErrorCode.EXPORT_BUILD_FAILED.code,
                error_message=ErrorCode.EXPORT_BUILD_FAILED.message,
            )
            db.commit()

        return build_failure_payload(
            stage=FailureStage.ZIP_BUILD,
            error_code=ErrorCode.EXPORT_BUILD_FAILED,
            status="failed",
            retryable=False,
            ready=False,
            export_job_id=export_job_id,
        )

    finally:
        db.close()


def run_cleanup_expired_exports() -> dict:
    """보관 기간이 지난 READY export job을 EXPIRED로 정리"""
    db = SessionLocal()
    repository = ExportRepository(db)

    try:
        expired_jobs = repository.get_expired_ready_jobs(now=utc_now_naive())
        expired_count = 0

        for job in expired_jobs:
            _delete_file_if_exists(job.file_path)
            repository.mark_expired(job.id)
            expired_count += 1

        db.commit()
        return {"expired_count": expired_count}

    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.export_task.build_group_export")
def build_group_export(self, export_job_id: int) -> dict:
    """그룹 전체 다운로드 ZIP 생성을 수행"""
    return run_group_export_job(export_job_id)


@celery_app.task(bind=True, name="tasks.export_task.cleanup_expired_exports")
def cleanup_expired_exports(self) -> dict:
    """만료된 export job 정리를 수행"""
    return run_cleanup_expired_exports()
