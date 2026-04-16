"""domains/document/document_schema_resolver.py

normalized document cache 진입점.

역할:
    - ExtractedDocument → DocumentSchema 변환 결과를 파일 기반 cache에 저장/로드한다.
    - summary_process.py, group_document_indexing_service.py 양쪽에서 이 resolver를
      통해 DocumentSchema를 얻으며, 직접 extract/normalize를 호출하지 않는다.

재사용 조건 (세 조건 모두 충족 시 cache 재사용):
    1. schema_version 일치
    2. normalization_version 일치
    3. source fingerprint 일치

fingerprint 비교 전략 (fast path → slow path):
    1단계 — os.stat(size + mtime) 비교: 일치하면 sha256 계산 없이 즉시 재사용.
    2단계 — stat 불일치 시에만 sha256 포함 full fingerprint 계산 후 최종 판단.

cache lifecycle:
    - cache는 재생성 가능 자산이다. DB와 원본 파일이 source of truth다.
    - 문서 최종 삭제(DELETED) 시 cleanup_document_files task가 .json/.tmp/.lock을 정리한다.
    - 경로: NORMALIZED_DOCUMENT_DIR 환경변수 (기본 runtime/normalized_documents/)
"""

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
        stored_document = self.store.load(document_id)

        # ── 1단계: version/schema 검사 + stat fast path ──────────────────────
        # sha256 계산 전에 version 불일치 또는 stat 변경 여부를 먼저 확인한다.
        # stat(size+mtime)이 같으면 sha256 없이 cache hit.
        if not force_regenerate:
            needs_regen = _check_version_or_stat(
                stored_document=stored_document,
                file_path=file_path,
                expected_normalization_version=self.normalizer.normalization_version,
                expected_schema_version=_SCHEMA_VERSION,
            )
            if needs_regen is False:
                # stat hit: sha256 계산 없이 재사용
                logger.info(
                    "[normalized document] 재사용(stat hit): document_id=%s version=%s",
                    document_id,
                    stored_document.normalization_version,
                )
                return stored_document

        # ── 2단계: stat miss → full fingerprint(sha256) 계산 ─────────────────
        source_fingerprint = _build_source_fingerprint(file_path)

        if not self.store.should_regenerate(
            stored_document,
            expected_version=self.normalizer.normalization_version,
            expected_schema_version=_SCHEMA_VERSION,
            current_source_fingerprint=source_fingerprint,
            force_regenerate=force_regenerate,
        ):
            logger.info(
                "[normalized document] 재사용(sha256 hit): document_id=%s version=%s",
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


def _build_stat_fingerprint(file_path: str) -> dict[str, int | str]:
    """size + mtime 기반 경량 fingerprint. sha256 계산 없음."""
    stat_result = os.stat(file_path)
    return {
        "path": file_path,
        "size": stat_result.st_size,
        "mtime": int(stat_result.st_mtime),
    }


def _build_source_fingerprint(file_path: str) -> dict[str, int | str]:
    """size + mtime + sha256 full fingerprint. 저장 및 최종 비교에 사용."""
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


def _check_version_or_stat(
    *,
    stored_document: DocumentSchema | None,
    file_path: str,
    expected_normalization_version: str,
    expected_schema_version: str,
) -> bool | None:
    """version/schema 불일치 또는 stat 변경 여부를 빠르게 판단한다.

    Returns:
        True  — 재생성 필요 (version 불일치 또는 stat 변경)
        False — stat hit, 재사용 가능 (sha256 계산 불필요)
        None  — stored fingerprint에 stat 정보 없음, 2단계로 진행
    """
    if stored_document is None:
        return True

    if stored_document.schema_version != expected_schema_version:
        return True

    if stored_document.normalization_version != expected_normalization_version:
        return True

    stored_fp = dict(stored_document.metadata.get("source_file", {}) or {})
    stored_size = stored_fp.get("size")
    stored_mtime = stored_fp.get("mtime")

    if stored_size is None or stored_mtime is None:
        # stored fingerprint에 stat 없음 → full fingerprint로 판단
        return None

    try:
        stat_result = os.stat(file_path)
    except OSError:
        return True

    current_size = stat_result.st_size
    current_mtime = int(stat_result.st_mtime)

    if current_size == stored_size and current_mtime == stored_mtime:
        # stat 일치 → sha256 없이 재사용 가능
        return False

    # stat 불일치 → full fingerprint(sha256)로 최종 판단
    return True


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
