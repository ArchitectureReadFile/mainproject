"""
services/ocr/document_worker_runner.py

문서 단위 OCR subprocess 실행.
run_ocr_document.py를 subprocess로 기동하고 결과를 파싱해 반환한다.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

_STDERR_LOG_MAX = 5000
_DOCUMENT_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "run_ocr_document.py"
)

DEFAULT_TIMEOUT = 600  # 10분


def run(pdf_path: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    run_ocr_document.py를 subprocess로 실행해 PDF 전체 OCR 텍스트를 반환한다.

    PYTHONPATH=/app を환경변수로 명시해 subprocess 안에서
    'from services.ocr...' import가 반드시 동작하도록 보장한다.

    Raises:
        RuntimeError: subprocess 실패(exit!=0) 또는 timeout 시
    """
    tag = f"doc={os.path.basename(pdf_path)}"
    logger.info("[doc_runner] 시작: %s timeout=%ds", tag, timeout)

    # 컨테이너 workdir(/app)를 PYTHONPATH에 추가해 services 패키지를 찾게 함
    env = {**os.environ, "PYTHONPATH": "/app"}

    try:
        proc = subprocess.run(
            [sys.executable, _DOCUMENT_SCRIPT, pdf_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.error("[doc_runner] timeout: %s (%ds 초과)", tag, timeout)
        raise RuntimeError(f"문서 OCR timeout: {pdf_path}")

    if proc.returncode != 0:
        stderr_out = proc.stderr.strip()
        stdout_out = proc.stdout.strip()
        logger.error(
            "[doc_runner] 실패: %s exit=%d\n"
            "=== stderr (%d chars) ===\n%s\n"
            "=== stdout (%d chars) ===\n%s\n"
            "=== end ===",
            tag,
            proc.returncode,
            len(stderr_out),
            stderr_out[:_STDERR_LOG_MAX],
            len(stdout_out),
            stdout_out[:500],
        )
        raise RuntimeError(f"문서 OCR 실패 (exit={proc.returncode}): {pdf_path}")

    try:
        data = json.loads(proc.stdout.strip())
        text = data.get("text", "")
        chars = data.get("chars", len(text))
        logger.info("[doc_runner] 완료: %s chars=%d", tag, chars)
        return text
    except json.JSONDecodeError:
        logger.error(
            "[doc_runner] stdout 파싱 실패: %s stdout=%r", tag, proc.stdout[:500]
        )
        raise RuntimeError(f"문서 OCR 결과 파싱 실패: {pdf_path}")
