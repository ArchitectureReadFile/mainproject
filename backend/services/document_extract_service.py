"""
services/document_extract_service.py

OpenDataLoader PDF 공식 권장 흐름을 따르는 문서 추출 서비스.

2단계 추출 전략:
  1차) pdf_hybrid (일반 텍스트 추출, OCR 없음)
  2차) pdf_hybrid_ocr (--force-ocr)

  OCR fallback 진입 조건 (둘 중 하나):
    a) 1차 추출 성공했지만 body가 비어 있음
    b) 1차 convert가 _HybridParseError로 실패 (timeout 포함)

  OCR fallback 미진입 조건:
    - _HybridConnectionError (연결 실패/서버 불능) → 바로 DOC_INTERNAL_PARSE_ERROR

내부 예외 분류:
  _HybridConnectionError : 연결 실패, 서버 불능 → fallback 없이 상위로 전파
  _HybridParseError      : 문서 변환 실패       → OCR fallback 후보
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass

import opendataloader_pdf as odl

from errors import AppException, ErrorCode
from services.document_input_builder import (
    extract_body_from_json,
    extract_body_from_markdown,
)

logger = logging.getLogger(__name__)


# ── 내부 분류 예외 (모듈 외부 노출 불필요) ────────────────────────────────────


class _HybridConnectionError(Exception):
    """hybrid 서버 연결 실패 또는 서비스 불능."""


class _HybridParseError(Exception):
    """문서 변환 실패 (연결은 됐지만 파싱 오류)."""


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ExtractedDocument:
    markdown: str
    json_data: dict | None


class DocumentExtractService:
    def __init__(self) -> None:
        self.format = os.getenv("ODL_OUTPUT_FORMAT", "markdown,json")
        self.image_output = os.getenv("ODL_IMAGE_OUTPUT", "off")
        self.hybrid_backend = os.getenv("ODL_HYBRID_BACKEND", "docling-fast")
        # 1차: 일반 hybrid (OCR 없음)
        self.hybrid_url = os.getenv("ODL_HYBRID_URL", "http://pdf_hybrid:5002")
        self.hybrid_timeout = (
            os.getenv("ODL_HYBRID_TIMEOUT")
            or os.getenv("ODL_HYBRID_TIMEOUT_MS")
            or "300000"
        )
        self.force_hybrid = (
            os.getenv("ODL_FORCE_HYBRID", "true").strip().lower() == "true"
        )
        # 2차: OCR 전용 hybrid (스캔본 fallback)
        self.ocr_hybrid_url = os.getenv(
            "ODL_OCR_HYBRID_URL", "http://pdf_hybrid_ocr:5003"
        )
        self.ocr_hybrid_timeout = (
            os.getenv("ODL_OCR_HYBRID_TIMEOUT")
            or os.getenv("ODL_OCR_HYBRID_TIMEOUT_MS")
            or "300000"
        )

    # ── public ───────────────────────────────────────────────────────────────

    def extract(self, file_path: str) -> ExtractedDocument:
        if not os.path.exists(file_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        # 1차: 일반 추출
        logger.info("[문서 추출] 1차 시도 (일반): path=%s", file_path)

        try:
            with tempfile.TemporaryDirectory() as output_dir:
                self._convert(file_path, output_dir, force_ocr=False)
                extracted = self._load_results(output_dir, os.path.basename(file_path))

            if self._extract_body(extracted).strip():
                return extracted

            logger.info(
                "[문서 추출] 1차 body 비어 있음 → OCR fallback 진입: path=%s", file_path
            )

        except _HybridConnectionError as exc:
            logger.error(
                "[문서 추출 실패] hybrid 연결 불가, fallback 없음: path=%s, error=%s",
                file_path,
                exc,
            )
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR) from exc

        except _HybridParseError as exc:
            logger.info(
                "[문서 추출] 1차 변환 오류 → OCR fallback 진입: path=%s, error=%s",
                file_path,
                exc,
            )

        # 2차: OCR fallback
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
        """OCR 전용 hybrid로 재시도. 실패하거나 body가 비면 예외를 올린다."""
        try:
            with tempfile.TemporaryDirectory() as ocr_output_dir:
                self._convert(file_path, ocr_output_dir, force_ocr=True)
                extracted = self._load_results(
                    ocr_output_dir, os.path.basename(file_path)
                )
        except (_HybridConnectionError, _HybridParseError) as exc:
            logger.error(
                "[문서 추출 실패] OCR fallback 변환 실패: path=%s, error=%s",
                file_path,
                exc,
            )
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR) from exc

        if not self._extract_body(extracted).strip():
            logger.warning(
                "[문서 추출] OCR fallback 후에도 body 비어 있음: path=%s", file_path
            )
            raise AppException(ErrorCode.DOC_PDF_TEXT_TOO_SHORT)

        logger.info("[문서 추출] OCR fallback 성공: path=%s", file_path)
        return extracted

    def _extract_body(self, extracted: ExtractedDocument) -> str:
        """markdown → json 순서로 body 텍스트를 추출한다."""
        return (
            extract_body_from_markdown(extracted.markdown)
            or extract_body_from_json(extracted.json_data)
            or ""
        )

    def _convert(self, file_path: str, output_dir: str, *, force_ocr: bool) -> None:
        """
        odl.convert 호출. 실패 시 원인에 따라 내부 예외를 올린다.

          연결/서버 불능  → _HybridConnectionError
          문서 변환 실패  → _HybridParseError
        """
        url = self.ocr_hybrid_url if force_ocr else self.hybrid_url
        timeout = self.ocr_hybrid_timeout if force_ocr else self.hybrid_timeout
        label = "OCR" if force_ocr else "일반"

        kwargs = {
            "input_path": file_path,
            "output_dir": output_dir,
            "format": self.format,
            "image_output": self.image_output,
            "quiet": True,
        }

        if self.force_hybrid:
            kwargs["hybrid"] = self.hybrid_backend
            kwargs["hybrid_url"] = url
            kwargs["hybrid_timeout"] = str(timeout)

        try:
            odl.convert(**kwargs)
        except Exception as exc:
            exc_str = str(exc).lower()

            if any(
                kw in exc_str
                for kw in (
                    "connection",
                    "connect",
                    "refused",
                    "unreachable",
                    "unavailable",
                )
            ):
                logger.error(
                    "[문서 추출 실패] %s hybrid 연결 실패: path=%s, url=%s, error=%s",
                    label,
                    file_path,
                    url,
                    exc,
                )
                raise _HybridConnectionError(str(exc)) from exc

            if any(kw in exc_str for kw in ("timeout", "timed out")):
                logger.error(
                    "[문서 추출 실패] %s 경로 timeout: path=%s, url=%s, timeout=%s, error=%s",
                    label,
                    file_path,
                    url,
                    timeout,
                    exc,
                )
                # timeout은 서버는 살아있지만 문서 처리가 오래 걸린 것 → 파싱 실패로 분류
                raise _HybridParseError(str(exc)) from exc

            logger.error(
                "[문서 추출 실패] %s 경로 변환 오류: path=%s, url=%s, error=%s",
                label,
                file_path,
                url,
                exc,
                exc_info=True,
            )
            raise _HybridParseError(str(exc)) from exc

    def _load_results(
        self, output_dir: str, original_filename: str
    ) -> ExtractedDocument:
        stem = os.path.splitext(original_filename)[0]

        md_path = os.path.join(output_dir, f"{stem}.md")
        json_path = os.path.join(output_dir, f"{stem}.json")

        markdown = self._read_first_matching_file(output_dir, md_path, ".md")
        json_data = self._read_json_with_fallback(output_dir, json_path)

        return ExtractedDocument(markdown=markdown, json_data=json_data)

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
        candidate_paths: list[str] = []
        if os.path.exists(preferred_path):
            candidate_paths.append(preferred_path)
        candidate_paths.extend(
            os.path.join(output_dir, fname)
            for fname in os.listdir(output_dir)
            if fname.endswith(".json")
            and os.path.join(output_dir, fname) != preferred_path
        )

        for path in candidate_paths:
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("[문서 추출] json 파싱 실패: %s", path)

        return None
