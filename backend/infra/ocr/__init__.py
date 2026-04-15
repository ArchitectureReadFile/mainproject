"""OCR 인프라 패키지."""

from infra.ocr.local_ocr_service import LocalOcrService
from infra.ocr.ocr_service import OcrService

__all__ = ["OcrService", "LocalOcrService"]
