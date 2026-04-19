import os

from domains.export.repository import ExportRepository
from domains.export.schemas import ExportJobResponse
from domains.export.tasks import build_group_export
from domains.workspace.service import GroupService
from errors import AppException, ErrorCode, FailureStage
from models.model import ExportJobStatus, utc_now_naive


class ExportService:
    def __init__(
        self,
        repository: ExportRepository,
        group_service: GroupService,
    ):
        self.repository = repository
        self.group_service = group_service

    def _delete_file_if_exists(self, file_path: str | None) -> None:
        """ZIP 파일이 존재하면 삭제"""
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    def _expire_if_needed(self, job) -> None:
        """만료된 READY job을 EXPIRED로 전환"""
        if job.status != ExportJobStatus.READY:
            return

        if job.expires_at is None or job.expires_at > utc_now_naive():
            return

        self._delete_file_if_exists(job.file_path)
        self.repository.mark_expired(job.id)
        self.repository.db.commit()
        self.repository.db.refresh(job)

    def _to_response(self, job, *, reused: bool = False) -> ExportJobResponse:
        """ExportJob ORM 객체를 응답 스키마로 변환"""
        return ExportJobResponse(
            id=job.id,
            group_id=job.group_id,
            status=job.status.value,
            export_file_name=job.export_file_name,
            failure_stage=job.failure_stage,
            failure_code=job.failure_code,
            error_message=job.error_message,
            total_file_count=job.total_file_count,
            exported_file_count=job.exported_file_count,
            missing_file_count=job.missing_file_count,
            expires_at=job.expires_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            reused=reused,
        )

    def _get_owned_job(self, *, job_id: int, user_id: int):
        """현재 사용자가 소유한 export job을 조회하고 만료 여부를 보정"""
        job = self.repository.get_by_id_for_user(
            export_job_id=job_id,
            user_id=user_id,
        )
        if not job:
            raise AppException(ErrorCode.EXPORT_NOT_FOUND)

        self._expire_if_needed(job)
        return job

    def create_job(self, *, user_id: int, group_id: int) -> ExportJobResponse:
        """전체 다운로드 job을 생성하거나 기존 진행 중 job을 재사용"""
        _, member = self.group_service.assert_review_view_permission(user_id, group_id)

        reusable_job = self.repository.get_reusable_job(
            user_id=user_id,
            group_id=group_id,
        )
        if reusable_job:
            return self._to_response(reusable_job, reused=True)

        job = self.repository.create_job(
            user_id=user_id,
            group_id=group_id,
            requester_role=member.role,
        )
        self.repository.db.commit()
        self.repository.db.refresh(job)

        try:
            build_group_export.delay(job.id)
        except Exception:
            self.repository.mark_failed(
                job.id,
                failure_stage=FailureStage.ENQUEUE.value,
                failure_code=ErrorCode.EXPORT_ENQUEUE_FAILED.code,
                error_message=ErrorCode.EXPORT_ENQUEUE_FAILED.message,
            )
            self.repository.db.commit()
            raise AppException(ErrorCode.EXPORT_ENQUEUE_FAILED)
        return self._to_response(job)

    def get_latest_job_for_group(
        self,
        *,
        user_id: int,
        group_id: int,
    ) -> ExportJobResponse | None:
        """현재 사용자/그룹의 최근 export job을 조회"""
        self.group_service.assert_review_view_permission(user_id, group_id)

        job = self.repository.get_latest_job_for_user_group(
            user_id=user_id,
            group_id=group_id,
        )
        if not job:
            return None

        self._expire_if_needed(job)
        return self._to_response(job)

    def get_job(self, *, job_id: int, user_id: int) -> ExportJobResponse:
        """export job 상태를 조회"""
        job = self._get_owned_job(job_id=job_id, user_id=user_id)
        self.group_service.assert_review_view_permission(user_id, job.group_id)
        return self._to_response(job)

    def cancel_job(self, *, job_id: int, user_id: int) -> ExportJobResponse:
        """진행 중 export job을 취소"""
        job = self._get_owned_job(job_id=job_id, user_id=user_id)
        self.group_service.assert_review_view_permission(user_id, job.group_id)

        if job.status in (
            ExportJobStatus.PENDING,
            ExportJobStatus.PROCESSING,
        ):
            self._delete_file_if_exists(job.file_path)
            self.repository.mark_cancelled(job.id)
            self.repository.db.commit()
            self.repository.db.refresh(job)

        return self._to_response(job)

    def get_download_file(self, *, job_id: int, user_id: int) -> tuple[str, str]:
        """다운로드 가능한 ZIP 경로와 파일명을 반환"""
        job = self._get_owned_job(job_id=job_id, user_id=user_id)
        self.group_service.assert_review_view_permission(user_id, job.group_id)

        if job.status == ExportJobStatus.EXPIRED:
            raise AppException(ErrorCode.EXPORT_EXPIRED)

        if job.status == ExportJobStatus.CANCELLED:
            raise AppException(ErrorCode.EXPORT_CANCELLED)

        if job.status != ExportJobStatus.READY:
            raise AppException(ErrorCode.EXPORT_NOT_READY)

        if not job.file_path or not os.path.exists(job.file_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        return job.file_path, (job.export_file_name or f"export_{job.id}.zip")
