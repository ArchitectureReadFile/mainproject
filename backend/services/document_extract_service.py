"""
services/document_extract_service.py

PDF 문서 추출 서비스.

담당:
    - 기본 opendataloader-pdf 추출 시도
    - body 비어 있으면 LocalOcrService.extract_text() 호출
    - ExtractedDocument 조립
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Literal

import opendataloader_pdf as odl

from errors import AppException, ErrorCode
from services.ocr.local_ocr_service import LocalOcrService
from services.ocr.ocr_service import OcrService

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocument:
    markdown: str
    json_data: dict | None
    source_type: Literal["odl", "ocr"]


class DocumentExtractService:
    def __init__(self, ocr_service: OcrService | None = None) -> None:
        self.format = os.getenv("ODL_OUTPUT_FORMAT", "markdown,json")
        self.image_output = os.getenv("ODL_IMAGE_OUTPUT", "off")
        self._ocr: OcrService = ocr_service or LocalOcrService()

    # ── public ───────────────────────────────────────────────────────────────

    def extract(self, file_path: str) -> ExtractedDocument:
        if not os.path.exists(file_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        logger.info("[문서 추출] 1차 시도: path=%s", file_path)
        extracted: ExtractedDocument | None = None

        try:
            with tempfile.TemporaryDirectory() as output_dir:
                self._convert(file_path, output_dir)
                extracted = self._load_results(output_dir, os.path.basename(file_path))
        except AppException:
            raise
        except Exception as exc:
            logger.info(
                "[문서 추출] 1차 변환 오류 → OCR fallback: path=%s error=%s",
                file_path,
                exc,
            )

        if extracted is not None and self._extract_body(extracted).strip():
            return extracted

        if extracted is not None:
            logger.info(
                "[문서 추출] 1차 body 비어 있음 → OCR fallback: path=%s", file_path
            )

        return self._extract_with_ocr(file_path)

    def extract_bytes(self, file_bytes: bytes) -> ExtractedDocument:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            return self.extract(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    # ── private ──────────────────────────────────────────────────────────────

    def _extract_with_ocr(self, file_path: str) -> ExtractedDocument:
        logger.info("[문서 추출] OCR fallback 시도: path=%s", file_path)

        try:
            text = self._ocr.extract_text(file_path)
        except Exception as exc:
            logger.error(
                "[문서 추출] OCR 오류: path=%s error=%s", file_path, exc, exc_info=True
            )
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR) from exc

        if not text or not text.strip():
            logger.warning("[문서 추출] OCR 후에도 body 비어 있음: path=%s", file_path)
            raise AppException(ErrorCode.DOC_PDF_TEXT_TOO_SHORT)

        logger.info(
            "[문서 추출] OCR fallback 성공: path=%s chars=%d", file_path, len(text)
        )
        return ExtractedDocument(markdown=text, json_data=None, source_type="ocr")

    def _extract_body(self, extracted: ExtractedDocument) -> str:
        """body 유무 판단용. markdown 우선, 없으면 json fallback."""
        body = (extracted.markdown or "").strip()
        if body:
            return body
        return _extract_body_from_json(extracted.json_data)

    def _convert(self, file_path: str, output_dir: str) -> None:
        try:
            odl.convert(
                input_path=file_path,
                output_dir=output_dir,
                format=self.format,
                image_output=self.image_output,
                quiet=True,
            )
        except Exception as exc:
            logger.error(
                "[문서 추출] 기본 변환 오류: path=%s error=%s",
                file_path,
                exc,
                exc_info=True,
            )
            raise

    def _load_results(
        self, output_dir: str, original_filename: str
    ) -> ExtractedDocument:
        stem = os.path.splitext(original_filename)[0]
        md_path = os.path.join(output_dir, f"{stem}.md")
        json_path = os.path.join(output_dir, f"{stem}.json")

        markdown = self._read_first_matching_file(output_dir, md_path, ".md")
        json_data = self._read_json_with_fallback(output_dir, json_path)

        return ExtractedDocument(
            markdown=markdown,
            json_data=json_data,
            source_type="odl",
        )

    def _read_first_matching_file(
        self, output_dir: str, preferred_path: str, suffix: str
    ) -> str:
        if os.path.exists(preferred_path):
            with open(preferred_path, encoding="utf-8") as f:
                return f.read()
        for fname in os.listdir(output_dir):
            if fname.endswith(suffix):
                with open(os.path.join(output_dir, fname), encoding="utf-8") as f:
                    return f.read()
        return ""

    def _read_json_with_fallback(
        self, output_dir: str, preferred_path: str
    ) -> dict | None:
        candidates = []
        if os.path.exists(preferred_path):
            candidates.append(preferred_path)
        candidates.extend(
            os.path.join(output_dir, fname)
            for fname in os.listdir(output_dir)
            if fname.endswith(".json")
            and os.path.join(output_dir, fname) != preferred_path
        )
        for path in candidates:
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("[문서 추출] json 파싱 실패: %s", path)
        return None


# ── 내부 헬퍼 (body 유무 판단 전용) ──────────────────────────────────────────
# normalize 책임은 DocumentNormalizeService에 있다.
# 여기서는 "OCR fallback 진입 여부 판단"에만 쓰인다.


def _extract_body_from_json(json_data: dict | list | None) -> str:
    if not json_data:
        return ""
    lines: list[str] = []
    _collect_body_lines(json_data, lines)
    return "\n".join(line for line in lines if line.strip()).strip()


def _collect_body_lines(node: dict | list, lines: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _collect_body_lines(item, lines)
        return
    if not isinstance(node, dict):
        return
    node_type = node.get("type")
    content = node.get("content")
    if isinstance(content, str) and content.strip():
        if node_type not in {"table cell", "table row", "table"}:
            lines.append(content.strip())
    for child in node.get("kids", []):
        _collect_body_lines(child, lines)
    for row in node.get("rows", []):
        _collect_body_lines(row, lines)
    for cell in node.get("cells", []):
        _collect_body_lines(cell, lines)
