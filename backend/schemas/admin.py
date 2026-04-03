from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

# ── 개요 (stats) ─────────────────────────────────────────────────────────────


class ConversionTrendItem(BaseModel):
    date: str
    rate: float


class AiTrendItem(BaseModel):
    date: str
    requests: int
    failure_rate: float


class AdminStatsResponse(BaseModel):
    total_users: int
    premium_users: int
    premium_conversion_rate: float
    active_groups: int
    ai_success_rate: float
    conversion_trend: list[ConversionTrendItem]
    ai_trend: list[AiTrendItem]


# ── 사용량 (usage) ────────────────────────────────────────────────────────────


class StorageInfo(BaseModel):
    used_gb: float
    limit_gb: float


class DailyUploadItem(BaseModel):
    date: str
    count: int


class JobStatusCount(BaseModel):
    DONE: int
    PROCESSING: int
    FAILED: int


class ServiceUsage(BaseModel):
    storage: StorageInfo
    daily_uploads: list[DailyUploadItem]
    document_jobs: JobStatusCount


class RagUsage(BaseModel):
    precedent_count: int
    vector_storage_mb: float
    index_jobs: JobStatusCount


class AdminUsageResponse(BaseModel):
    service_usage: ServiceUsage
    rag_usage: RagUsage


# ── platform sync ────────────────────────────────────────────────────────────

AdminPlatformSourceType = Literal["law", "precedent", "interpretation", "admin_rule"]


class AdminPlatformSourceSummary(BaseModel):
    source_type: AdminPlatformSourceType
    label: str
    document_count: int
    chunk_count: int
    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_message: Optional[str] = None
    fetched_count: int = 0
    created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    current_page: Optional[int] = None
    total_count: Optional[int] = None
    last_external_id: Optional[str] = None
    last_display_title: Optional[str] = None


class AdminPlatformRecentItem(BaseModel):
    id: int
    source_type: AdminPlatformSourceType
    display_title: Optional[str]
    external_id: str
    issued_at: Optional[datetime]
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminPlatformSummaryResponse(BaseModel):
    total_documents: int
    total_chunks: int
    sources: list[AdminPlatformSourceSummary]
    recent_items: list[AdminPlatformRecentItem]


class AdminPlatformSyncRequest(BaseModel):
    source_type: AdminPlatformSourceType


class AdminPlatformSyncResponse(BaseModel):
    run_id: int
    source_type: AdminPlatformSourceType
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: Literal["queued", "running", "success", "no_changes", "failed", "cancelled"]
    fetched: int
    created: int
    skipped: int
    failed: int
    message: str


class AdminPlatformStopRequest(BaseModel):
    source_type: AdminPlatformSourceType


class AdminPlatformStopResponse(BaseModel):
    run_id: int
    source_type: AdminPlatformSourceType
    status: Literal["cancelled", "not_found"]
    message: str


# ── platform sync failures ────────────────────────────────────────────────────


class AdminPlatformFailureItem(BaseModel):
    id: int
    sync_run_id: int
    source_type: AdminPlatformSourceType
    external_id: Optional[str] = None
    display_title: Optional[str] = None
    detail_link: Optional[str] = None
    page: Optional[int] = None
    error_type: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminPlatformFailuresResponse(BaseModel):
    items: list[AdminPlatformFailureItem]
    total: int


# ── 회원 (users) ──────────────────────────────────────────────────────────────


class AdminUserItem(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    plan: str
    active_group_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int


class AdminUserStatusUpdateRequest(BaseModel):
    is_active: bool
