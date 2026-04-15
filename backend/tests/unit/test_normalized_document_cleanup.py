"""
tests/unit/test_normalized_document_cleanup.py

normalized document cache cleanup lifecycle 테스트.

검증 계약:
    1. cleanup 시 normalized .json이 삭제 대상에 포함됨
    2. .json.tmp / .lock 파일도 삭제 대상에 포함됨
    3. 파일이 없어도 예외 없이 skip
    4. 기존 stored_path / preview_pdf_path cleanup 계약을 깨지 않음
    5. get_cleanup_paths가 [.json, .json.tmp, .lock] 세 경로를 반환
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ── 1·2·3. _get_document_file_paths에 normalized cache 경로 포함 ──────────────


class TestGetDocumentFilePathsIncludesNormalizedCache:
    def _make_document(self, doc_id: int, stored_path: str | None = None) -> MagicMock:
        doc = MagicMock()
        doc.id = doc_id
        doc.stored_path = stored_path
        doc.preview_pdf_path = None
        return doc

    def test_normalized_json_included_in_paths(self, tmp_path):
        """cleanup 대상 경로에 normalized .json이 포함되는지 확인."""
        from domains.document.file_cleanup_task import _get_document_file_paths
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        doc = self._make_document(doc_id=10)

        with patch(
            "domains.document.file_cleanup_task.NormalizedDocumentStore",
            return_value=store,
        ):
            paths = _get_document_file_paths(doc)

        assert str(store.get_path(10)) in paths

    def test_tmp_and_lock_included_in_paths(self, tmp_path):
        """.json.tmp / .lock 경로도 cleanup 대상에 포함되는지 확인."""
        from domains.document.file_cleanup_task import _get_document_file_paths
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        doc = self._make_document(doc_id=20)

        with patch(
            "domains.document.file_cleanup_task.NormalizedDocumentStore",
            return_value=store,
        ):
            paths = _get_document_file_paths(doc)

        assert str(store.get_tmp_path(20)) in paths
        assert str(store.get_lock_path(20)) in paths

    def test_missing_cache_files_do_not_raise(self, tmp_path):
        """cache 파일이 존재하지 않아도 예외 없이 skip."""
        from domains.document.file_cleanup_task import _get_document_file_paths
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        doc = self._make_document(doc_id=30)

        with patch(
            "domains.document.file_cleanup_task.NormalizedDocumentStore",
            return_value=store,
        ):
            paths = _get_document_file_paths(doc)

        # 경로는 반환되지만 실제 파일이 없으므로 cleanup task에서 skip됨
        assert isinstance(paths, list)

    def test_stored_path_still_included(self, tmp_path):
        """기존 stored_path 계약이 깨지지 않는지 확인."""
        from domains.document.file_cleanup_task import _get_document_file_paths
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        doc = self._make_document(doc_id=40, stored_path="/app/runtime/uploads/doc.pdf")

        with patch(
            "domains.document.file_cleanup_task.NormalizedDocumentStore",
            return_value=store,
        ):
            paths = _get_document_file_paths(doc)

        assert "/app/runtime/uploads/doc.pdf" in paths

    def test_no_duplicates_in_paths(self, tmp_path):
        """경로 목록에 중복이 없는지 확인."""
        from domains.document.file_cleanup_task import _get_document_file_paths
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        doc = self._make_document(
            doc_id=50, stored_path="/app/runtime/uploads/doc50.pdf"
        )

        with patch(
            "domains.document.file_cleanup_task.NormalizedDocumentStore",
            return_value=store,
        ):
            paths = _get_document_file_paths(doc)

        assert len(paths) == len(set(paths))


# ── 4. cleanup_document_files task idempotent 동작 ───────────────────────────


class TestCleanupDocumentFilesWithNormalizedCache:
    def test_existing_cache_file_is_deleted(self, tmp_path):
        """존재하는 normalized cache 파일이 실제로 삭제되는지 확인."""
        from domains.document.file_cleanup_task import cleanup_document_files
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        cache_path = store.get_path(60)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('{"source_type": "odl"}', encoding="utf-8")
        assert cache_path.exists()

        mock_doc = MagicMock()
        mock_doc.id = 60
        mock_doc.stored_path = None
        mock_doc.preview_pdf_path = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        with (
            patch(
                "domains.document.file_cleanup_task.SessionLocal", return_value=mock_db
            ),
            patch(
                "domains.document.file_cleanup_task.NormalizedDocumentStore",
                return_value=store,
            ),
        ):
            result = cleanup_document_files(60)

        assert not cache_path.exists()
        assert result["cleaned"] is True
        assert result["deleted_path_count"] >= 1

    def test_missing_cache_file_is_skipped_not_raised(self, tmp_path):
        """cache 파일이 없어도 예외 없이 skip 처리되는지 확인."""
        from domains.document.file_cleanup_task import cleanup_document_files
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        # 파일 생성 없이 바로 cleanup 호출

        mock_doc = MagicMock()
        mock_doc.id = 70
        mock_doc.stored_path = None
        mock_doc.preview_pdf_path = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        with (
            patch(
                "domains.document.file_cleanup_task.SessionLocal", return_value=mock_db
            ),
            patch(
                "domains.document.file_cleanup_task.NormalizedDocumentStore",
                return_value=store,
            ),
        ):
            result = cleanup_document_files(70)

        assert result["cleaned"] is True
        assert result["skipped_path_count"] >= 3  # .json, .tmp, .lock 모두 skip

    def test_tmp_and_lock_files_deleted(self, tmp_path):
        """.json.tmp / .lock 파일이 존재하면 함께 삭제되는지 확인."""
        from domains.document.file_cleanup_task import cleanup_document_files
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        tmp_file = store.get_tmp_path(80)
        lock_file = store.get_lock_path(80)
        tmp_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text("partial", encoding="utf-8")
        lock_file.write_text("", encoding="utf-8")

        mock_doc = MagicMock()
        mock_doc.id = 80
        mock_doc.stored_path = None
        mock_doc.preview_pdf_path = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        with (
            patch(
                "domains.document.file_cleanup_task.SessionLocal", return_value=mock_db
            ),
            patch(
                "domains.document.file_cleanup_task.NormalizedDocumentStore",
                return_value=store,
            ),
        ):
            result = cleanup_document_files(80)

        assert not tmp_file.exists()
        assert not lock_file.exists()
        assert result["deleted_path_count"] >= 2


# ── 5. get_cleanup_paths 계약 ─────────────────────────────────────────────────


class TestGetCleanupPaths:
    def test_returns_three_paths(self, tmp_path):
        """get_cleanup_paths가 [.json, .json.tmp, .lock] 세 경로를 반환하는지 확인."""
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        paths = store.get_cleanup_paths(99)

        assert len(paths) == 3
        path_strs = [str(p) for p in paths]
        assert str(store.get_path(99)) in path_strs
        assert str(store.get_tmp_path(99)) in path_strs
        assert str(store.get_lock_path(99)) in path_strs

    def test_paths_use_correct_document_id(self, tmp_path):
        """반환된 경로가 올바른 document_id를 사용하는지 확인."""
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        paths = store.get_cleanup_paths(123)

        for path in paths:
            assert "123" in path.name

    def test_does_not_create_files(self, tmp_path):
        """get_cleanup_paths 호출 자체가 파일을 생성하지 않는지 확인."""
        from domains.document.normalized_document_store import NormalizedDocumentStore

        store = NormalizedDocumentStore(base_dir=tmp_path)
        store.get_cleanup_paths(456)

        assert not any(tmp_path.iterdir())
