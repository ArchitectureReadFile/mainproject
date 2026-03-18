import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    GENERAL = "GENERAL"

class SubscriptionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"

class MembershipRole(enum.Enum):
    OWNER = "OWNER" 
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

class MembershipStatus(enum.Enum):
    INVITED = "INVITED" 
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"

class GroupStatus(enum.Enum):
    ACTIVE = "ACTIVE" 
    DELETE_PENDING = "DELETE_PENDING"
    DELETED = "DELETED"

class DocumentStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"

class ReviewStatus(enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW" 
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class DocumentLifecycleStatus(enum.Enum):
    ACTIVE = "ACTIVE" 
    DELETE_PENDING = "DELETE_PENDING"
    DELETED = "DELETED"


class ChatMessageRole(enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class NotificationType(enum.Enum):
    GROUP_DELETE_REQUESTED = "GROUP_DELETE_REQUESTED" 
    GROUP_DELETE_CANCELED = "GROUP_DELETE_CANCELED"
    DOCUMENT_DELETE_REQUESTED = "DOCUMENT_DELETE_REQUESTED"
    DOCUMENT_RESTORED = "DOCUMENT_RESTORED"
    MEMBER_INVITED = "MEMBER_INVITED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    SYSTEM = "SYSTEM"


class SubscriptionPlan(enum.Enum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"


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
        "Document",
        foreign_keys="Document.uploader_user_id",
        back_populates="owner",
    )
    # cascade 제거 — FK가 SET NULL이므로 ORM이 row를 삭제하면 안 됨
    precedents = relationship(
        "Precedent", back_populates="uploaded_by_admin", passive_deletes=True
    )
    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    owned_groups = relationship("Group", back_populates="owner")
    
    memberships = relationship(
        "GroupMember",
        foreign_keys="GroupMember.user_id",
        back_populates="user",
    )

    invited_members = relationship(
        "GroupMember",
        foreign_keys="GroupMember.invited_by_user_id",
        back_populates="invited_by",
    )

    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    
    notifications = relationship(
        "Notification",
        foreign_keys="Notification.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    sent_notifications = relationship(
        "Notification",
        foreign_keys="Notification.actor_user_id",
        back_populates="actor",
    )

    reviewed_documents = relationship(
       "DocumentApproval",
       foreign_keys="DocumentApproval.reviewer_user_id",
       back_populates="reviewer",
    )

    deleted_documents = relationship(
        "Document",
        foreign_keys="Document.deleted_by_user_id",
        back_populates="deleted_by",
    )



class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan = Column(Enum(SubscriptionPlan, native_enum=False), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus, native_enum=False), default=SubscriptionStatus.ACTIVE, nullable=False)

    started_at = Column(DateTime, default=utc_now_naive, nullable=False)
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    user = relationship("User", back_populates="subscription")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(Enum(GroupStatus, native_enum=False), default=GroupStatus.ACTIVE, nullable=False)

    delete_requested_at = Column(DateTime)
    delete_scheduled_at = Column(DateTime)
    deleted_at = Column(DateTime)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    owner = relationship("User", back_populates="owned_groups")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    documents = relationship(
        "Document",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    notifications = relationship(
       "Notification",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MembershipRole, native_enum=False), nullable=False)
    status = Column(Enum(MembershipStatus, native_enum=False), default=MembershipStatus.ACTIVE, nullable=False)

    invited_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    invited_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime)
    removed_at = Column(DateTime)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )

    user = relationship("User", foreign_keys=[user_id], back_populates="memberships")
    group = relationship("Group", back_populates="members")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id], back_populates="invited_members")



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

    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)

    uploader_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(1024), nullable=False, unique=True)

    title = Column(String(255))
    document_type = Column(String(50))

    processing_status = Column(
        Enum(DocumentStatus, native_enum=False),
        default=DocumentStatus.PENDING,
        nullable=False,
    )

    lifecycle_status = Column(
        Enum(DocumentLifecycleStatus, native_enum=False),
        default=DocumentLifecycleStatus.ACTIVE,
        nullable=False,
    )

    delete_requested_at = Column(DateTime)
    delete_scheduled_at = Column(DateTime)
    deleted_at = Column(DateTime)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    owner = relationship("User", foreign_keys=[uploader_user_id], back_populates="documents")

    summary = relationship(
        "Summary",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    approval = relationship(
        "DocumentApproval",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    categories = relationship(
        "Category",
        secondary=document_categories,
        back_populates="documents",
    )

    group = relationship("Group", back_populates="documents")

    deleted_by = relationship(
       "User",
        foreign_keys=[deleted_by_user_id],
        back_populates="deleted_documents",
    )


class DocumentApproval(Base):
    __tablename__ = "document_approvals"

    id = Column(Integer, primary_key=True)

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    reviewer_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    status = Column(
        Enum(ReviewStatus, native_enum=False),
        default=ReviewStatus.PENDING_REVIEW,
        nullable=False,
    )

    feedback = Column(Text)
    reviewed_at = Column(DateTime)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    document = relationship("Document", back_populates="approval")
    reviewer = relationship("User", back_populates="reviewed_documents")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    summary_title = Column(String(255))
    summary_text = Column(Text)
    key_points = Column(Text)

    metadata_json = Column(Text)  # 판례/계약서 구조 데이터

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    document = relationship("Document", back_populates="summary")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255))

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    user = relationship("User", back_populates="chat_sessions")

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )



class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)

    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(
        Enum(ChatMessageRole, native_enum=False),
        nullable=False,
    )

    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    session = relationship("ChatSession", back_populates="messages")


class Precedent(Base):
    """RAG용 판례 메타 및 인덱싱 상태 테이블"""

    __tablename__ = "precedents"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String(2048), unique=True, nullable=False)
    title = Column(String(512), nullable=True)  # 자동 추출 전까지 null 허용
    processing_status = Column(
        Enum(DocumentStatus, native_enum=False),
        default=DocumentStatus.PENDING,
        nullable=False,
    )
    error_message = Column(Text, nullable=True)
    uploaded_by_admin_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False
    )

    uploaded_by_admin = relationship("User", back_populates="precedents")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
    )

    type = Column(
        Enum(NotificationType, native_enum=False),
        nullable=False,
    )

    title = Column(String(255), nullable=False)
    body = Column(Text)

    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime)

    target_type = Column(String(50))
    target_id = Column(Integer)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    user = relationship("User", foreign_keys=[user_id], back_populates="notifications")
    actor = relationship("User", foreign_keys=[actor_user_id], back_populates="sent_notifications")
    group = relationship("Group", back_populates="notifications")

