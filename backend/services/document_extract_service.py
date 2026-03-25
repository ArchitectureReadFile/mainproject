"""
services/document_extract_service.py

opendataloader-pdf (Java-only) 기반 문서 추출 서비스.
PDF 파일 경로 또는 bytes를 받아 ExtractedDocument를 반환한다.

출력 포맷:
    format="markdown,json"
    image_output="off"   (이미지 추출 비활성화)
    quiet=True           (콘솔 로그 억제)
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass

import opendataloader_pdf as odl

from errors import AppException, ErrorCode

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocument:
    markdown: str  # 본문 구조 원본
    json_data: dict | None  # 표/구조 원본
    plain_text: str  # fallback용 markdown 평문화 값


class DocumentExtractService:
    def extract(self, file_path: str) -> ExtractedDocument:
        """
        PDF 파일 경로를 받아 ExtractedDocument를 반환한다.
        추출 결과 파일은 임시 디렉터리에 쓰고 읽은 뒤 삭제한다.
        """
        if not os.path.exists(file_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

        with tempfile.TemporaryDirectory() as output_dir:
            try:
                odl.convert(
                    input_path=file_path,
                    output_dir=output_dir,
                    format="markdown,json",
                    image_output="off",
                    quiet=True,
                )
            except Exception as exc:
                logger.error(
                    "[문서 추출 실패] path=%s, error=%s", file_path, exc, exc_info=True
                )
                raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR)

            return self._load_results(output_dir, os.path.basename(file_path))

    def extract_bytes(
        self, file_bytes: bytes, filename: str = "document.pdf"
    ) -> ExtractedDocument:
        """
        bytes 입력을 임시 파일로 저장한 뒤 extract()에 위임한다.
        채팅 첨부파일 등 파일 경로 없이 bytes만 있는 소비처에서 사용한다.
        """
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

    def _load_results(
        self, output_dir: str, original_filename: str
    ) -> ExtractedDocument:
        """
        output_dir에서 .md / .json 결과 파일을 읽어 ExtractedDocument로 조립한다.
        파일명 stem은 입력 PDF stem과 동일하다.
        """
        stem = os.path.splitext(original_filename)[0]

        md_path = os.path.join(output_dir, f"{stem}.md")
        json_path = os.path.join(output_dir, f"{stem}.json")

        # markdown 읽기
        markdown = ""
        if os.path.exists(md_path):
            with open(md_path, encoding="utf-8") as f:
                markdown = f.read()
        else:
            # 디렉터리에서 첫 번째 .md 파일 fallback
            for fname in os.listdir(output_dir):
                if fname.endswith(".md"):
                    with open(os.path.join(output_dir, fname), encoding="utf-8") as f:
                        markdown = f.read()
                    break

        if not markdown.strip():
            logger.warning("[문서 추출] markdown 결과가 비어 있음: stem=%s", stem)
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        # json 읽기 (없어도 계속 진행)
        json_data: dict | None = None
        if os.path.exists(json_path):
            try:
                with open(json_path, encoding="utf-8") as f:
                    json_data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("[문서 추출] json 파싱 실패: %s", json_path)
        else:
            for fname in os.listdir(output_dir):
                if fname.endswith(".json"):
                    try:
                        with open(
                            os.path.join(output_dir, fname), encoding="utf-8"
                        ) as f:
                            json_data = json.load(f)
                    except json.JSONDecodeError:
                        pass
                    break

        plain_text = _markdown_to_plain(markdown)

        return ExtractedDocument(
            markdown=markdown,
            json_data=json_data,
            plain_text=plain_text,
        )


def _markdown_to_plain(markdown: str) -> str:
    """markdown을 평문화한다. 표 행(| ... |)은 제거한다."""
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        # 표 행 제거
        if stripped.startswith("|"):
            continue
        # 헤딩 기호 제거
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        lines.append(stripped)
    return "\n".join(lines).strip()
