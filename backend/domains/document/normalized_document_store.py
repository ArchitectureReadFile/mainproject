"""domains/document/normalized_document_store.py

normalized document cache 저장소.

역할:
    - DocumentSchema를 JSON 파일로 저장하고 로드한다.
    - 저장 위치: NORMALIZED_DOCUMENT_DIR 환경변수 (기본 runtime/normalized_documents/)
    - 파일 구조: {document_id}.json / {document_id}.json.tmp / {document_id}.lock

재생성 판단 (should_regenerate):
    - force_regenerate, document 없음, schema_version 불일치,
      normalization_version 불일치, source fingerprint 불일치 중 하나라도 True
    - fingerprint fast path(stat) 판단은 resolver(document_schema_resolver.py)를 참고

cache lifecycle:
    - 재생성 가능 자산. 소실되면 다음 extract/normalize 시 자동 복구된다.
    - 문서 최종 삭제 시 cleanup_document_files task에서 get_cleanup_paths()를 통해 정리된다.
    - .json.tmp: save() 시 atomic write 중간 파일. 정상 완료 시 정리된다.
    - .lock: fcntl 기반 동시 작성 차단용. 중단 시 남을 수 있으며 안전하게 재사용 가능하다.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
from pathlib import Path

from domains.document.document_schema import DocumentSchema

logger = logging.getLogger(__name__)


class NormalizedDocumentStore:
    BASE_DIR = os.getenv("NORMALIZED_DOCUMENT_DIR", "runtime/normalized_documents")

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or self.BASE_DIR)

    def load(self, document_id: int) -> DocumentSchema | None:
        path = self.get_path(document_id)
        if not path.exists():
            return None

        try:
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "[normalized document] load 실패: document_id=%s path=%s error=%s",
                document_id,
                path,
                exc,
            )
            return None

        if not isinstance(payload, dict):
            logger.warning(
                "[normalized document] payload 타입 오류: document_id=%s path=%s",
                document_id,
                path,
            )
            return None
        return DocumentSchema.from_dict(payload)

    def save(self, document_id: int, document: DocumentSchema) -> Path:
        path = self.get_path(document_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.get_tmp_path(document_id)
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return path

    def get_path(self, document_id: int) -> Path:
        return self.base_dir / f"{document_id}.json"

    def get_tmp_path(self, document_id: int) -> Path:
        return self.base_dir / f"{document_id}.json.tmp"

    def get_lock_path(self, document_id: int) -> Path:
        return self.base_dir / f"{document_id}.lock"

    def get_cleanup_paths(self, document_id: int) -> list[Path]:
        """document_id 기준 cleanup 대상 파일 목록을 반환한다.

        실제 존재 여부는 판단하지 않으며,
        호출자가 skip 또는 remove를 선택한다.
        목록: [.json, .json.tmp, .lock]
        """
        return [
            self.get_path(document_id),
            self.get_tmp_path(document_id),
            self.get_lock_path(document_id),
        ]

    @contextlib.contextmanager
    def document_lock(self, document_id: int):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.get_lock_path(document_id)
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def should_regenerate(
        self,
        document: DocumentSchema | None,
        *,
        expected_version: str,
        expected_schema_version: str | None = None,
        current_source_fingerprint: dict | None = None,
        force_regenerate: bool = False,
    ) -> bool:
        if force_regenerate:
            return True
        if document is None:
            return True
        if (
            expected_schema_version is not None
            and document.schema_version != expected_schema_version
        ):
            return True
        if document.normalization_version != expected_version:
            return True
        if current_source_fingerprint is None:
            return False
        stored_fingerprint = dict(document.metadata.get("source_file", {}) or {})
        return stored_fingerprint != current_source_fingerprint
