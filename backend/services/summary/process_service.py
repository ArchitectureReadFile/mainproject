import logging

from database import SessionLocal
from models.model import DocumentStatus
from repositories.document_repository import DocumentRepository
from repositories.summary_repository import SummaryRepository
from services.document_extract_service import DocumentExtractService
from services.document_normalize_service import DocumentNormalizeService
from services.summary.document_summary_payload_service import (
    DocumentSummaryPayloadService,
)
from services.summary.llm_service import LLMService

logger = logging.getLogger(__name__)

_TEXT_FIELDS = {"summary_text", "document_type"}


class ProcessService:
    def __init__(self):
        self.llm = LLMService()
        self.extractor = DocumentExtractService()
        self.normalizer = DocumentNormalizeService()
        self.summary_payload = DocumentSummaryPayloadService()

    def _normalize_summary_data(self, data: dict) -> dict:
        """LLM 응답의 타입을 DB 저장 가능한 형태로 정규화합니다."""
        normalized = {}
        for key, value in data.items():
            if value is None or value == "" or str(value).strip().lower() == "null":
                normalized[key] = None
            elif key in _TEXT_FIELDS:
                normalized[key] = str(value).strip() or None
            elif key == "key_points":
                if isinstance(value, list):
                    normalized[key] = [str(v).strip() for v in value if str(v).strip()]
                else:
                    normalized[key] = [
                        line.strip().lstrip("-").lstrip("•").strip()
                        for line in str(value).splitlines()
                        if line.strip()
                    ]
            else:
                normalized[key] = value
        return normalized

    def process_file(
        self, file_path: str, document_id: int, *, mark_processing: bool = True
    ):
        db = SessionLocal()
        repository = DocumentRepository(db)

        try:
            if mark_processing:
                repository.update_status(document_id, DocumentStatus.PROCESSING)
                db.commit()

            extracted = self.extractor.extract(file_path)
            document = self.normalizer.normalize(extracted)
            summary_input = self.summary_payload.build(document)

            raw_data = self.llm.summarize([summary_input])
            summary_data = self._normalize_summary_data(raw_data)

            metadata = {"source": "group_document_summary"}
            if summary_data.get("document_type"):
                metadata["document_type"] = summary_data["document_type"]

            summary_repo = SummaryRepository(db)
            summary_repo.create_summary(
                document_id=document_id,
                summary_text=summary_data.get("summary_text"),
                key_points=(
                    "\n".join(summary_data.get("key_points", []))
                    if summary_data.get("key_points")
                    else None
                ),
                metadata=metadata,
            )

            repository.update_status(document_id, DocumentStatus.DONE)
            db.commit()

        except Exception as e:
            db.rollback()
            self.llm.release_resources()
            logger.error(
                f"[요약 실패] doc_id={document_id}, error={str(e)}", exc_info=True
            )
            repository.update_status(document_id, DocumentStatus.FAILED)
            db.commit()
            raise
        finally:
            db.close()
