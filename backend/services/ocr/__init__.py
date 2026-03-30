"""services/ocr/__init__.py"""

from services.ocr.local_ocr_service import LocalOcrService
from services.ocr.ocr_service import OcrService

__all__ = ["OcrService", "LocalOcrService"]
