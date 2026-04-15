"""
services/ocr/page_worker_runner.py

단일 페이지 이미지 OCR worker subprocess 실행.
subprocess 호출, stdout/stderr 파싱, timeout 처리만 담당한다.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_STDERR_LOG_MAX = 5000


def run(
    image_path: str,
    det_limit: int,
    timeout: int,
    worker_script: str,
    tag: str = "",
) -> dict:
    """
    worker_script를 subprocess로 실행해 OCR 결과를 반환한다.

    Returns:
        {"text": str, "chars": int, "korean": int}
    """
    try:
        proc = subprocess.run(
            [sys.executable, worker_script, image_path, str(det_limit)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[worker_runner] timeout: %s", tag)
        return _empty()

    if proc.returncode != 0:
        _log_failure(tag, proc)
        return _empty()

    return _parse_stdout(tag, proc.stdout)


def _empty() -> dict:
    return {"text": "", "chars": 0, "korean": 0}


def _log_failure(tag: str, proc: subprocess.CompletedProcess) -> None:
    stderr_out = proc.stderr.strip()
    stdout_out = proc.stdout.strip()
    logger.warning(
        "[worker_runner] 실패: %s exit=%d\n"
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


def _parse_stdout(tag: str, stdout: str) -> dict:
    try:
        data = json.loads(stdout.strip())
    except json.JSONDecodeError:
        logger.warning(
            "[worker_runner] stdout 파싱 실패: %s stdout=%r", tag, stdout[:500]
        )
        return _empty()

    text = data.get("text", "")
    chars = data.get("chars", len(text))
    korean = data.get("korean", sum(1 for c in text if "\uac00" <= c <= "\ud7a3"))
    return {"text": text, "chars": chars, "korean": korean}
