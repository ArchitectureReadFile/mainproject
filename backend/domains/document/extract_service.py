"""
domains/document/extract_service.py

PDF 문서 추출 서비스.

담당:
    - opendataloader-pdf hybrid OCR 경로 호출
    - markdown/json 결과를 ExtractedDocument로 조립
    - body 유무를 검증해 공통 에러 코드로 변환

환경변수 단위 정의:
    ODL_HYBRID_TIMEOUT: milliseconds (OpenDataLoader 공식 문서 기준)
                        로컬 기본값 180000 (3분), 운영 권장값 180000 이상
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

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocument:
    markdown: str
    json_data: dict | None
    source_type: Literal["odl", "ocr"]


class DocumentExtractService:
    def __init__(self) -> None:
        self.format = os.getenv("ODL_OUTPUT_FORMAT", "markdown,json")
        self.image_output = os.getenv("ODL_IMAGE_OUTPUT", "off")
        self.hybrid = os.getenv("ODL_HYBRID", "docling-fast")
        self.hybrid_mode = os.getenv("ODL_HYBRID_MODE")
        self.hybrid_url = os.getenv("ODL_HYBRID_URL", "http://odl_hybrid:5002")
        self.hybrid_timeout = int(
            os.getenv("ODL_HYBRID_TIMEOUT", "180000")
        )  # milliseconds
        self.hybrid_fallback = _env_bool("ODL_HYBRID_FALLBACK", False)

    # ── public ───────────────────────────────────────────────────────────────

    def extract(self, file_path: str) -> ExtractedDocument:
        if not os.path.exists(file_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        try:
            with tempfile.TemporaryDirectory() as output_dir:
                self._convert(file_path, output_dir)
                extracted = self._load_results(output_dir, os.path.basename(file_path))
        except AppException:
            raise
        except Exception as exc:
            logger.error(
                "[문서 추출] ODL hybrid 변환 오류: path=%s error=%s",
                file_path,
                exc,
                exc_info=True,
            )
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR) from exc

        if self._extract_body(extracted).strip():
            return extracted

        logger.warning("[문서 추출] ODL hybrid 결과 body 비어 있음: path=%s", file_path)
        raise AppException(ErrorCode.DOC_PDF_TEXT_TOO_SHORT)

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

    def _extract_body(self, extracted: ExtractedDocument) -> str:
        """body 유무 판단용. markdown 우선, 없으면 json fallback."""
        body = (extracted.markdown or "").strip()
        if body:
            return body
        return _extract_body_from_json(extracted.json_data)

    def _convert(self, file_path: str, output_dir: str) -> None:
        logger.info(
            "[문서 추출] ODL hybrid 호출: path=%s hybrid=%s url=%s timeout=%s fallback=%s",
            file_path,
            self.hybrid,
            self.hybrid_url,
            self.hybrid_timeout,
            self.hybrid_fallback,
        )
        odl.convert(
            input_path=file_path,
            output_dir=output_dir,
            format=self.format,
            image_output=self.image_output,
            quiet=True,
            hybrid=self.hybrid,
            hybrid_mode=self.hybrid_mode,
            hybrid_url=self.hybrid_url,
            hybrid_timeout=self.hybrid_timeout,
            hybrid_fallback=self.hybrid_fallback,
        )

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
# 여기서는 "추출 결과 body 유무 판단"에만 쓰인다.


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


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
