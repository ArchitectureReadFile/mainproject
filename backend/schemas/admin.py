from datetime import datetime
from typing import Optional

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


# ── 판례 (precedents) ─────────────────────────────────────────────────────────


class PrecedentSummary(BaseModel):
    total: int
    indexed: int
    pending: int
    failed: int


class PrecedentItem(BaseModel):
    id: int
    source_url: str
    title: Optional[str]
    processing_status: str
    error_message: Optional[str]
    uploaded_by_admin_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminPrecedentListResponse(BaseModel):
    summary: PrecedentSummary
    items: list[PrecedentItem]
    failed_items: list[PrecedentItem]
    pending_items: list[PrecedentItem]
    recent_items: list[PrecedentItem]
    total: int


class AdminPrecedentCreateRequest(BaseModel):
    source_url: str


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
