import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    GENERAL = "GENERAL"


class DocumentStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


document_categories = Table(
    "document_categories",
    Base.metadata,
    Column(
        "document_id",
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(20), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(
        Enum(UserRole, native_enum=False), default=UserRole.GENERAL, nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False
    )

    documents = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    documents = relationship(
        "Document", secondary=document_categories, back_populates="categories"
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    document_url = Column(String(1024), nullable=False, unique=True)
    status = Column(
        Enum(DocumentStatus, native_enum=False),
        default=DocumentStatus.PENDING,
        nullable=False,
    )
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    owner = relationship("User", back_populates="documents")
    summary = relationship(
        "Summary",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    categories = relationship(
        "Category", secondary=document_categories, back_populates="documents"
    )


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    case_number = Column(String(100))
    case_name = Column(String(255))
    court_name = Column(String(100))
    judgment_date = Column(Date)
    summary_title = Column(String(255))
    summary_main = Column(Text)
    plaintiff = Column(Text)
    defendant = Column(Text)
    facts = Column(Text)
    judgment_order = Column(Text)
    judgment_reason = Column(Text)
    related_laws = Column(Text)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    document = relationship("Document", back_populates="summary")
