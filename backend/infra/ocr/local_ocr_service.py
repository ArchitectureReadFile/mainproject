"""
infra/ocr/local_ocr_service.py

backend 내부 OCR 서비스 구현체.

2단계 subprocess 격리:
    1. 문서 단위: document_worker_runner → run_ocr_document.py subprocess
    2. 페이지 단위: page_worker_runner → ocr_worker.py subprocess

backend 메인 프로세스는 OCR 장시간 실행을 직접 들고 있지 않으며,
문서 단위 subprocess가 종료되면 OCR 관련 메모리가 OS 수준에서 강제 회수된다.
반복 실행 시 이전 문서 잔류 메모리가 다음 실행에 누적되지 않는다.
"""

from __future__ import annotations

import logging

from infra.ocr.ocr_service import OcrService

logger = logging.getLogger(__name__)


class LocalOcrService(OcrService):
    def extract_text(self, file_path: str) -> str:
        from infra.ocr.document_worker_runner import run

        logger.info("[LocalOCR] 문서 subprocess 시작: path=%s", file_path)
        try:
            text = run(file_path)
        except RuntimeError as exc:
            logger.error(
                "[LocalOCR] 문서 subprocess 실패: path=%s error=%s", file_path, exc
            )
            raise
        logger.info("[LocalOCR] 완료: path=%s chars=%d", file_path, len(text))
        return text
