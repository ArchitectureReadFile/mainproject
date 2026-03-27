"""
services/ocr/page_renderer.py

pdfium 페이지 → PNG 파일 렌더링.
"""

from __future__ import annotations

import logging

import pypdfium2 as pdfium

logger = logging.getLogger(__name__)

_RENDER_SCALE = 1.0


def render_page_to_file(
    pdf_path: str,
    page_index: int,
    output_path: str,
    scale: float = _RENDER_SCALE,
) -> bool:
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        page = pdf[page_index]
        try:
            bitmap = page.render(scale=scale)
            bitmap.to_pil().convert("RGB").save(output_path)
            return True
        finally:
            page.close()
            pdf.close()
    except Exception as exc:
        logger.warning(
            "[renderer] 렌더링 실패: path=%s page=%d error=%r",
            pdf_path,
            page_index,
            exc,
        )
        return False
