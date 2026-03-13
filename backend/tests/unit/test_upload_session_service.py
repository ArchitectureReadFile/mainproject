from services.upload_session_service import (
    ABANDONED_UPLOAD_MESSAGE,
    UploadSessionService,
)


def test_create_session_stores_waiting_items(fake_redis):
    service = UploadSessionService()

    session = service.create_session(1, ["a.pdf", "b.pdf"])

    assert len(session["items"]) == 2
    assert session["items"][0]["file_name"] == "a.pdf"
    assert session["items"][0]["status"] == "waiting"
    assert session["items"][1]["file_name"] == "b.pdf"
    assert session["items"][1]["status"] == "waiting"


def test_abandon_session_keeps_processing_and_fails_remaining(fake_redis):
    service = UploadSessionService()

    service.create_session(1, ["a.pdf", "b.pdf", "c.pdf"])
    service.mark_processing(1, "a.pdf", 101)

    session = service.abandon_session(1)

    assert session["items"][0]["status"] == "processing"
    assert session["items"][0]["doc_id"] == 101
    assert session["items"][1]["status"] == "failed"
    assert session["items"][1]["error"] == ABANDONED_UPLOAD_MESSAGE
    assert session["items"][2]["status"] == "failed"
    assert session["items"][2]["error"] == ABANDONED_UPLOAD_MESSAGE


def test_mark_document_done_updates_summary(fake_redis):
    service = UploadSessionService()

    service.create_session(1, ["a.pdf"])
    service.mark_processing(1, "a.pdf", 101)

    session = service.mark_document_done(
        1,
        101,
        {
            "case_number": "2024다12345",
            "court": "대법원",
            "date": "2024-01-01",
            "content": "요약 본문",
        },
    )

    assert session["items"][0]["status"] == "done"
    assert session["items"][0]["summary"]["court"] == "대법원"
    assert session["items"][0]["summary"]["content"] == "요약 본문"
