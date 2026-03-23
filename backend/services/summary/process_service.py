import logging
import os

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from io import BytesIO

import numpy as np
import pdfplumber
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes

from database import SessionLocal
from errors import AppException, ErrorCode
from models.model import DocumentStatus
from repositories.document_repository import DocumentRepository
from repositories.summary_repository import SummaryRepository
from services.summary.llm_service import LLMService

logger = logging.getLogger(__name__)

_TEXT_FIELDS = {"summary_text", "document_type"}

MIN_TEXT_LENGTH = 200

_ocr_instance: PaddleOCR | None = None


def _get_ocr_instance() -> PaddleOCR:
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="korean")
    return _ocr_instance


class ProcessService:
    def __init__(self):
        self.llm = LLMService()

    def extract_pages_from_bytes(self, file_bytes: bytes) -> list[str]:
        ocr = _get_ocr_instance()
        pages = []

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            pdf_images = convert_from_bytes(file_bytes)

            for i, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                text = text.strip()

                image_objects = page.images
                if image_objects:
                    page_img = pdf_images[i]
                    page_width = page.width
                    page_height = page.height
                    img_w, img_h = page_img.size

                    ocr_texts = []
                    for img_obj in image_objects:
                        x0 = img_obj["x0"] / page_width * img_w
                        y0 = (page_height - img_obj["y1"]) / page_height * img_h
                        x1 = img_obj["x1"] / page_width * img_w
                        y1 = (page_height - img_obj["y0"]) / page_height * img_h

                        if (x1 - x0) < 30 or (y1 - y0) < 30:
                            continue

                        cropped = page_img.crop((x0, y0, x1, y1))
                        cropped_np = np.array(cropped)
                        result = ocr.ocr(cropped_np, cls=True)
                        if result and result[0]:
                            lines = [
                                line[1][0] for line in result[0] if line and line[1]
                            ]
                            ocr_texts.append(" ".join(lines))

                    if ocr_texts:
                        text = text + "\n" + "\n".join(ocr_texts)
                        logger.info(
                            f"[혼합 페이지 OCR] page={i + 1}, 이미지 영역 {len(ocr_texts)}개 처리"
                        )

                pages.append(text.strip())

        return pages

    def extract_pages_from_bytes_ocr(self, file_bytes: bytes) -> list[str]:
        ocr = _get_ocr_instance()
        images = convert_from_bytes(file_bytes)
        pages = []
        for image in images:
            image_np = np.array(image)
            result = ocr.ocr(image_np, cls=True)
            if result and result[0]:
                lines = [line[1][0] for line in result[0] if line and line[1]]
                pages.append(" ".join(lines))
            else:
                pages.append("")
        return pages

    def is_text_too_short(self, text: str) -> bool:
        return len(text.strip()) < MIN_TEXT_LENGTH

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

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            pages = self.extract_pages_from_bytes(file_bytes)

            if self.is_text_too_short("\n".join(pages)):
                logger.info(
                    f"[OCR fallback] doc_id={document_id}, 텍스트 레이어 부족 → PaddleOCR 시도"
                )
                pages = self.extract_pages_from_bytes_ocr(file_bytes)

            if self.is_text_too_short("\n".join(pages)):
                raise AppException(ErrorCode.DOC_PDF_TEXT_TOO_SHORT)

            raw_data = self.llm.summarize(pages)
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
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(
                        "[업로드 원본 삭제] doc_id=%s, path=%s", document_id, file_path
                    )
                except OSError:
                    logger.warning(
                        "[업로드 원본 삭제 실패] doc_id=%s, path=%s",
                        document_id,
                        file_path,
                        exc_info=True,
                    )
            raise
        finally:
            db.close()
