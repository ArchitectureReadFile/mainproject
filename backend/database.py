import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL이 설정되지 않았습니다. "
        "루트 디렉토리에 .env 파일을 생성하고 DATABASE_URL을 설정해주세요."
    )

engine = create_engine(
    DATABASE_URL,
    echo=SQLALCHEMY_ECHO,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    """WebSocket / 비-DI 경로에서 DB 세션을 안전하게 사용하기 위한 context manager.

    FastAPI DI(get_db)를 쓸 수 없는 경로(WebSocket, Celery task 등)에서 사용한다.

    Example::

        with db_session() as db:
            repo = SomeRepository(db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
