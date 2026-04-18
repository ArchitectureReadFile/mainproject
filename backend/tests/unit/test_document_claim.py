from datetime import timedelta

from domains.document.repository import DocumentRepository
from models.model import (
    Document,
    DocumentLifecycleStatus,
    DocumentPreviewStatus,
    DocumentStatus,
    Group,
    GroupStatus,
    User,
    utc_now_naive,
)


def _make_user_and_group(db_session):
    user = User(
        email="owner@example.com",
        username="owner",
        password="hashed",
    )
    db_session.add(user)
    db_session.flush()

    group = Group(
        owner_user_id=user.id,
        name="group",
        description="desc",
        status=GroupStatus.ACTIVE,
    )
    db_session.add(group)
    db_session.flush()
    return user, group


def _make_document(
    db_session,
    *,
    group_id: int,
    uploader_user_id: int,
    created_at,
    status=DocumentStatus.PENDING,
    lifecycle=DocumentLifecycleStatus.ACTIVE,
):
    document = Document(
        group_id=group_id,
        uploader_user_id=uploader_user_id,
        original_filename=f"doc-{created_at.timestamp()}.pdf",
        stored_path=f"/tmp/doc-{created_at.timestamp()}.pdf",
        preview_status=DocumentPreviewStatus.PENDING,
        processing_status=status,
        lifecycle_status=lifecycle,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(document)
    db_session.flush()
    return document


def test_claim_next_pending_document_picks_oldest_active_pending(db_session):
    user, group = _make_user_and_group(db_session)
    now = utc_now_naive()
    first = _make_document(
        db_session,
        group_id=group.id,
        uploader_user_id=user.id,
        created_at=now,
    )
    _make_document(
        db_session,
        group_id=group.id,
        uploader_user_id=user.id,
        created_at=now + timedelta(seconds=1),
    )
    db_session.commit()

    repo = DocumentRepository(db_session)
    claimed = repo.claim_next_pending_document()

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.processing_status == DocumentStatus.PROCESSING


def test_claim_next_pending_document_skips_row_lost_to_race(db_session, monkeypatch):
    user, group = _make_user_and_group(db_session)
    now = utc_now_naive()
    first = _make_document(
        db_session,
        group_id=group.id,
        uploader_user_id=user.id,
        created_at=now,
    )
    second = _make_document(
        db_session,
        group_id=group.id,
        uploader_user_id=user.id,
        created_at=now + timedelta(seconds=1),
    )
    db_session.commit()

    repo = DocumentRepository(db_session)
    original_try_claim = repo._try_claim_document
    raced = {"done": False}

    def fake_try_claim(document_id: int) -> bool:
        if document_id == first.id and not raced["done"]:
            raced["done"] = True
            db_session.query(Document).filter(Document.id == first.id).update(
                {Document.processing_status: DocumentStatus.PROCESSING},
                synchronize_session=False,
            )
            db_session.flush()
            return False
        return original_try_claim(document_id)

    monkeypatch.setattr(repo, "_try_claim_document", fake_try_claim)

    claimed = repo.claim_next_pending_document()

    assert claimed is not None
    assert claimed.id == second.id
    assert claimed.processing_status == DocumentStatus.PROCESSING
