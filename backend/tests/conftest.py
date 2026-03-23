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
from models.model import Document, Group, Summary, User
from redis_client import redis_client
from routers.auth import get_current_user
from services.auth_service import AuthService

auth_service = AuthService()
from tests.dummy_data import documents, summaries, users

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

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
    """users[0]로 로그인 + seed_documents 적용된 클라이언트"""
    # 유저 등록
    for user_data in users:
        u = user_data.copy()
        u["password"] = auth_service.hash_password(u["password"])
        db_session.add(User(**u))
    for group_data in groups:
        db_session.add(Group(**group_data))
    # 문서 + 요약 삽입
    for d in documents:
        db_session.add(Document(**d))
    for s in summaries:
        db_session.add(Summary(**s))
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
    group_objects = [Group(**g) for g in groups]
    doc_objects = [Document(**d) for d in documents]
    sum_objects = [Summary(**s) for s in summaries]
    for obj in group_objects:
        db_session.add(obj)
    for obj in doc_objects:
        db_session.add(obj)
    for obj in sum_objects:
        db_session.add(obj)
    db_session.commit()
    for obj in group_objects + doc_objects + sum_objects:
        db_session.refresh(obj)
    return {"groups": group_objects, "documents": doc_objects, "summaries": sum_objects}
