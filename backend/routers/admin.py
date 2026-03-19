from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from errors import AppException, ErrorCode
from models.model import User, UserRole
from routers.auth import get_current_user
from schemas.admin import (
    AdminPrecedentCreateRequest,
    AdminPrecedentListResponse,
    AdminStatsResponse,
    AdminUsageResponse,
    AdminUserListResponse,
    AdminUserStatusUpdateRequest,
)
from services import admin_service

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


# ── 판례 ──────────────────────────────────────────────────────────────────────


@router.get("/precedents", response_model=AdminPrecedentListResponse)
def list_precedents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_service.get_admin_precedents(db, skip=skip, limit=limit)


@router.post("/precedents", status_code=status.HTTP_201_CREATED)
def create_precedent(
    payload: AdminPrecedentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    precedent = admin_service.create_precedent(db, current_user, payload.source_url)
    return {
        "id": precedent.id,
        "source_url": precedent.source_url,
        "processing_status": precedent.processing_status.value,
        "error_message": precedent.error_message,
    }


@router.post("/precedents/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex_precedents(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return admin_service.reindex_precedents(db)


@router.post("/precedents/{precedent_id}/retry", status_code=status.HTTP_200_OK)
def retry_precedent(
    precedent_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    precedent = admin_service.retry_precedent(db, precedent_id)
    return {
        "id": precedent.id,
        "processing_status": precedent.processing_status.value,
        "error_message": precedent.error_message,
    }


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
def update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),  # current_admin 전달
):
    user = admin_service.update_admin_user_status(
        db, user_id, payload.is_active, current_admin=current_user
    )
    return {"id": user.id, "is_active": user.is_active}
