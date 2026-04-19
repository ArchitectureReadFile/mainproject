from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from domains.chat.service import ChatService
from errors import AppException, ErrorCode
from models.model import ChatSessionReferenceChunk, ChatSessionReferenceStatus


def test_enqueue_reference_document_replaces_previous_reference(monkeypatch, tmp_path):
    chat_repo = MagicMock()
    service = ChatService(chat_repo, MagicMock(), MagicMock())
    session = SimpleNamespace(
        id=11,
        user_id=1,
    )
    previous_reference = SimpleNamespace(upload_path=str(tmp_path / "old.pdf"))

    chat_repo.get_reference_by_session_id.return_value = previous_reference
    monkeypatch.setattr(
        service,
        "_get_session_with_permission",
        lambda user_id, session_id: session,
    )
    monkeypatch.setattr(
        service,
        "_write_reference_upload",
        lambda session_id, file_name, file_bytes: str(tmp_path / "new.pdf"),
    )
    remove_file = MagicMock()
    monkeypatch.setattr(service, "_remove_file_quietly", remove_file)

    with patch("domains.chat.tasks.process_session_reference_document.delay"):
        reference = service.enqueue_reference_document(
            user_id=1,
            session_id=11,
            file_name="new.pdf",
            file_bytes=b"pdf",
        )

    chat_repo.delete.assert_called_once_with(previous_reference)
    chat_repo.flush.assert_called_once()
    chat_repo.add.assert_called_once()
    chat_repo.commit.assert_called_once()
    remove_file.assert_called_once_with(str(tmp_path / "old.pdf"))

    assert reference.session_id == 11
    assert reference.title == "new.pdf"
    assert reference.status == ChatSessionReferenceStatus.PROCESSING


def test_enqueue_reference_document_marks_failed_when_enqueue_fails(
    monkeypatch, tmp_path
):
    chat_repo = MagicMock()
    service = ChatService(chat_repo, MagicMock(), MagicMock())
    session = SimpleNamespace(
        id=11,
        user_id=1,
    )

    chat_repo.get_reference_by_session_id.return_value = None
    monkeypatch.setattr(
        service,
        "_get_session_with_permission",
        lambda user_id, session_id: session,
    )
    monkeypatch.setattr(
        service,
        "_write_reference_upload",
        lambda session_id, file_name, file_bytes: str(tmp_path / "failed.pdf"),
    )
    remove_file = MagicMock()
    monkeypatch.setattr(service, "_remove_file_quietly", remove_file)

    with (
        patch(
            "domains.chat.tasks.process_session_reference_document.delay",
            side_effect=RuntimeError("queue down"),
        ),
        pytest.raises(AppException) as exc_info,
    ):
        service.enqueue_reference_document(
            user_id=1,
            session_id=11,
            file_name="failed.pdf",
            file_bytes=b"pdf",
        )

    assert exc_info.value.error_code == ErrorCode.CHAT_REFERENCE_ENQUEUE_FAILED

    reference = chat_repo.add.call_args[0][0]
    assert reference.status == ChatSessionReferenceStatus.FAILED
    assert reference.failure_code == ErrorCode.CHAT_REFERENCE_ENQUEUE_FAILED.code
    assert reference.error_message == ErrorCode.CHAT_REFERENCE_ENQUEUE_FAILED.message
    assert reference.upload_path is None
    assert chat_repo.commit.call_count == 2
    remove_file.assert_called_once_with(str(tmp_path / "failed.pdf"))


def test_process_session_reference_document_success(monkeypatch, tmp_path):
    from domains.chat.tasks import process_session_reference_document

    db = MagicMock()
    upload_path = tmp_path / "ref.pdf"
    upload_path.write_bytes(b"pdf")
    reference = SimpleNamespace(
        id=7,
        upload_path=str(upload_path),
        extracted_text=None,
        status=ChatSessionReferenceStatus.PROCESSING,
        failure_code=None,
        error_message=None,
    )
    repository = MagicMock()
    repository.get_reference_by_id.return_value = reference

    monkeypatch.setattr("domains.chat.tasks.SessionLocal", lambda: db)
    monkeypatch.setattr("domains.chat.tasks.ChatRepository", lambda db: repository)
    monkeypatch.setattr("domains.chat.tasks._extractor.extract_bytes", lambda _: "raw")
    monkeypatch.setattr("domains.chat.tasks._normalizer.normalize", lambda _: "schema")
    monkeypatch.setattr("domains.chat.tasks._session_payload.build", lambda _: "본문")

    result = process_session_reference_document(7)

    assert result == {"status": "success", "reference_id": 7}
    assert reference.status == ChatSessionReferenceStatus.READY
    assert reference.extracted_text == "본문"
    assert reference.failure_code is None
    assert reference.error_message is None
    assert reference.upload_path is None
    added_chunks = [
        call.args[0]
        for call in repository.add.call_args_list
        if isinstance(call.args[0], ChatSessionReferenceChunk)
    ]
    assert added_chunks
    assert [chunk.chunk_order for chunk in added_chunks] == list(
        range(len(added_chunks))
    )
    repository.commit.assert_called_once()
    assert not upload_path.exists()
    db.close.assert_called_once()


def test_process_session_reference_document_failure(monkeypatch, tmp_path):
    from domains.chat.tasks import process_session_reference_document

    db = MagicMock()
    upload_path = tmp_path / "ref.pdf"
    upload_path.write_bytes(b"pdf")
    reference = SimpleNamespace(
        id=7,
        upload_path=str(upload_path),
        extracted_text=None,
        status=ChatSessionReferenceStatus.PROCESSING,
        failure_code=None,
        error_message=None,
    )
    repository = MagicMock()
    repository.get_reference_by_id.return_value = reference

    monkeypatch.setattr("domains.chat.tasks.SessionLocal", lambda: db)
    monkeypatch.setattr("domains.chat.tasks.ChatRepository", lambda db: repository)
    monkeypatch.setattr(
        "domains.chat.tasks._extractor.extract_bytes",
        MagicMock(side_effect=RuntimeError("parse fail")),
    )

    result = process_session_reference_document(7)

    assert result["status"] == "failed"
    assert result["failure_code"] == ErrorCode.CHAT_REFERENCE_PARSE_FAILED.code
    assert reference.status == ChatSessionReferenceStatus.FAILED
    assert reference.failure_code == ErrorCode.CHAT_REFERENCE_PARSE_FAILED.code
    assert reference.error_message == ErrorCode.CHAT_REFERENCE_PARSE_FAILED.message
    assert reference.upload_path is None
    repository.commit.assert_called_once()
    assert not upload_path.exists()
    db.close.assert_called_once()
