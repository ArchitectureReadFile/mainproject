from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from domains.admin import platform_service as admin_platform_service
from domains.admin import service as admin_service
from domains.admin.schemas import (
    AdminPlatformFailuresResponse,
    AdminPlatformStopRequest,
    AdminPlatformStopResponse,
    AdminPlatformSummaryResponse,
    AdminPlatformSyncRequest,
    AdminPlatformSyncResponse,
    AdminStatsResponse,
    AdminUsageResponse,
    AdminUserListResponse,
    AdminUserUpdateRequest,
)
from domains.auth.router import get_current_user
from errors import AppException, ErrorCode
from models.model import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """ADMIN role이 아니면 403 반환"""
    if current_user.role != UserRole.ADMIN:
        raise AppException(ErrorCode.AUTH_FORBIDDEN)
    return current_user


# ── 개요 ──────────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_service.get_admin_stats(db)


# ── 사용량 ────────────────────────────────────────────────────────────────────


@router.get("/usage", response_model=AdminUsageResponse)
def get_usage(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_service.get_admin_usage(db)


# ── platform sync ────────────────────────────────────────────────────────────


@router.get("/platform/summary", response_model=AdminPlatformSummaryResponse)
def get_platform_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_platform_service.get_admin_platform_summary(db)


@router.post(
    "/platform/sync",
    response_model=AdminPlatformSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_platform_source(
    payload: AdminPlatformSyncRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_platform_service.enqueue_platform_source_sync(
        db,
        source_type=payload.source_type,
    )


@router.post(
    "/platform/sync/stop",
    response_model=AdminPlatformStopResponse,
    status_code=status.HTTP_200_OK,
)
def stop_platform_source(
    payload: AdminPlatformStopRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_platform_service.stop_platform_source_sync(
        db,
        source_type=payload.source_type,
    )


@router.get("/platform/failures", response_model=AdminPlatformFailuresResponse)
def get_platform_failures(
    source_type: str = Query(default=None),
    run_id: int = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_platform_service.get_admin_platform_failures(
        db,
        source_type=source_type,
        run_id=run_id,
        limit=limit,
    )


# ── 회원 ──────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    search: str = Query(default=""),
    plan: str = Query(default=""),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_service.get_admin_users(
        db, search=search, plan=plan, skip=skip, limit=limit
    )


@router.patch("/users/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),  # current_admin 전달
):
    user, effective_plan = admin_service.update_admin_user(
        db,
        user_id,
        current_admin=current_user,
        is_active=payload.is_active,
        plan=payload.plan,
    )
    return {"id": user.id, "is_active": user.is_active, "plan": effective_plan}
