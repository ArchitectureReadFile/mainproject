"""initial schema

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18 20:30:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260418_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_raw_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("api_target", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("raw_format", sa.String(length=8), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("extra_meta", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "provider", "api_target", "external_id", name="uq_raw_source"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_raw_sources_fetched_at",
        "platform_raw_sources",
        ["fetched_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_raw_sources_source_type",
        "platform_raw_sources",
        ["source_type"],
        unique=False,
    )

    op.create_table(
        "platform_sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_sync_runs_source_type",
        "platform_sync_runs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_platform_sync_runs_started_at",
        "platform_sync_runs",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "GENERAL", name="userrole", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "DELETE_PENDING",
                "BLOCKED",
                "DELETED",
                name="groupstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "pending_reason",
            sa.Enum(
                "OWNER_DELETE_REQUEST",
                "SUBSCRIPTION_EXPIRED",
                name="grouppendingreason",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("delete_requested_at", sa.DateTime(), nullable=True),
        sa.Column("delete_scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "notification_type",
            sa.Enum(
                "AI_ANSWER_COMPLETE",
                "WORKSPACE_INVITED",
                "WORKSPACE_DELETE_NOTICE",
                "DOCUMENT_UPLOAD_REQUESTED",
                "DOCUMENT_DELETED",
                "WORKSPACE_KICKED",
                "COMMENT_MENTIONED",
                "WORKSPACE_MEMBER_UPDATE",
                "DOCUMENT_REVIEW_RESULT",
                "WORKSPACE_STATUS_UPDATE",
                name="notificationtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_toast_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "notification_type", name="uq_user_notification_type"
        ),
    )

    op.create_table(
        "platform_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("raw_source_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("display_title", sa.String(length=768), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("agency", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "external_id", name="uq_platform_doc"),
        sa.ForeignKeyConstraint(
            ["raw_source_id"], ["platform_raw_sources.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_platform_documents_external_id",
        "platform_documents",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        "ix_platform_documents_issued_at",
        "platform_documents",
        ["issued_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_documents_raw_source_id",
        "platform_documents",
        ["raw_source_id"],
        unique=False,
    )
    op.create_index(
        "ix_platform_documents_source_type",
        "platform_documents",
        ["source_type"],
        unique=False,
    )

    op.create_table(
        "platform_sync_failures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("display_title", sa.String(length=512), nullable=True),
        sa.Column("detail_link", sa.String(length=2048), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("payload_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("retried_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sync_run_id"], ["platform_sync_runs.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_platform_sync_failures_created_at",
        "platform_sync_failures",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_sync_failures_source_type",
        "platform_sync_failures",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_platform_sync_failures_sync_run_id",
        "platform_sync_failures",
        ["sync_run_id"],
        unique=False,
    )

    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("FREE", "PREMIUM", name="subscriptionplan", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "CANCELED",
                "EXPIRED",
                name="subscriptionstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("auto_renew", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("reference_group_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reference_group_id"], ["groups.id"], ondelete="SET NULL"
        ),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("uploader_user_id", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("original_content_type", sa.String(length=255), nullable=True),
        sa.Column("preview_pdf_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "preview_status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "READY",
                "FAILED",
                name="documentpreviewstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "DONE",
                "FAILED",
                name="documentstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("failure_stage", sa.String(length=32), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.Enum(
                "ACTIVE",
                "DELETE_PENDING",
                "DELETED",
                name="documentlifecyclestatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("delete_requested_at", sa.DateTime(), nullable=True),
        sa.Column("delete_scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploader_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("stored_path"),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("preview_pdf_path"),
    )
    op.create_index("ix_documents_id", "documents", ["id"], unique=False)
    op.create_index(
        "ix_documents_uploader_user_id", "documents", ["uploader_user_id"], unique=False
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column(
            "requester_role",
            sa.Enum(
                "OWNER",
                "ADMIN",
                "EDITOR",
                "VIEWER",
                name="membershiprole",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "READY",
                "FAILED",
                "EXPIRED",
                "CANCELLED",
                name="exportjobstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("export_file_name", sa.String(length=255), nullable=True),
        sa.Column("failure_stage", sa.String(length=32), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_file_count", sa.Integer(), nullable=False),
        sa.Column("exported_file_count", sa.Integer(), nullable=False),
        sa.Column("missing_file_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_export_jobs_expires_at", "export_jobs", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_export_jobs_group_id", "export_jobs", ["group_id"], unique=False
    )
    op.create_index("ix_export_jobs_id", "export_jobs", ["id"], unique=False)
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"], unique=False)
    op.create_index(
        "ix_export_jobs_user_group_status",
        "export_jobs",
        ["user_id", "group_id", "status"],
        unique=False,
    )
    op.create_index("ix_export_jobs_user_id", "export_jobs", ["user_id"], unique=False)

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "OWNER",
                "ADMIN",
                "EDITOR",
                "VIEWER",
                name="membershiprole",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "INVITED",
                "ACTIVE",
                "REMOVED",
                name="membershipstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=True),
        sa.Column("invited_at", sa.DateTime(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "AI_ANSWER_COMPLETE",
                "WORKSPACE_INVITED",
                "WORKSPACE_DELETE_NOTICE",
                "DOCUMENT_UPLOAD_REQUESTED",
                "DOCUMENT_DELETED",
                "WORKSPACE_KICKED",
                "COMMENT_MENTIONED",
                "WORKSPACE_MEMBER_UPDATE",
                "DOCUMENT_REVIEW_RESULT",
                "WORKSPACE_STATUS_UPDATE",
                name="notificationtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "platform_document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform_document_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("chunk_type", sa.String(length=32), nullable=True),
        sa.Column("chunk_order", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_id_str", sa.String(length=256), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["platform_document_id"], ["platform_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id_str"),
    )
    op.create_index(
        "ix_platform_doc_chunks_chunk_type",
        "platform_document_chunks",
        ["chunk_type"],
        unique=False,
    )
    op.create_index(
        "ix_platform_doc_chunks_source_type",
        "platform_document_chunks",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_platform_document_chunks_platform_document_id",
        "platform_document_chunks",
        ["platform_document_id"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("USER", "ASSISTANT", name="chatmessagerole", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
    )

    op.create_table(
        "chat_session_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("upload_path", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PROCESSING",
                "READY",
                "FAILED",
                name="chatsessionreferencestatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "document_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("assignee_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_REVIEW",
                "APPROVED",
                "REJECTED",
                name="reviewstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assignee_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("document_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "document_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("comment_scope", sa.String(length=20), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["document_comments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_comments_author_user_id",
        "document_comments",
        ["author_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_comments_comment_scope",
        "document_comments",
        ["comment_scope"],
        unique=False,
    )
    op.create_index(
        "ix_document_comments_deleted_by_user_id",
        "document_comments",
        ["deleted_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_comments_document_id",
        "document_comments",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_comments_parent_id",
        "document_comments",
        ["parent_id"],
        unique=False,
    )

    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("key_points", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_summaries_id", "summaries", ["id"], unique=False)

    op.create_table(
        "chat_session_reference_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=False),
        sa.Column("chunk_order", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reference_id"], ["chat_session_references.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "reference_id",
            "chunk_order",
            name="uq_chat_session_reference_chunk_order",
        ),
    )
    op.create_index(
        "ix_chat_session_reference_chunks_reference_id",
        "chat_session_reference_chunks",
        ["reference_id"],
        unique=False,
    )

    op.create_table(
        "document_comment_mentions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("mentioned_user_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_username", sa.String(length=20), nullable=False),
        sa.Column("start_index", sa.Integer(), nullable=False),
        sa.Column("end_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "comment_id", "start_index", "end_index", name="uq_comment_mention_span"
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"], ["document_comments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mentioned_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_document_comment_mentions_comment_id",
        "document_comment_mentions",
        ["comment_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_comment_mentions_mentioned_user_id",
        "document_comment_mentions",
        ["mentioned_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_comment_mentions_mentioned_user_id",
        table_name="document_comment_mentions",
    )
    op.drop_index(
        "ix_document_comment_mentions_comment_id",
        table_name="document_comment_mentions",
    )
    op.drop_table("document_comment_mentions")
    op.drop_index(
        "ix_chat_session_reference_chunks_reference_id",
        table_name="chat_session_reference_chunks",
    )
    op.drop_table("chat_session_reference_chunks")
    op.drop_index("ix_summaries_id", table_name="summaries")
    op.drop_table("summaries")
    op.drop_index("ix_document_comments_parent_id", table_name="document_comments")
    op.drop_index("ix_document_comments_document_id", table_name="document_comments")
    op.drop_index(
        "ix_document_comments_deleted_by_user_id", table_name="document_comments"
    )
    op.drop_index("ix_document_comments_comment_scope", table_name="document_comments")
    op.drop_index("ix_document_comments_author_user_id", table_name="document_comments")
    op.drop_table("document_comments")
    op.drop_table("document_approvals")
    op.drop_table("chat_session_references")
    op.drop_table("chat_messages")
    op.drop_index(
        "ix_platform_document_chunks_platform_document_id",
        table_name="platform_document_chunks",
    )
    op.drop_index(
        "ix_platform_doc_chunks_source_type", table_name="platform_document_chunks"
    )
    op.drop_index(
        "ix_platform_doc_chunks_chunk_type", table_name="platform_document_chunks"
    )
    op.drop_table("platform_document_chunks")
    op.drop_table("notifications")
    op.drop_table("group_members")
    op.drop_index("ix_export_jobs_user_id", table_name="export_jobs")
    op.drop_index("ix_export_jobs_user_group_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_id", table_name="export_jobs")
    op.drop_index("ix_export_jobs_group_id", table_name="export_jobs")
    op.drop_index("ix_export_jobs_expires_at", table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_index("ix_documents_uploader_user_id", table_name="documents")
    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("chat_sessions")
    op.drop_table("subscriptions")
    op.drop_table("social_accounts")
    op.drop_index(
        "ix_platform_sync_failures_sync_run_id", table_name="platform_sync_failures"
    )
    op.drop_index(
        "ix_platform_sync_failures_source_type", table_name="platform_sync_failures"
    )
    op.drop_index(
        "ix_platform_sync_failures_created_at", table_name="platform_sync_failures"
    )
    op.drop_table("platform_sync_failures")
    op.drop_index("ix_platform_documents_source_type", table_name="platform_documents")
    op.drop_index(
        "ix_platform_documents_raw_source_id", table_name="platform_documents"
    )
    op.drop_index("ix_platform_documents_issued_at", table_name="platform_documents")
    op.drop_index("ix_platform_documents_external_id", table_name="platform_documents")
    op.drop_table("platform_documents")
    op.drop_table("notification_settings")
    op.drop_table("groups")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_platform_sync_runs_started_at", table_name="platform_sync_runs")
    op.drop_index("ix_platform_sync_runs_source_type", table_name="platform_sync_runs")
    op.drop_table("platform_sync_runs")
    op.drop_index(
        "ix_platform_raw_sources_source_type", table_name="platform_raw_sources"
    )
    op.drop_index(
        "ix_platform_raw_sources_fetched_at", table_name="platform_raw_sources"
    )
    op.drop_table("platform_raw_sources")
