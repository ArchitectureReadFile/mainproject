from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models.model import (
    Document,
    DocumentLifecycleStatus,
    ExportJob,
    ExportJobStatus,
    MembershipRole,
    utc_now_naive,
)


class ExportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_reusable_job(self, *, user_id: int, group_id: int) -> ExportJob | None:
        """동일 사용자/그룹의 재사용 가능한 진행 중 job을 조회"""
        return (
            self.db.query(ExportJob)
            .filter(
                ExportJob.user_id == user_id,
                ExportJob.group_id == group_id,
                ExportJob.status.in_(
                    [
                        ExportJobStatus.PENDING,
                        ExportJobStatus.PROCESSING,
                    ]
                ),
            )
            .order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
            .first()
        )

    def create_job(
        self,
        *,
        user_id: int,
        group_id: int,
        requester_role: MembershipRole,
    ) -> ExportJob:
        """새 export job을 생성"""
        job = ExportJob(
            user_id=user_id,
            group_id=group_id,
            requester_role=requester_role,
            status=ExportJobStatus.PENDING,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get_by_id(self, export_job_id: int) -> ExportJob | None:
        """export job 단건을 조회"""
        return (
            self.db.query(ExportJob)
            .options(
                joinedload(ExportJob.user),
                joinedload(ExportJob.group),
            )
            .filter(ExportJob.id == export_job_id)
            .first()
        )

    def get_by_id_for_user(
        self,
        *,
        export_job_id: int,
        user_id: int,
    ) -> ExportJob | None:
        """특정 사용자가 소유한 export job 단건을 조회"""
        return (
            self.db.query(ExportJob)
            .options(joinedload(ExportJob.group))
            .filter(
                ExportJob.id == export_job_id,
                ExportJob.user_id == user_id,
            )
            .first()
        )

    def mark_processing(self, export_job_id: int) -> ExportJob | None:
        """PENDING 상태 job만 PROCESSING으로 변경하고 시작 시각을 기록"""
        job = self.db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
        if not job:
            return None

        if job.status != ExportJobStatus.PENDING:
            return None

        job.status = ExportJobStatus.PROCESSING
        job.started_at = job.started_at or utc_now_naive()
        job.error_message = None
        return job

    def mark_ready(
        self,
        export_job_id: int,
        *,
        file_path: str,
        export_file_name: str,
        total_file_count: int,
        exported_file_count: int,
        missing_file_count: int,
        expires_at: datetime,
    ) -> ExportJob | None:
        """job 상태를 READY로 변경하고 결과 파일 정보를 저장"""
        job = self.db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
        if not job:
            return None

        job.status = ExportJobStatus.READY
        job.file_path = file_path
        job.export_file_name = export_file_name
        job.error_message = None
        job.total_file_count = total_file_count
        job.exported_file_count = exported_file_count
        job.missing_file_count = missing_file_count
        job.finished_at = utc_now_naive()
        job.expires_at = expires_at
        return job

    def mark_failed(self, export_job_id: int, error_message: str) -> ExportJob | None:
        """job 상태를 FAILED로 변경하고 실패 메시지를 저장"""
        job = self.db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
        if not job:
            return None

        job.status = ExportJobStatus.FAILED
        job.error_message = error_message
        job.finished_at = utc_now_naive()
        job.expires_at = None
        return job

    def mark_cancelled(self, export_job_id: int) -> ExportJob | None:
        """job 상태를 CANCELLED로 변경"""
        job = self.db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
        if not job:
            return None

        now = utc_now_naive()
        job.status = ExportJobStatus.CANCELLED
        job.cancelled_at = now
        job.finished_at = now
        job.expires_at = None
        return job

    def mark_expired(self, export_job_id: int) -> ExportJob | None:
        """job 상태를 EXPIRED로 변경하고 파일 정보를 비움"""
        job = self.db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
        if not job:
            return None

        job.status = ExportJobStatus.EXPIRED
        job.file_path = None
        job.expires_at = None
        return job

    def get_expired_ready_jobs(self, *, now: datetime) -> list[ExportJob]:
        """보관 기간이 지난 READY job 목록을 조회"""
        return (
            self.db.query(ExportJob)
            .filter(
                ExportJob.status == ExportJobStatus.READY,
                ExportJob.expires_at.is_not(None),
                ExportJob.expires_at <= now,
            )
            .order_by(ExportJob.expires_at.asc(), ExportJob.id.asc())
            .all()
        )

    def get_group_documents_for_export(self, *, group_id: int) -> list[Document]:
        """그룹 전체 다운로드 대상 문서를 조회"""
        return (
            self.db.query(Document)
            .options(joinedload(Document.approval))
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status.in_(
                    [
                        DocumentLifecycleStatus.ACTIVE,
                        DocumentLifecycleStatus.DELETE_PENDING,
                    ]
                ),
            )
            .order_by(Document.created_at.asc(), Document.id.asc())
            .all()
        )

    def get_latest_job_for_user_group(
        self,
        *,
        user_id: int,
        group_id: int,
    ) -> ExportJob | None:
        """특정 사용자/그룹의 가장 최근 export job을 조회"""
        return (
            self.db.query(ExportJob)
            .options(joinedload(ExportJob.group))
            .filter(
                ExportJob.user_id == user_id,
                ExportJob.group_id == group_id,
            )
            .order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
            .first()
        )
