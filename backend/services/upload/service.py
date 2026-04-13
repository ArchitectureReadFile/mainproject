import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Optional

from models.model import MembershipRole, ReviewStatus, utc_now_naive
from repositories.document_repository import DocumentRepository
from services.group_service import GroupService
from tasks.upload_task import process_next_pending_document

logger = logging.getLogger(__name__)


class UploadService:
    UPLOAD_DIR = "uploads/documents"

    def __init__(self, repository: DocumentRepository, group_service: GroupService):
        self.repository = repository
        self.group_service = group_service
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        return unicodedata.normalize("NFC", filename or "").strip()

    def handle_upload(
        self,
        files,
        *,
        user_id: int,
        group_id: int,
        uploader_role: MembershipRole,
        assignee_user_id: Optional[int] = None,
    ):
        doc_ids = []
        is_auto_approved = uploader_role in (MembershipRole.OWNER, MembershipRole.ADMIN)

        if not is_auto_approved and assignee_user_id is not None:
            self.group_service.assert_reviewer_assignable(assignee_user_id, group_id)

        for file in files:
            filename = self._normalize_filename(file.filename or "unknown")
            safe_name = re.sub(r"[^\w\-_. ]", "_", filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{timestamp}_u{user_id}_g{group_id}_{safe_name}"

            group_dir = os.path.join(self.UPLOAD_DIR, f"group_{group_id}")
            os.makedirs(group_dir, exist_ok=True)
            file_path = os.path.join(group_dir, unique_name)

            with open(file_path, "wb") as f:
                f.write(file.file.read())

            document = self.repository.create_pending_document(
                group_id=group_id,
                uploader_user_id=user_id,
                original_filename=filename,
                stored_path=file_path,
                original_content_type=file.content_type,
            )

            if is_auto_approved:
                self.repository.create_document_approval(
                    document_id=document.id,
                    status=ReviewStatus.APPROVED,
                    reviewer_user_id=user_id,
                    reviewed_at=utc_now_naive(),
                )
            else:
                self.repository.create_document_approval(
                    document_id=document.id,
                    status=ReviewStatus.PENDING_REVIEW,
                    assignee_user_id=assignee_user_id,
                )

                if assignee_user_id:
                    from models.model import NotificationType
                    from repositories.notification_repository import (
                        NotificationRepository,
                    )
                    from services.notification_service import NotificationService

                    notif_repo = NotificationRepository(self.repository.db)
                    notif_service = NotificationService(notif_repo)  # ✅
                    notif_service.create_notification_sync(
                        user_id=assignee_user_id,  # ✅ repository= 제거
                        actor_user_id=user_id,
                        group_id=group_id,
                        type=NotificationType.DOCUMENT_UPLOAD_REQUESTED,
                        title="새로운 문서 검토 요청",
                        body=f"'{filename}' 문서의 검토 승인자로 지정되었습니다.",
                        target_type="group",
                        target_id=group_id,
                    )

            self.repository.db.commit()
            self.repository.db.refresh(document)
            doc_ids.append(document.id)

        if doc_ids:
            process_next_pending_document.delay()

        return {"message": "업로드 완료, AI 처리 대기 중", "document_ids": doc_ids}
