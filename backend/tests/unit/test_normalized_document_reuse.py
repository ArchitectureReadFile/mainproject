from __future__ import annotations

import hashlib
import json
from pathlib import Path

from domains.document.document_schema import (
    DocumentPage,
    DocumentSchema,
    DocumentTableBlock,
)
from domains.document.document_schema_resolver import DocumentSchemaResolver
from domains.document.extract_service import ExtractedDocument
from domains.document.normalized_document_store import NormalizedDocumentStore
from domains.document.summary_process import ProcessService
from domains.rag import group_document_indexing_service as indexing_module
from models.model import DocumentStatus


def _document_schema(
    *,
    body_text: str = "본문",
    schema_version: str = "v1",
    version: str = "v1",
    source_type: str = "odl",
    source_file: dict | None = None,
) -> DocumentSchema:
    return DocumentSchema(
        source_type=source_type,
        body_text=body_text,
        table_blocks=[
            DocumentTableBlock(
                table_id="table:0",
                text="[표 1]\ncol1 | col2",
                row_count=1,
                metadata={"kind": "simple"},
            )
        ],
        pages=[
            DocumentPage(
                page_number=1,
                text=body_text,
                table_ids=["table:0"],
                metadata={"estimated": True},
            )
        ],
        metadata={
            "schema_version": schema_version,
            "extraction_source": source_type,
            "has_tables": True,
            "page_count": 1,
            "body_char_count": len(body_text),
            "table_count": 1,
            "normalization_version": version,
            "source_file": source_file or {},
        },
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class StubExtractor:
    def __init__(self, extracted: ExtractedDocument | None = None):
        self.extracted = extracted or ExtractedDocument(
            markdown="생성된 본문",
            json_data={"kids": []},
            source_type="odl",
        )
        self.calls: list[str] = []

    def extract(self, file_path: str) -> ExtractedDocument:
        self.calls.append(file_path)
        return self.extracted


class StubNormalizer:
    def __init__(self, document: DocumentSchema | None = None, version: str = "v1"):
        self.document = document or _document_schema(version=version)
        self.normalization_version = version
        self.calls: list[ExtractedDocument] = []

    def normalize(self, extracted: ExtractedDocument) -> DocumentSchema:
        self.calls.append(extracted)
        return self.document


def test_document_schema_store_round_trip(tmp_path):
    store = NormalizedDocumentStore(base_dir=tmp_path)
    original = _document_schema(
        body_text="라운드트립 본문",
        source_file={"size": 10, "mtime": 123, "sha256": "abc"},
    )

    saved_path = store.save(101, original)
    loaded = store.load(101)

    assert saved_path == tmp_path / "101.json"
    assert loaded is not None
    assert loaded.to_dict() == original.to_dict()
    raw_payload = json.loads(saved_path.read_text(encoding="utf-8"))
    assert raw_payload["source_type"] == "odl"
    assert raw_payload["body_text"] == "라운드트립 본문"
    assert raw_payload["schema_version"] == "v1"
    assert raw_payload["normalization_version"] == "v1"
    assert raw_payload["metadata"]["schema_version"] == "v1"
    assert raw_payload["metadata"]["normalization_version"] == "v1"
    assert not store.get_tmp_path(101).exists()


def test_document_schema_from_dict_populates_default_schema_version():
    loaded = DocumentSchema.from_dict(
        {
            "source_type": "odl",
            "body_text": "본문",
            "table_blocks": [],
            "pages": [],
            "metadata": {"normalization_version": "v1"},
        }
    )

    assert loaded.schema_version == "v1"
    assert loaded.normalization_version == "v1"


def test_resolver_reuses_existing_normalized_document_without_extract_or_normalize(
    tmp_path,
):
    store = NormalizedDocumentStore(base_dir=tmp_path)
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"cached")
    stat_result = file_path.stat()
    cached = _document_schema(
        body_text="캐시된 본문",
        source_file={
            "path": str(file_path),
            "size": stat_result.st_size,
            "mtime": int(stat_result.st_mtime),
            "sha256": _sha256(b"cached"),
        },
    )
    store.save(7, cached)

    extractor = StubExtractor()
    normalizer = StubNormalizer()
    resolver = DocumentSchemaResolver(
        extractor=extractor,
        normalizer=normalizer,
        store=store,
    )

    resolved = resolver.get_or_create(document_id=7, file_path=str(file_path))

    assert resolved.body_text == "캐시된 본문"
    assert extractor.calls == []
    assert normalizer.calls == []


def test_resolver_generates_and_saves_when_normalized_document_missing(tmp_path):
    store = NormalizedDocumentStore(base_dir=tmp_path)
    generated = _document_schema(body_text="새로 생성된 본문")
    file_path = tmp_path / "new.pdf"
    file_path.write_bytes(b"new")
    extractor = StubExtractor()
    normalizer = StubNormalizer(document=generated)
    resolver = DocumentSchemaResolver(
        extractor=extractor,
        normalizer=normalizer,
        store=store,
    )

    resolved = resolver.get_or_create(document_id=8, file_path=str(file_path))

    assert resolved.body_text == "새로 생성된 본문"
    assert extractor.calls == [str(file_path)]
    assert len(normalizer.calls) == 1
    saved = store.load(8)
    assert saved is not None
    assert saved.to_dict() == generated.to_dict()
    assert saved.metadata["source_file"]["size"] == file_path.stat().st_size


def test_resolver_regenerates_when_normalization_version_mismatch(tmp_path):
    store = NormalizedDocumentStore(base_dir=tmp_path)
    file_path = tmp_path / "version.pdf"
    file_path.write_bytes(b"version")
    stat_result = file_path.stat()
    store.save(
        9,
        _document_schema(
            body_text="이전 버전",
            version="v0",
            source_file={
                "path": str(file_path),
                "size": stat_result.st_size,
                "mtime": int(stat_result.st_mtime),
                "sha256": _sha256(b"version"),
            },
        ),
    )

    regenerated = _document_schema(body_text="최신 버전", version="v1")
    extractor = StubExtractor()
    normalizer = StubNormalizer(document=regenerated, version="v1")
    resolver = DocumentSchemaResolver(
        extractor=extractor,
        normalizer=normalizer,
        store=store,
    )

    resolved = resolver.get_or_create(document_id=9, file_path=str(file_path))

    assert resolved.body_text == "최신 버전"
    assert extractor.calls == [str(file_path)]
    assert len(normalizer.calls) == 1
    saved = store.load(9)
    assert saved is not None
    assert saved.normalization_version == "v1"


def test_resolver_regenerates_when_source_fingerprint_changes(tmp_path):
    store = NormalizedDocumentStore(base_dir=tmp_path)
    file_path = tmp_path / "changed.pdf"
    file_path.write_bytes(b"old")
    old_stat = file_path.stat()
    store.save(
        10,
        _document_schema(
            body_text="오래된 본문",
            source_file={
                "path": str(file_path),
                "size": old_stat.st_size,
                "mtime": int(old_stat.st_mtime),
                "sha256": _sha256(b"old"),
            },
        ),
    )
    file_path.write_bytes(b"new-content")

    extractor = StubExtractor()
    regenerated = _document_schema(body_text="새 본문")
    normalizer = StubNormalizer(document=regenerated)
    resolver = DocumentSchemaResolver(
        extractor=extractor,
        normalizer=normalizer,
        store=store,
    )

    resolved = resolver.get_or_create(document_id=10, file_path=str(file_path))

    assert resolved.body_text == "새 본문"
    assert extractor.calls == [str(file_path)]
    assert len(normalizer.calls) == 1


def test_resolver_rechecks_after_lock_before_regenerating(tmp_path):
    store = NormalizedDocumentStore(base_dir=tmp_path)
    file_path = tmp_path / "locked.pdf"
    file_path.write_bytes(b"locked")

    class DoubleCheckStore(NormalizedDocumentStore):
        def __init__(self, base_dir: Path, document: DocumentSchema):
            super().__init__(base_dir=base_dir)
            self.document = document
            self.load_calls = 0

        def load(self, document_id: int):
            self.load_calls += 1
            if self.load_calls == 1:
                return None
            return self.document

    stat_result = file_path.stat()
    stored = _document_schema(
        body_text="다른 워커가 저장한 본문",
        source_file={
            "path": str(file_path),
            "size": stat_result.st_size,
            "mtime": int(stat_result.st_mtime),
            "sha256": _sha256(b"locked"),
        },
    )
    store = DoubleCheckStore(tmp_path, stored)
    extractor = StubExtractor()
    normalizer = StubNormalizer()
    resolver = DocumentSchemaResolver(
        extractor=extractor,
        normalizer=normalizer,
        store=store,
    )

    resolved = resolver.get_or_create(document_id=11, file_path=str(file_path))

    assert resolved.body_text == "다른 워커가 저장한 본문"
    assert extractor.calls == []
    assert normalizer.calls == []


def test_summary_process_reuses_normalized_document(monkeypatch):
    process = ProcessService()
    cached_document = _document_schema(body_text="저장된 normalized 본문")

    class FakeDB:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.closed = False

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed = True

    class FakeDocumentRecord:
        original_filename = "report.pdf"

    class FakeDocumentRepository:
        def __init__(self, db):
            self.db = db
            self.status_updates: list[tuple[int, str]] = []
            self.classification_updates: list[tuple[int, str, str]] = []

        def update_status(self, document_id, status):
            self.status_updates.append((document_id, status))

        def get_by_id(self, document_id):
            return FakeDocumentRecord()

        def update_classification(self, document_id, document_type, category):
            self.classification_updates.append((document_id, document_type, category))

    summary_calls = []

    class FakeSummaryRepository:
        def __init__(self, db):
            self.db = db

        def create_summary(self, **kwargs):
            summary_calls.append(kwargs)

    fake_db = FakeDB()
    fake_document_repository = FakeDocumentRepository(fake_db)

    monkeypatch.setattr(
        "domains.document.summary_process.SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "domains.document.summary_process.DocumentRepository",
        lambda db: fake_document_repository,
    )
    monkeypatch.setattr(
        "domains.document.summary_process.SummaryRepository",
        FakeSummaryRepository,
    )

    process.document_resolver.get_or_create = lambda **kwargs: cached_document
    process.classifier.classify = lambda title, body_text: {
        "document_type": "report",
        "category": "general",
    }
    process.summary_payload.build = lambda document: f"payload::{document.body_text}"
    process.llm.summarize = lambda payloads: {
        "summary_text": "요약",
        "key_points": ["핵심1", "핵심2"],
    }

    process.process_file("/tmp/report.pdf", 55)

    assert fake_document_repository.status_updates[0] == (
        55,
        DocumentStatus.PROCESSING,
    )
    assert fake_document_repository.status_updates[-1] == (55, DocumentStatus.DONE)
    assert fake_document_repository.classification_updates == [
        (55, "report", "general")
    ]
    assert summary_calls
    assert summary_calls[0]["document_id"] == 55
    assert summary_calls[0]["summary_text"] == "요약"
    assert summary_calls[0]["key_points"] == "핵심1\n핵심2"


def test_group_document_indexing_reuses_normalized_document(monkeypatch):
    cached_document = _document_schema(body_text="저장된 normalized 본문")

    resolver_calls = []
    embed_inputs = []
    vector_upserts = []
    bm25_upserts = []

    monkeypatch.setattr(
        indexing_module._document_schema_resolver,
        "get_or_create",
        lambda **kwargs: resolver_calls.append(kwargs) or cached_document,
    )
    monkeypatch.setattr(
        indexing_module._chunk_service,
        "build_group_document_chunks",
        lambda document, **kwargs: [
            {
                "chunk_id": "gdoc:1:chunk:0",
                "document_id": 1,
                "group_id": 2,
                "file_name": "doc.pdf",
                "source_type": "pdf",
                "chunk_type": "body",
                "section_title": "본문",
                "order_index": 0,
                "text": f"chunk::{document.body_text}",
            }
        ],
    )
    monkeypatch.setattr(
        indexing_module,
        "embed_passages",
        lambda texts: embed_inputs.append(texts) or [[0.1, 0.2]],
    )
    monkeypatch.setattr(
        indexing_module.vector_store,
        "get_document_chunk_ids",
        lambda document_id: set(),
    )
    monkeypatch.setattr(
        indexing_module.bm25_store,
        "get_document_chunk_ids",
        lambda document_id: set(),
    )
    monkeypatch.setattr(
        indexing_module.vector_store,
        "upsert",
        lambda **kwargs: vector_upserts.append(kwargs),
    )
    monkeypatch.setattr(
        indexing_module.bm25_store,
        "upsert_document_chunk",
        lambda **kwargs: bm25_upserts.append(kwargs),
    )
    monkeypatch.setattr(
        indexing_module.vector_store,
        "delete_document_chunks",
        lambda document_id, stale_chunk_ids: None,
    )
    monkeypatch.setattr(
        indexing_module.bm25_store,
        "delete_document_chunks",
        lambda document_id, group_id, stale_chunk_ids: None,
    )

    count = indexing_module.index_group_document(
        document_id=1,
        group_id=2,
        file_name="doc.pdf",
        file_path="/tmp/doc.pdf",
        document_type="report",
        category="general",
    )

    assert count == 1
    assert resolver_calls == [{"document_id": 1, "file_path": "/tmp/doc.pdf"}]
    assert embed_inputs == [["chunk::저장된 normalized 본문"]]
    assert vector_upserts[0]["payload"]["document_type"] == "report"
    assert vector_upserts[0]["payload"]["category"] == "general"
    assert bm25_upserts[0]["text"] == "chunk::저장된 normalized 본문"
