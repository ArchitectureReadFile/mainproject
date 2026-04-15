"""
tests/unit/test_normalized_document_fingerprint.py

normalized document fingerprint 최적화 테스트.

검증 계약:
    1. stored size/mtime가 같으면 sha256 계산 없이 cache hit
    2. size/mtime가 다르면 sha256 계산 경로로 진입
    3. 파일 내용 변경 시 (mtime 동일해도 sha256 다르면) regenerate
    4. normalization_version mismatch는 stat 검사 전에 재생성 결정
    5. schema_version mismatch는 stat 검사 전에 재생성 결정
    6. force_regenerate는 stat 검사 없이 바로 재생성
    7. stored fingerprint에 stat 정보 없으면 full fingerprint로 fallback
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

from domains.document.document_schema import DocumentSchema
from domains.document.document_schema_resolver import (
    DocumentSchemaResolver,
    _build_source_fingerprint,
    _build_stat_fingerprint,
    _check_version_or_stat,
)
from domains.document.normalized_document_store import NormalizedDocumentStore

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _make_stored_document(
    *,
    body_text: str = "본문",
    normalization_version: str = "v1",
    schema_version: str = "v1",
    source_file: dict | None = None,
) -> DocumentSchema:
    return DocumentSchema(
        source_type="odl",
        body_text=body_text,
        table_blocks=[],
        pages=[],
        metadata={
            "schema_version": schema_version,
            "normalization_version": normalization_version,
            "source_file": source_file or {},
        },
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── 1. stat hit: sha256 계산 없이 cache 재사용 ────────────────────────────────


class TestStatHitSkipsSha256:
    def test_sha256_not_called_when_stat_matches(self, tmp_path):
        """size/mtime가 일치하면 _compute_sha256이 호출되지 않는다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"content")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": "any_stored_hash",
            }
        )

        store = MagicMock(spec=NormalizedDocumentStore)
        store.load.return_value = stored
        extractor = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"

        resolver = DocumentSchemaResolver(
            extractor=extractor,
            normalizer=normalizer,
            store=store,
        )

        with patch(
            "domains.document.document_schema_resolver._compute_sha256"
        ) as mock_sha256:
            result = resolver.get_or_create(document_id=1, file_path=str(pdf))

        mock_sha256.assert_not_called()
        assert result is stored
        extractor.extract.assert_not_called()

    def test_cache_hit_returns_stored_document(self, tmp_path):
        """stat hit 경로에서 stored document가 그대로 반환된다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"cached content")
        stat = pdf.stat()

        stored = _make_stored_document(
            body_text="캐시 본문",
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": _sha256(b"cached content"),
            },
        )

        store = MagicMock(spec=NormalizedDocumentStore)
        store.load.return_value = stored
        extractor = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"

        resolver = DocumentSchemaResolver(
            extractor=extractor, normalizer=normalizer, store=store
        )
        result = resolver.get_or_create(document_id=2, file_path=str(pdf))

        assert result.body_text == "캐시 본문"
        extractor.extract.assert_not_called()


# ── 2. stat miss → sha256 계산 경로 진입 ─────────────────────────────────────


class TestStatMissTriggersFullFingerprint:
    def test_sha256_called_when_mtime_differs(self, tmp_path):
        """mtime이 다르면 _compute_sha256이 호출된다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"new content")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime) - 100,  # 다른 mtime
                "sha256": _sha256(b"old content"),
            }
        )

        store = MagicMock(spec=NormalizedDocumentStore)
        store.load.return_value = stored
        store.should_regenerate.return_value = True
        store.document_lock.return_value.__enter__ = MagicMock(return_value=None)
        store.document_lock.return_value.__exit__ = MagicMock(return_value=False)
        # lock 후 재확인에서도 regenerate
        store.load.side_effect = [stored, None]
        store.should_regenerate.side_effect = [True, True]

        extractor = MagicMock()
        extractor.extract.return_value = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"
        normalizer.normalize.return_value = _make_stored_document()

        resolver = DocumentSchemaResolver(
            extractor=extractor, normalizer=normalizer, store=store
        )

        with patch(
            "domains.document.document_schema_resolver._compute_sha256",
            return_value="new_sha256",
        ) as mock_sha256:
            resolver.get_or_create(document_id=3, file_path=str(pdf))

        mock_sha256.assert_called_once_with(str(pdf))

    def test_sha256_called_when_size_differs(self, tmp_path):
        """size가 다르면 _compute_sha256이 호출된다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"new content here")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size + 1,  # 다른 size
                "mtime": int(stat.st_mtime),
                "sha256": "old_hash",
            }
        )

        store = MagicMock(spec=NormalizedDocumentStore)
        store.load.side_effect = [stored, None]
        store.should_regenerate.side_effect = [True, True]
        store.document_lock.return_value.__enter__ = MagicMock(return_value=None)
        store.document_lock.return_value.__exit__ = MagicMock(return_value=False)

        extractor = MagicMock()
        extractor.extract.return_value = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"
        normalizer.normalize.return_value = _make_stored_document()

        resolver = DocumentSchemaResolver(
            extractor=extractor, normalizer=normalizer, store=store
        )

        with patch(
            "domains.document.document_schema_resolver._compute_sha256",
            return_value="new_hash",
        ) as mock_sha256:
            resolver.get_or_create(document_id=4, file_path=str(pdf))

        mock_sha256.assert_called_once_with(str(pdf))


# ── 3. 파일 변경 시 regenerate (stat miss + sha256 다름) ─────────────────────


class TestFileChangedTriggersRegenerate:
    def test_file_change_detected_and_regenerated(self, tmp_path):
        """파일이 변경되면 extractor가 호출되고 새 document가 저장된다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"original")
        stat_orig = pdf.stat()

        stored = _make_stored_document(
            body_text="원본 본문",
            source_file={
                "path": str(pdf),
                "size": stat_orig.st_size,
                "mtime": int(stat_orig.st_mtime),
                "sha256": _sha256(b"original"),
            },
        )

        store = NormalizedDocumentStore(base_dir=tmp_path / "cache")
        store.save(10, stored)

        # 파일 내용 변경
        pdf.write_bytes(b"modified content that is longer")
        new_document = _make_stored_document(body_text="새 본문")

        extractor = MagicMock()
        extractor.extract.return_value = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"
        normalizer.normalize.return_value = new_document

        resolver = DocumentSchemaResolver(
            extractor=extractor, normalizer=normalizer, store=store
        )
        result = resolver.get_or_create(document_id=10, file_path=str(pdf))

        extractor.extract.assert_called_once_with(str(pdf))
        assert result.body_text == "새 본문"


# ── 4·5. version/schema mismatch는 stat 전에 재생성 결정 ──────────────────────


class TestVersionMismatchTriggersRegenerateBeforeStat:
    def test_normalization_version_mismatch_regenerates_without_sha256(self, tmp_path):
        """normalization_version 불일치는 stat 검사 없이 바로 재생성된다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"content")
        stat = pdf.stat()

        stored = _make_stored_document(
            normalization_version="v0",  # 구버전
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": _sha256(b"content"),
            },
        )

        store = MagicMock(spec=NormalizedDocumentStore)
        store.load.side_effect = [stored, None]
        store.should_regenerate.side_effect = [True, True]
        store.document_lock.return_value.__enter__ = MagicMock(return_value=None)
        store.document_lock.return_value.__exit__ = MagicMock(return_value=False)

        extractor = MagicMock()
        extractor.extract.return_value = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"  # 새 버전
        normalizer.normalize.return_value = _make_stored_document()

        resolver = DocumentSchemaResolver(
            extractor=extractor, normalizer=normalizer, store=store
        )

        with patch(
            "domains.document.document_schema_resolver._compute_sha256"
        ) as mock_sha256:
            resolver.get_or_create(document_id=5, file_path=str(pdf))

        # version 불일치이므로 stat에서 True 반환 → sha256은 그 이후에 호출됨
        # (2단계 full fingerprint 경로로 진입)
        mock_sha256.assert_called_once()
        extractor.extract.assert_called_once()

    def test_schema_version_mismatch_also_regenerates(self, tmp_path):
        """schema_version 불일치도 재생성을 트리거한다."""
        result = _check_version_or_stat(
            stored_document=_make_stored_document(schema_version="v0"),
            file_path="/irrelevant",
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        assert result is True


# ── 6. force_regenerate ───────────────────────────────────────────────────────


class TestForceRegenerate:
    def test_force_regenerate_skips_stat_check(self, tmp_path):
        """force_regenerate=True이면 stat 검사 없이 바로 sha256 → 재생성 경로."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"content")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": _sha256(b"content"),
            }
        )

        store = MagicMock(spec=NormalizedDocumentStore)
        store.load.side_effect = [stored, None]
        store.should_regenerate.side_effect = [True, True]
        store.document_lock.return_value.__enter__ = MagicMock(return_value=None)
        store.document_lock.return_value.__exit__ = MagicMock(return_value=False)

        extractor = MagicMock()
        extractor.extract.return_value = MagicMock()
        normalizer = MagicMock()
        normalizer.normalization_version = "v1"
        normalizer.normalize.return_value = _make_stored_document()

        resolver = DocumentSchemaResolver(
            extractor=extractor, normalizer=normalizer, store=store
        )
        resolver.get_or_create(document_id=6, file_path=str(pdf), force_regenerate=True)

        extractor.extract.assert_called_once()


# ── 7. stored fingerprint에 stat 없으면 full fingerprint fallback ─────────────


class TestNoStatInStoredFingerprintFallsBackToFullFingerprint:
    def test_missing_stat_in_stored_triggers_sha256(self, tmp_path):
        """stored fingerprint에 size/mtime이 없으면 full fingerprint로 판단한다."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"content")

        result = _check_version_or_stat(
            stored_document=_make_stored_document(
                source_file={"path": str(pdf), "sha256": "some_hash"}  # size/mtime 없음
            ),
            file_path=str(pdf),
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        # None 반환 → 2단계(full fingerprint) 경로로 진행
        assert result is None

    def test_empty_source_file_triggers_none(self, tmp_path):
        """source_file이 빈 dict이면 None 반환."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"content")

        result = _check_version_or_stat(
            stored_document=_make_stored_document(source_file={}),
            file_path=str(pdf),
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        assert result is None


# ── _check_version_or_stat 단위 테스트 ───────────────────────────────────────


class TestCheckVersionOrStat:
    def test_returns_true_when_stored_is_none(self, tmp_path):
        result = _check_version_or_stat(
            stored_document=None,
            file_path=str(tmp_path / "x.pdf"),
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        assert result is True

    def test_returns_false_when_stat_matches(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"data")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": "any",
            }
        )
        result = _check_version_or_stat(
            stored_document=stored,
            file_path=str(pdf),
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        assert result is False

    def test_returns_true_when_mtime_differs(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"data")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime) + 1,
                "sha256": "any",
            }
        )
        result = _check_version_or_stat(
            stored_document=stored,
            file_path=str(pdf),
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        assert result is True

    def test_returns_true_when_size_differs(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"data")
        stat = pdf.stat()

        stored = _make_stored_document(
            source_file={
                "path": str(pdf),
                "size": stat.st_size + 10,
                "mtime": int(stat.st_mtime),
                "sha256": "any",
            }
        )
        result = _check_version_or_stat(
            stored_document=stored,
            file_path=str(pdf),
            expected_normalization_version="v1",
            expected_schema_version="v1",
        )
        assert result is True


# ── fingerprint 헬퍼 단위 테스트 ─────────────────────────────────────────────


class TestFingerprintHelpers:
    def test_stat_fingerprint_has_no_sha256(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"data")
        fp = _build_stat_fingerprint(str(pdf))
        assert "sha256" not in fp
        assert "size" in fp
        assert "mtime" in fp

    def test_source_fingerprint_has_sha256(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"data")
        fp = _build_source_fingerprint(str(pdf))
        assert "sha256" in fp
        assert fp["sha256"] == _sha256(b"data")

    def test_source_fingerprint_sha256_changes_with_content(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"version_a")
        fp_a = _build_source_fingerprint(str(pdf))
        pdf.write_bytes(b"version_b")
        fp_b = _build_source_fingerprint(str(pdf))
        assert fp_a["sha256"] != fp_b["sha256"]
