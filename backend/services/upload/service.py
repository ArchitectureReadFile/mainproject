import logging
import os
import re
from datetime import datetime

from repositories.document_repository import DocumentRepository
from tasks.upload_task import process_next_pending_document

logger = logging.getLogger(__name__)


class UploadService:
    UPLOAD_DIR = "uploads/documents"

    def __init__(self, repository: DocumentRepository):
        self.repository = repository
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

    def handle_upload(self, files, *, user_id: int, group_id: int):
        doc_ids = []

        for file in files:
            filename = file.filename or "unknown.pdf"
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
            )
            self.repository.db.commit()
            self.repository.db.refresh(document)
            doc_ids.append(document.id)

        if doc_ids:
            process_next_pending_document.delay()

        return {"message": "업로드 완료, AI 요약 대기 중", "document_ids": doc_ids}
