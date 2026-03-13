import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL이 설정되지 않았습니다. "
        "루트 디렉토리에 .env 파일을 생성하고 DATABASE_URL을 설정해주세요."
    )

engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True, pool_recycle=3600)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
