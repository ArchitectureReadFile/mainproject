from __future__ import annotations

import hashlib
import logging
import os

from domains.document.document_schema import DocumentSchema
from domains.document.extract_service import DocumentExtractService
from domains.document.normalize_service import DocumentNormalizeService
from domains.document.normalized_document_store import NormalizedDocumentStore

logger = logging.getLogger(__name__)
_SCHEMA_VERSION = "v1"


class DocumentSchemaResolver:
    def __init__(
        self,
        *,
        extractor: DocumentExtractService | None = None,
        normalizer: DocumentNormalizeService | None = None,
        store: NormalizedDocumentStore | None = None,
    ) -> None:
        self.extractor = extractor or DocumentExtractService()
        self.normalizer = normalizer or DocumentNormalizeService()
        self.store = store or NormalizedDocumentStore()

    def get_or_create(
        self,
        *,
        document_id: int,
        file_path: str,
        force_regenerate: bool = False,
    ) -> DocumentSchema:
        source_fingerprint = _build_source_fingerprint(file_path)
        stored_document = self.store.load(document_id)
        if not self.store.should_regenerate(
            stored_document,
            expected_version=self.normalizer.normalization_version,
            expected_schema_version=_SCHEMA_VERSION,
            current_source_fingerprint=source_fingerprint,
            force_regenerate=force_regenerate,
        ):
            logger.info(
                "[normalized document] 재사용: document_id=%s version=%s",
                document_id,
                stored_document.normalization_version,
            )
            return stored_document

        with self.store.document_lock(document_id):
            # 다른 워커가 lock 획득 전에 저장했을 수 있으므로 다시 확인한다.
            stored_document = self.store.load(document_id)
            if not self.store.should_regenerate(
                stored_document,
                expected_version=self.normalizer.normalization_version,
                expected_schema_version=_SCHEMA_VERSION,
                current_source_fingerprint=source_fingerprint,
                force_regenerate=force_regenerate,
            ):
                logger.info(
                    "[normalized document] lock 후 재사용: document_id=%s version=%s",
                    document_id,
                    stored_document.normalization_version,
                )
                return stored_document

            logger.info(
                "[normalized document] 재생성: document_id=%s reason=%s",
                document_id,
                _build_regeneration_reason(
                    stored_document=stored_document,
                    expected_normalization_version=self.normalizer.normalization_version,
                    expected_schema_version=_SCHEMA_VERSION,
                    source_fingerprint=source_fingerprint,
                    force_regenerate=force_regenerate,
                ),
            )

            extracted = self.extractor.extract(file_path)
            normalized = self.normalizer.normalize(extracted)
            normalized.metadata["schema_version"] = _SCHEMA_VERSION
            normalized.metadata["normalization_version"] = (
                self.normalizer.normalization_version
            )
            normalized.metadata["source_file"] = source_fingerprint
            self.store.save(document_id, normalized)
            return normalized


def _build_source_fingerprint(file_path: str) -> dict[str, int | str]:
    stat_result = os.stat(file_path)
    return {
        "path": file_path,
        "size": stat_result.st_size,
        "mtime": int(stat_result.st_mtime),
        "sha256": _compute_sha256(file_path),
    }


def _compute_sha256(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_regeneration_reason(
    *,
    stored_document: DocumentSchema | None,
    expected_normalization_version: str,
    expected_schema_version: str,
    source_fingerprint: dict[str, int | str],
    force_regenerate: bool,
) -> str:
    if stored_document is None:
        return "missing"
    if force_regenerate:
        return "forced"
    if stored_document.schema_version != expected_schema_version:
        return (
            "schema_version_mismatch:"
            f"{stored_document.schema_version}->{expected_schema_version}"
        )
    if stored_document.normalization_version != expected_normalization_version:
        return (
            "normalization_version_mismatch:"
            f"{stored_document.normalization_version}"
            f"->{expected_normalization_version}"
        )
    stored_fingerprint = dict(stored_document.metadata.get("source_file", {}) or {})
    if stored_fingerprint != source_fingerprint:
        return "source_fingerprint_changed"
    return "unknown"
