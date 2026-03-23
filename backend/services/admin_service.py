"""
services/admin_service.py

어드민 관련 비즈니스 로직.
- 통계/사용량 조회
- 판례 등록 / 재처리 / 재인덱싱
- 회원 상태 변경

집계/표시 기준:
  total_users    : GENERAL + is_active=True
  premium_users  : GENERAL + is_active=True + Subscription.plan=PREMIUM + status=ACTIVE
  사용자 목록 plan: ACTIVE PREMIUM → PREMIUM, 나머지 모두 → FREE
  사용자 목록     : GENERAL only (ADMIN 노출 차단)
  사용자 상태변경 : GENERAL only (다른 ADMIN 비활성화 차단)

URL 검증 기준:
  허용 scheme : https
  허용 도메인 : taxlaw.nts.go.kr
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from errors import AppException, ErrorCode
from models.model import (
    Document,
    DocumentStatus,
    Group,
    GroupMember,
    GroupStatus,
    Precedent,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    UserRole,
)
from schemas.admin import (
    AdminPrecedentListResponse,
    AdminStatsResponse,
    AdminUsageResponse,
    AdminUserListResponse,
    DailyUploadItem,
    JobStatusCount,
    PrecedentItem,
    PrecedentSummary,
    RagUsage,
    ServiceUsage,
    StorageInfo,
)

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"https"}
_ALLOWED_DOMAINS = {"taxlaw.nts.go.kr"}


# ── 통계 ──────────────────────────────────────────────────────────────────────


def get_admin_stats(db: Session) -> AdminStatsResponse:
    active_general = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.GENERAL, User.is_active)
        .scalar()
        or 0
    )
    premium_users = (
        db.query(func.count(User.id))
        .join(User.subscription)
        .filter(
            User.role == UserRole.GENERAL,
            User.is_active,
            Subscription.plan == SubscriptionPlan.PREMIUM,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .scalar()
        or 0
    )
    premium_conversion_rate = (
        round(premium_users / active_general * 100, 1) if active_general else 0.0
    )
    active_groups = (
        db.query(func.count(Group.id))
        .filter(Group.status == GroupStatus.ACTIVE)
        .scalar()
        or 0
    )
    total_docs = db.query(func.count(Document.id)).scalar() or 0
    done_docs = (
        db.query(func.count(Document.id))
        .filter(Document.processing_status == DocumentStatus.DONE)
        .scalar()
        or 0
    )
    ai_success_rate = round(done_docs / total_docs * 100, 1) if total_docs else 0.0

    return AdminStatsResponse(
        total_users=active_general,
        premium_users=premium_users,
        premium_conversion_rate=premium_conversion_rate,
        active_groups=active_groups,
        ai_success_rate=ai_success_rate,
        conversion_trend=[],
        ai_trend=[],
    )


# ── 사용량 ────────────────────────────────────────────────────────────────────


def get_admin_usage(db: Session) -> AdminUsageResponse:
    today = datetime.now(timezone.utc).date()
    daily_uploads: list[DailyUploadItem] = []
    for i in range(7):
        day = today - timedelta(days=i)
        cnt = (
            db.query(func.count(Document.id))
            .filter(func.date(Document.created_at) == day)
            .scalar()
            or 0
        )
        daily_uploads.append(DailyUploadItem(date=str(day), count=cnt))

    def _job_counts(status_col) -> JobStatusCount:
        rows = db.query(status_col, func.count()).group_by(status_col).all()
        mapping = {r[0]: r[1] for r in rows}
        return JobStatusCount(
            DONE=mapping.get(DocumentStatus.DONE, 0),
            PROCESSING=mapping.get(DocumentStatus.PROCESSING, 0),
            FAILED=mapping.get(DocumentStatus.FAILED, 0),
        )

    return AdminUsageResponse(
        service_usage=ServiceUsage(
            storage=StorageInfo(used_gb=0.0, limit_gb=10.0),
            daily_uploads=list(reversed(daily_uploads)),
            document_jobs=_job_counts(Document.processing_status),
        ),
        rag_usage=RagUsage(
            precedent_count=db.query(func.count(Precedent.id)).scalar() or 0,
            vector_storage_mb=0.0,
            index_jobs=_job_counts(Precedent.processing_status),
        ),
    )


# ── 판례 ──────────────────────────────────────────────────────────────────────


def get_admin_precedents(
    db: Session, skip: int = 0, limit: int = 20
) -> AdminPrecedentListResponse:
    base = db.query(Precedent)
    total = base.count()

    summary = PrecedentSummary(
        total=total,
        indexed=base.filter(Precedent.processing_status == DocumentStatus.DONE).count(),
        pending=base.filter(
            Precedent.processing_status.in_(
                [DocumentStatus.PENDING, DocumentStatus.PROCESSING]
            )
        ).count(),
        failed=base.filter(
            Precedent.processing_status == DocumentStatus.FAILED
        ).count(),
    )

    items = base.order_by(Precedent.created_at.desc()).offset(skip).limit(limit).all()
    failed_items = (
        base.filter(Precedent.processing_status == DocumentStatus.FAILED)
        .order_by(Precedent.updated_at.desc())
        .limit(5)
        .all()
    )
    pending_items = (
        base.filter(
            Precedent.processing_status.in_(
                [DocumentStatus.PENDING, DocumentStatus.PROCESSING]
            )
        )
        .order_by(Precedent.updated_at.desc())
        .limit(5)
        .all()
    )
    recent_items = (
        base.filter(Precedent.processing_status == DocumentStatus.DONE)
        .order_by(Precedent.updated_at.desc())
        .limit(5)
        .all()
    )
    return AdminPrecedentListResponse(
        summary=summary,
        items=[PrecedentItem.model_validate(p) for p in items],
        failed_items=[PrecedentItem.model_validate(p) for p in failed_items],
        pending_items=[PrecedentItem.model_validate(p) for p in pending_items],
        recent_items=[PrecedentItem.model_validate(p) for p in recent_items],
        total=total,
    )


def create_precedent(db: Session, admin: User, source_url: str) -> Precedent:
    """
    판례 URL을 등록하고 백그라운드 추출 task를 enqueue한다.

    검증 순서:
      1. URL scheme / domain 선검증  → 422
      2. 중복 URL 확인               → 409
      3. PENDING 등록
      4. precedent worker enqueue
    """
    _validate_precedent_url(source_url)

    existing = db.query(Precedent).filter(Precedent.source_url == source_url).first()
    if existing:
        raise AppException(ErrorCode.PRECEDENT_DUPLICATE_URL)

    precedent = Precedent(
        source_url=source_url,
        processing_status=DocumentStatus.PENDING,
        uploaded_by_admin_id=admin.id,
    )
    db.add(precedent)
    db.commit()
    db.refresh(precedent)

    _enqueue_precedent_processing()

    return precedent


def retry_precedent(db: Session, precedent_id: int) -> Precedent:
    """FAILED 상태 판례를 재처리한다."""
    precedent = db.query(Precedent).filter(Precedent.id == precedent_id).first()
    if not precedent:
        raise AppException(ErrorCode.PRECEDENT_NOT_FOUND)

    precedent.processing_status = DocumentStatus.PENDING
    precedent.error_message = None
    precedent.title = None
    precedent.text = None
    db.commit()
    db.refresh(precedent)
    _enqueue_precedent_processing()

    return precedent


def reindex_precedents(db: Session) -> dict:
    """DONE 상태인 모든 판례를 재인덱싱한다."""
    precedents = (
        db.query(Precedent)
        .filter(
            Precedent.processing_status == DocumentStatus.DONE,
            Precedent.text.isnot(None),
        )
        .all()
    )
    for p in precedents:
        _enqueue_index(p.id)
    return {"enqueued": len(precedents)}


# ── 회원 ──────────────────────────────────────────────────────────────────────


def get_admin_users(
    db: Session,
    search: str = "",
    plan: str = "",
    skip: int = 0,
    limit: int = 20,
) -> AdminUserListResponse:
    from schemas.admin import AdminUserItem

    # GENERAL만 조회 — ADMIN 계정은 목록에 노출하지 않음
    query = db.query(User).filter(User.role == UserRole.GENERAL)

    if search:
        query = query.filter(
            User.username.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )
    if plan:
        try:
            plan_enum = SubscriptionPlan[plan.upper()]
            if plan_enum == SubscriptionPlan.PREMIUM:
                # ACTIVE PREMIUM만 필터 — INACTIVE/CANCELLED는 FREE로 간주
                query = query.join(User.subscription).filter(
                    Subscription.plan == SubscriptionPlan.PREMIUM,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                )
            else:
                # FREE 필터: 구독 없거나, PREMIUM이 아니거나, ACTIVE가 아닌 경우
                query = query.outerjoin(User.subscription).filter(
                    (Subscription.id.is_(None))
                    | (Subscription.plan != SubscriptionPlan.PREMIUM)
                    | (Subscription.status != SubscriptionStatus.ACTIVE)
                )
        except KeyError:
            pass

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    items = []
    for user in users:
        sub = user.subscription
        # ACTIVE PREMIUM만 PREMIUM, 나머지는 FREE
        is_active_premium = (
            sub is not None
            and sub.plan == SubscriptionPlan.PREMIUM
            and sub.status == SubscriptionStatus.ACTIVE
        )
        plan_val = (
            SubscriptionPlan.PREMIUM.value
            if is_active_premium
            else SubscriptionPlan.FREE.value
        )
        active_group_count = (
            db.query(func.count(GroupMember.id))
            .join(Group, GroupMember.group_id == Group.id)
            .filter(
                GroupMember.user_id == user.id,
                Group.status == GroupStatus.ACTIVE,
            )
            .scalar()
            or 0
        )
        items.append(
            AdminUserItem(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role.value,
                is_active=user.is_active,
                plan=plan_val,
                active_group_count=active_group_count,
                created_at=user.created_at,
            )
        )

    return AdminUserListResponse(items=items, total=total)


def update_admin_user_status(
    db: Session, user_id: int, is_active: bool, current_admin: User
) -> User:
    if user_id == current_admin.id:
        raise AppException(ErrorCode.AUTH_FORBIDDEN)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)

    if user.role == UserRole.ADMIN:
        raise AppException(ErrorCode.AUTH_FORBIDDEN)

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────


def _validate_precedent_url(url: str) -> None:
    """scheme과 domain을 사전 검증한다. 실패 시 AppException 발생."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise AppException(ErrorCode.PRECEDENT_INVALID_URL)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise AppException(ErrorCode.PRECEDENT_INVALID_URL)

    if parsed.netloc not in _ALLOWED_DOMAINS:
        raise AppException(ErrorCode.PRECEDENT_DOMAIN_NOT_ALLOWED)


def _enqueue_precedent_processing() -> None:
    """precedent 추출 worker를 깨운다. 지연 import로 순환 참조 방지."""
    try:
        from tasks.precedent_task import process_next_pending_precedent

        process_next_pending_precedent.delay()
    except Exception as exc:
        logger.error("precedent 처리 task enqueue 실패: error=%s", exc)


def _enqueue_index(precedent_id: int) -> None:
    """인덱싱 Celery task를 enqueue한다. 지연 import로 순환 참조 방지."""
    try:
        from tasks.precedent_task import index_precedent

        index_precedent.delay(precedent_id)
        logger.info("인덱싱 task enqueue: precedent_id=%s", precedent_id)
    except Exception as exc:
        logger.error(
            "인덱싱 task enqueue 실패: precedent_id=%s, error=%s", precedent_id, exc
        )
