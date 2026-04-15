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
