import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base, get_db
from main import app
from models.model import (
    Document,
    DocumentApproval,
    DocumentComment,
    DocumentLifecycleStatus,
    DocumentStatus,
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    ReviewStatus,
    Summary,
    User,
    utc_now_naive,
)
from redis_client import redis_client
from routers.auth import get_current_user
from services.auth_service import AuthService
from tests.dummy_data import documents, groups, summaries, users

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

auth_service = AuthService(None)

engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
database.engine = engine


@pytest.fixture(autouse=True)
def setup_redis_state():
    redis_client.flushall()
    yield


@pytest.fixture()
def fake_redis():
    return redis_client


@pytest.fixture(autouse=True)
def stub_async_side_effects(monkeypatch, fake_redis):
    """테스트 중 Redis/Celery 외부 부수효과를 no-op으로 막는다."""
    import services.group_service as group_service_module
    import tasks.file_cleanup_task as file_cleanup_task_module
    from services.notification_service import NotificationService
    from tasks.group_document_task import deindex_document, index_approved_document

    monkeypatch.setattr(
        NotificationService,
        "send_realtime_notification_sync",
        lambda self, user_id, notification: None,
    )
    monkeypatch.setattr(
        deindex_document,
        "delay",
        lambda document_id: None,
    )
    monkeypatch.setattr(
        index_approved_document,
        "delay",
        lambda document_id: None,
    )
    monkeypatch.setattr(group_service_module, "redis_client", fake_redis)
    monkeypatch.setattr(file_cleanup_task_module, "redis_client", fake_redis)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(db_session):
    user_data = users[0].copy()
    user_data["password"] = auth_service.hash_password(user_data["password"])
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, db_session):
    """
    users[0]로 로그인 + seed_documents 적용된 클라이언트.

    - users[0] → group_id=1 OWNER 멤버십
    - users[1] → group_id=2 OWNER 멤버십
    - doc_id=101 (group_id=1) → APPROVED 승인 레코드 포함
      목록 기본 조회(view_type=all)는 APPROVED 문서만 반환하므로 필수
    """
    for user_data in users:
        u = user_data.copy()
        u["password"] = auth_service.hash_password(u["password"])
        db_session.add(User(**u))
    for group_data in groups:
        db_session.add(Group(**group_data))
    for d in documents:
        db_session.add(Document(**d))
    for s in summaries:
        db_session.add(Summary(**s))
    db_session.flush()

    # users[0] → group_id=1 OWNER 멤버십
    db_session.add(
        GroupMember(
            user_id=1,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    # users[1] → group_id=2 OWNER 멤버십
    db_session.add(
        GroupMember(
            user_id=2,
            group_id=2,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    # doc_id=101 승인 레코드 — view_type=all 목록 조회 필수 조건
    db_session.add(DocumentApproval(document_id=101, status=ReviewStatus.APPROVED))
    db_session.commit()

    token = auth_service.create_access_token(users[0]["email"])
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def logged_in_user(request, db_session):
    user_data = request.param.copy()
    user_data["password"] = auth_service.hash_password(user_data["password"])
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def registered_admin(db_session):
    user_data = users[1].copy()
    user_data["password"] = auth_service.hash_password(user_data["password"])
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def seed_documents(db_session):
    """
    그룹/문서/요약 seed fixture.

    - users[0] → group_id=1 OWNER 멤버십
    - users[1] → group_id=2 OWNER 멤버십
    - doc_id=101 (group_id=1) → APPROVED 승인 레코드 포함
    """
    group_objects = [Group(**g) for g in groups]
    doc_objects = [Document(**d) for d in documents]
    sum_objects = [Summary(**s) for s in summaries]
    for obj in group_objects:
        db_session.add(obj)
    for obj in doc_objects:
        db_session.add(obj)
    for obj in sum_objects:
        db_session.add(obj)
    db_session.flush()

    # users[0] → group_id=1 OWNER 멤버십
    db_session.add(
        GroupMember(
            user_id=1,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    # users[1] → group_id=2 OWNER 멤버십
    db_session.add(
        GroupMember(
            user_id=2,
            group_id=2,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    # doc_id=101 승인 레코드
    db_session.add(DocumentApproval(document_id=101, status=ReviewStatus.APPROVED))
    db_session.commit()
    for obj in group_objects + doc_objects + sum_objects:
        db_session.refresh(obj)
    return {"groups": group_objects, "documents": doc_objects, "summaries": sum_objects}


@pytest.fixture
def user_factory(db_session):
    """테스트용 사용자를 생성하는 팩토리를 제공한다."""

    def _create(user_data: dict) -> User:
        payload = user_data.copy()
        payload["password"] = auth_service.hash_password(payload["password"])
        user = User(**payload)
        db_session.add(user)
        db_session.flush()
        return user

    return _create


@pytest.fixture
def group_factory(db_session):
    """테스트용 워크스페이스를 생성하는 팩토리를 제공한다."""

    def _create(
        *,
        group_id: int = 1,
        owner_user_id: int,
        name: str = groups[0]["name"],
        description: str = groups[0]["description"],
        status: GroupStatus = GroupStatus.ACTIVE,
    ) -> Group:
        group = Group(
            id=group_id,
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            status=status,
        )
        db_session.add(group)
        db_session.flush()
        return group

    return _create


@pytest.fixture
def group_member_factory(db_session):
    """테스트용 워크스페이스 멤버십을 생성하는 팩토리를 제공한다."""

    def _create(
        *,
        user_id: int,
        group_id: int = 1,
        role: MembershipRole,
        status: MembershipStatus = MembershipStatus.ACTIVE,
    ) -> GroupMember:
        member = GroupMember(
            user_id=user_id,
            group_id=group_id,
            role=role,
            status=status,
        )
        db_session.add(member)
        db_session.flush()
        return member

    return _create


@pytest.fixture
def document_factory(db_session):
    """테스트용 문서와 승인 상태를 생성하는 팩토리를 제공한다."""

    def _create(
        *,
        doc_id: int,
        uploader_user_id: int,
        approval_status: ReviewStatus,
        group_id: int = 1,
        filename_prefix: str = "comment_doc",
    ) -> Document:
        document = Document(
            id=doc_id,
            group_id=group_id,
            uploader_user_id=uploader_user_id,
            original_filename=f"{filename_prefix}_{doc_id}.pdf",
            stored_path=f"/tmp/test_docs/{filename_prefix}_{doc_id}.pdf",
            processing_status=DocumentStatus.DONE,
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
        )
        db_session.add(document)
        db_session.add(
            DocumentApproval(
                document_id=doc_id,
                status=approval_status,
            )
        )
        db_session.flush()
        return document

    return _create


@pytest.fixture
def comment_factory(db_session):
    """테스트용 댓글 또는 답글을 생성하는 팩토리를 제공한다."""

    def _create(
        *,
        document_id: int,
        author_user_id: int,
        content: str,
        scope: str,
        parent_id: int | None = None,
        deleted: bool = False,
    ) -> DocumentComment:
        comment = DocumentComment(
            document_id=document_id,
            author_user_id=author_user_id,
            parent_id=parent_id,
            content=content,
            comment_scope=scope,
            page=1 if parent_id is None else None,
            x=0.11 if parent_id is None else None,
            y=0.22 if parent_id is None else None,
            deleted_at=utc_now_naive() if deleted else None,
        )
        db_session.add(comment)
        db_session.flush()
        return comment

    return _create
