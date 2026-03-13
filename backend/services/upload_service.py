import logging
import os
import re
from datetime import datetime

from repositories.document_repository import DocumentRepository
from services.summary.process_service import ProcessService
from services.upload_session_service import UploadSessionService

logger = logging.getLogger(__name__)


class UploadService:
    """파일 저장 + Document 레코드 생성 + 백그라운드 요약 태스크 등록을 담당합니다."""

    UPLOAD_DIR = "uploads"

    def __init__(self, repository: DocumentRepository):
        self.repository = repository
        self.process_service = ProcessService()
        self.upload_session_service = UploadSessionService()
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

    def handle_upload(self, files, background_tasks, user_id: int):
        doc_ids = []

        for file in files:
            filename = file.filename or "unknown.pdf"
            safe_name = re.sub(r"[^\w\-_. ]", "_", filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{timestamp}_{safe_name}"
            file_path = os.path.join(self.UPLOAD_DIR, unique_name)

            with open(file_path, "wb") as f:
                f.write(file.file.read())

            document = self.repository.create_pending_document(
                user_id=user_id,
                document_url=file_path,
            )
            doc_ids.append(document.id)
            self.upload_session_service.mark_processing(user_id, filename, document.id)

            background_tasks.add_task(
                self.process_service.process_file,
                file_path,
                document.id,
            )

        return {"message": "업로드 중", "document_ids": doc_ids}
