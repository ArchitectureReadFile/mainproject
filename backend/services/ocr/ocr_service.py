"""
services/ocr/ocr_service.py

PDF OCR 서비스 인터페이스.
구현체 교체 시 이 인터페이스를 유지한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class OcrService(ABC):
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """
        PDF 파일에서 OCR로 텍스트를 추출한다.

        Returns:
            추출된 텍스트. 없으면 빈 문자열.
        Raises:
            Exception: 복구 불가능한 오류 발생 시.
        """
