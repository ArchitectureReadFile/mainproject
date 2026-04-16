from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time

from domains.document.repository import DocumentRepository
from errors import AppException, ErrorCode
from models.model import Document, DocumentPreviewStatus

logger = logging.getLogger(__name__)

_STDERR_LOG_MAX = 5000
_DEFAULT_TIMEOUT = int(os.environ.get("DOC_PREVIEW_TIMEOUT_SECONDS", "180"))
_DEFAULT_OFFICE_BIN = os.environ.get("LIBREOFFICE_BIN", "soffice")
_PROCESSING_WAIT_SECONDS = float(
    os.environ.get("DOC_PREVIEW_PROCESSING_WAIT_SECONDS", "30")
)
_PROCESSING_POLL_INTERVAL = float(
    os.environ.get("DOC_PREVIEW_POLL_INTERVAL_SECONDS", "1")
)


class DocumentPreviewService:
    def __init__(self, repository: DocumentRepository):
        self.repository = repository
        self._timeout = _DEFAULT_TIMEOUT
        self._office_bin = _DEFAULT_OFFICE_BIN

    def ensure_preview_pdf(self, document: Document) -> str:
        """
        문서의 preview PDF 경로를 보장해 반환

        처리 규칙:
        - 이미 READY 이고 파일이 존재하면 그대로 반환
        - 다른 워커가 PROCESSING 중이면 잠시 기다렸다가 결과를 재사용
        - 원본이 PDF면 stored_path 를 preview_pdf_path 로 사용
        - 비PDF면 LibreOffice headless 변환을 수행
        - 실패 상세는 로그에만 남기고 DB에는 상태만 반영
        """
        try:
            existing_path = (document.preview_pdf_path or "").strip()

            if (
                document.preview_status == DocumentPreviewStatus.READY
                and existing_path
                and os.path.exists(existing_path)
            ):
                return existing_path

            if document.preview_status == DocumentPreviewStatus.PROCESSING:
                waited_path = self._wait_until_processing_finishes(document.id)
                if waited_path:
                    return waited_path

            self._assert_source_exists(document)

            self.repository.update_preview_status(
                document.id,
                DocumentPreviewStatus.PROCESSING,
            )
            self.repository.db.commit()

            if self._is_pdf_original(document):
                preview_path = document.stored_path
            else:
                preview_path = self._convert_to_pdf(document)

            self.repository.update_preview_status(
                document.id,
                DocumentPreviewStatus.READY,
                preview_pdf_path=preview_path,
            )
            self.repository.db.commit()

            document.preview_status = DocumentPreviewStatus.READY
            document.preview_pdf_path = preview_path
            return preview_path

        except AppException:
            self.repository.db.rollback()
            self.repository.update_preview_status(
                document.id,
                DocumentPreviewStatus.FAILED,
            )
            self.repository.db.commit()
            document.preview_status = DocumentPreviewStatus.FAILED
            raise

        except Exception as exc:
            self.repository.db.rollback()
            logger.error(
                "[preview 변환 실패] doc_id=%s file=%s error=%s",
                document.id,
                document.original_filename,
                exc,
                exc_info=True,
            )
            self.repository.update_preview_status(
                document.id,
                DocumentPreviewStatus.FAILED,
            )
            self.repository.db.commit()
            document.preview_status = DocumentPreviewStatus.FAILED
            raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR) from exc

    def _wait_until_processing_finishes(self, document_id: int) -> str | None:
        """
        다른 워커가 preview PDF 를 만드는 중이면 잠시 기다렸다가 결과를 재사용

        반환:
        - READY 상태가 되고 파일이 존재하면 해당 경로
        - FAILED 상태가 되면 예외
        - 제한 시간 안에 준비되지 않으면 None
        """
        deadline = time.monotonic() + _PROCESSING_WAIT_SECONDS

        while time.monotonic() < deadline:
            # 세션이 기억하고 있던 객체 캐시를 만료시키고
            # 매 poll 마다 세션 캐시를 비우고 DB 최신값을 다시 읽음
            self.repository.db.expire_all()

            current = self.repository.get_by_id(document_id)
            if current is None:
                raise AppException(ErrorCode.DOC_NOT_FOUND)

            current_path = (current.preview_pdf_path or "").strip()

            if (
                current.preview_status == DocumentPreviewStatus.READY
                and current_path
                and os.path.exists(current_path)
            ):
                return current_path

            if current.preview_status == DocumentPreviewStatus.FAILED:
                raise AppException(ErrorCode.DOC_INTERNAL_PARSE_ERROR)

            if current.preview_status != DocumentPreviewStatus.PROCESSING:
                return None

            time.sleep(_PROCESSING_POLL_INTERVAL)

        logger.warning(
            "[preview 처리 대기 timeout] doc_id=%s wait=%.1fs",
            document_id,
            _PROCESSING_WAIT_SECONDS,
        )
        return None

    def _assert_source_exists(self, document: Document) -> None:
        """원본 파일이 실제로 존재하는지 검증"""
        if not document.stored_path or not os.path.exists(document.stored_path):
            raise AppException(ErrorCode.FILE_NOT_FOUND)

    def _is_pdf_original(self, document: Document) -> bool:
        """원본이 PDF인지 MIME 타입과 확장자로 판별"""
        content_type = (document.original_content_type or "").lower()
        ext = os.path.splitext(document.original_filename or "")[1].lower()
        return content_type == "application/pdf" or ext == ".pdf"

    def _convert_to_pdf(self, document: Document) -> str:
        """비PDF 원본을 LibreOffice headless 로 PDF로 변환"""
        office_bin = shutil.which(self._office_bin)
        if not office_bin:
            raise RuntimeError(
                f"LibreOffice 실행 파일을 찾을 수 없습니다: {self._office_bin}"
            )

        preview_path = self._build_preview_pdf_path(document)
        preview_dir = os.path.dirname(preview_path)
        os.makedirs(preview_dir, exist_ok=True)

        tag = f"doc_id={document.id} file={os.path.basename(document.stored_path)}"
        convert_env = os.environ.copy()
        convert_env["HOME"] = "/tmp"
        convert_env["LANG"] = convert_env.get("LANG", "ko_KR.UTF-8")
        convert_env["LC_ALL"] = convert_env.get("LC_ALL", "ko_KR.UTF-8")

        with (
            tempfile.TemporaryDirectory() as output_dir,
            tempfile.TemporaryDirectory() as profile_dir,
        ):
            try:
                proc = subprocess.run(
                    [
                        office_bin,
                        "--headless",
                        f"-env:UserInstallation=file://{profile_dir}",
                        "--convert-to",
                        "pdf:writer_pdf_Export",
                        "--outdir",
                        output_dir,
                        document.stored_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    env=convert_env,
                )
            except subprocess.TimeoutExpired as exc:
                logger.error(
                    "[preview 변환 timeout] %s timeout=%ds",
                    tag,
                    self._timeout,
                )
                raise RuntimeError("문서 preview PDF 변환 timeout") from exc

            if proc.returncode != 0:
                self._log_failure(tag, proc)
                raise RuntimeError(
                    f"문서 preview PDF 변환 실패 (exit={proc.returncode})"
                )

            generated_pdf = self._find_generated_pdf(output_dir)
            if not generated_pdf:
                self._log_failure(tag, proc)
                logger.error(
                    "[preview 변환 결과 없음] %s output_dir=%s files=%s",
                    tag,
                    output_dir,
                    os.listdir(output_dir),
                )
                raise RuntimeError("문서 preview PDF 결과 파일을 찾을 수 없습니다.")

            if os.path.exists(preview_path):
                os.remove(preview_path)

            shutil.move(generated_pdf, preview_path)

        logger.info(
            "[preview 변환 완료] doc_id=%s preview=%s",
            document.id,
            preview_path,
        )
        return preview_path

    def _build_preview_pdf_path(self, document: Document) -> str:
        """문서별 고정 preview PDF 경로를 생성"""
        source_dir = os.path.dirname(document.stored_path)
        preview_dir = os.path.join(source_dir, "previews")
        filename = f"doc_{document.id}_preview.pdf"
        return os.path.join(preview_dir, filename)

    @staticmethod
    def _find_generated_pdf(output_dir: str) -> str | None:
        """변환 결과 디렉터리에서 생성된 PDF 하나를 찾아 반환"""
        for name in os.listdir(output_dir):
            if name.lower().endswith(".pdf"):
                return os.path.join(output_dir, name)
        return None

    @staticmethod
    def _log_failure(tag: str, proc: subprocess.CompletedProcess) -> None:
        """변환 subprocess 실패 로그를 기록"""
        stderr_out = proc.stderr.strip()
        stdout_out = proc.stdout.strip()
        logger.error(
            "[preview 변환 실패] %s exit=%d\n"
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
