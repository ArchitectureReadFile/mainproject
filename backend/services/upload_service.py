import logging
import os
import re
from datetime import datetime

from repositories.document_repository import DocumentRepository
from services.upload_session_service import UploadSessionService
from tasks.upload_task import process_upload_task

logger = logging.getLogger(__name__)


class UploadService:
    UPLOAD_DIR = "uploads"

    def __init__(self, repository: DocumentRepository):
        self.repository = repository
        self.upload_session_service = UploadSessionService()
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

    def handle_upload(self, files, user_id: int):
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

            process_upload_task.delay(
                file_path=file_path,
                document_id=document.id,
                user_id=user_id,
                file_name=filename,
            )

        return {"message": "업로드 중", "document_ids": doc_ids}
