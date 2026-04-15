"""domains/document/summary_process.py

문서 처리 파이프라인 진입점 (Celery task 호출 경로).

흐름: extract/normalize(cache) → classify → summarize → DONE → index enqueue

■ normalized document cache 재사용:
    DocumentSchemaResolver.get_or_create()를 통해 DocumentSchema를 얻는다.
    직접 DocumentExtractService / DocumentNormalizeService를 호출하지 않는다.
    cache hit 시 원본 파일 I/O를 생략한다.

■ 승인 연동 계약 (auto-approved 및 early-approved 포함):
    processing_status == DONE 설정 직후 approval 상태를 다시 확인한다.
    - APPROVED 이면 즉시 index_approved_document.delay() 호출
    - 미승인이면 스킵 (이후 approve_document() 쪽에서 enqueue)
    이 계약 덕분에 auto-approved 업로드 / 조기 승인 두 경우 모두 정상 인덱싱된다.
"""

import logging
import os

from database import SessionLocal
from domains.document.classification_service import DocumentClassificationService
from domains.document.document_schema_resolver import DocumentSchemaResolver
from domains.document.repository import DocumentRepository
from domains.document.summary_llm_service import LLMService
from domains.document.summary_payload import (
    DocumentSummaryPayloadService,
)
from domains.document.summary_repository import SummaryRepository
from models.model import DocumentStatus, ReviewStatus

logger = logging.getLogger(__name__)


class ProcessService:
    def __init__(self):
        self.llm = LLMService()
        self.document_resolver = DocumentSchemaResolver()
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

            # 1. normalized document 로드 또는 생성
            document = self.document_resolver.get_or_create(
                document_id=document_id,
                file_path=file_path,
            )

            # 2. classify
            current_document = repository.get_by_id(document_id)
            title = (
                current_document.original_filename
                if current_document and current_document.original_filename
                else os.path.basename(file_path)
            )
            classification = self.classifier.classify(
                title=title,
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

            # 처리 완료 후 approval 상태를 다시 확인해 APPROVED면 인덱싱 enqueue
            # (auto-approved 문서와 조기 승인 문서 모두 이 경로를 통해 인덱싱됨)
            current_doc = repository.get_by_id(document_id)
            approval = getattr(current_doc, "approval", None) if current_doc else None
            if approval is not None and approval.status == ReviewStatus.APPROVED:
                from domains.document.index_task import index_approved_document

                index_approved_document.delay(document_id)
                logger.info(
                    "[process_file] APPROVED 확인 후 index enqueue: doc_id=%s",
                    document_id,
                )
            else:
                logger.info(
                    "[process_file] 인덱싱 스킵 (approval_status=%s): doc_id=%s",
                    approval.status.value if approval else "no_approval",
                    document_id,
                )

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
