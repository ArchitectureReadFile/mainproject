"""
services/ocr/ocr_orchestrator.py

PDF 전체 OCR 오케스트레이션.
페이지별 page_ocr_policy를 호출하고 결과를 합산한다.
"""

from __future__ import annotations

import logging
import tempfile

import pypdfium2 as pdfium

from services.ocr import page_ocr_policy

logger = logging.getLogger(__name__)


def extract_text(pdf_path: str, worker_script: str) -> str:
    """
    PDF 전체를 페이지별로 OCR해 텍스트를 반환한다.

    Args:
        pdf_path      : OCR 대상 PDF 경로
        worker_script : worker subprocess 진입점 스크립트 경로

    Returns:
        전체 페이지 텍스트를 "\\n\\n"으로 합친 문자열.
        실패 시 빈 문자열.
    """
    try:
        pdf = pdfium.PdfDocument(pdf_path)
    except Exception as exc:
        logger.error("[orchestrator] PDF 열기 실패: path=%s error=%r", pdf_path, exc)
        return ""

    total_pages = len(pdf)
    pdf.close()

    page_texts: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for page_index in range(total_pages):
            pnum = page_index + 1
            text, path_tag = page_ocr_policy.run_page(
                pdf_path, page_index, pnum, total_pages, tmpdir, worker_script
            )
            _log_page(pnum, total_pages, text, path_tag)
            if text:
                page_texts.append(text)

    result = "\n\n".join(page_texts).strip()
    logger.info(
        "[orchestrator] 완료: total=%d collected=%d chars=%d",
        total_pages,
        len(page_texts),
        len(result),
    )
    return result


def _log_page(pnum: int, total: int, text: str, path_tag: str) -> None:
    qm = page_ocr_policy.quality_meta(text)
    logger.info(
        "[orchestrator] page=%d/%d path=%-14s | chars=%d korean=%d quality=%s%s",
        pnum,
        total,
        path_tag,
        qm["chars"],
        qm["korean"],
        "OK" if not qm["low"] else f"LOW({qm['reason']})",
        " [EMPTY]" if not text else "",
    )
