import logging

from database import SessionLocal
from models.model import DocumentStatus
from repositories.document_repository import DocumentRepository
from repositories.summary_repository import SummaryRepository
from services.document_classification_service import DocumentClassificationService
from services.document_extract_service import DocumentExtractService
from services.document_normalize_service import DocumentNormalizeService
from services.summary.document_summary_payload_service import (
    DocumentSummaryPayloadService,
)
from services.summary.llm_service import LLMService

logger = logging.getLogger(__name__)


class ProcessService:
    def __init__(self):
        self.llm = LLMService()
        self.extractor = DocumentExtractService()
        self.normalizer = DocumentNormalizeService()
        self.classifier = DocumentClassificationService()
        self.summary_payload = DocumentSummaryPayloadService()

    def _normalize_summary_data(self, data: dict) -> dict:
        """LLM 응답의 타입을 DB 저장 가능한 형태로 정규화합니다."""
        normalized = {}
        for key, value in data.items():
            if value is None or value == "" or str(value).strip().lower() == "null":
                normalized[key] = None
            elif key == "summary_text":
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

            # 1. extract → normalize
            extracted = self.extractor.extract(file_path)
            document = self.normalizer.normalize(extracted)

            # 2. classify
            classification = self.classifier.classify(
                title=document.metadata.get("title"),
                body_text=document.body_text,
            )
            logger.info(
                "[분류 완료] doc_id=%s, document_type=%s, category=%s",
                document_id,
                classification["document_type"],
                classification["category"],
            )

            # 3. classification 저장
            repository.update_classification(
                document_id,
                document_type=classification["document_type"],
                category=classification["category"],
            )
            db.commit()

            # 4. summarize
            summary_input = self.summary_payload.build(document)
            raw_data = self.llm.summarize([summary_input])
            summary_data = self._normalize_summary_data(raw_data)

            # 5. summary 저장
            summary_repo = SummaryRepository(db)
            summary_repo.create_summary(
                document_id=document_id,
                summary_text=summary_data.get("summary_text"),
                key_points=(
                    "\n".join(summary_data.get("key_points", []))
                    if summary_data.get("key_points")
                    else None
                ),
                metadata={"source": "group_document_summary"},
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
