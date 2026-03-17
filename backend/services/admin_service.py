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

# 허용된 판례 도메인 — 실제 크롤링 가능한 도메인만 등록
ALLOWED_PRECEDENT_DOMAINS = {
    "www.law.go.kr",
    "casenote.kr",
    "lbox.kr",
    "glaw.scourt.go.kr",
}

# 허용 scheme — 수집 파이프라인이 http/https만 처리
ALLOWED_SCHEMES = {"http", "https"}


def _today_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_precedent_domain(source_url: str) -> None:
    """scheme + 허용 도메인 검증 — 둘 중 하나라도 불일치하면 거부"""
    try:
        parsed = urlparse(source_url)
        scheme = parsed.scheme.lower()
        domain = parsed.netloc.lower()
    except Exception:
        raise AppException(ErrorCode.PRECEDENT_INVALID_URL)

    if not scheme or not domain:
        raise AppException(ErrorCode.PRECEDENT_INVALID_URL)

    if scheme not in ALLOWED_SCHEMES:
        raise AppException(ErrorCode.PRECEDENT_INVALID_URL)

    if domain not in ALLOWED_PRECEDENT_DOMAINS:
        raise AppException(ErrorCode.PRECEDENT_DOMAIN_NOT_ALLOWED)


# ── 개요 ──────────────────────────────────────────────────────────────────────


def get_admin_stats(db: Session) -> dict:
    # 전체 회원 (ADMIN 제외)
    total_users = (
        db.query(func.count(User.id)).filter(User.role == UserRole.GENERAL).scalar()
        or 0
    )

    # 프리미엄 회원 — GENERAL 사용자 중 plan=PREMIUM AND status=ACTIVE
    # User join으로 GENERAL 강제 — 운영 계정/잘못된 데이터로 인한 전환율 왜곡 방지
    premium_users = (
        db.query(func.count(Subscription.id))
        .join(User, User.id == Subscription.user_id)
        .filter(
            User.role == UserRole.GENERAL,
            Subscription.plan == SubscriptionPlan.PREMIUM,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .scalar()
        or 0
    )
    premium_conversion_rate = round(
        (premium_users / total_users * 100) if total_users else 0.0, 1
    )

    # 활성 워크스페이스 수 — groups.status=ACTIVE
    active_groups = (
        db.query(func.count(Group.id))
        .filter(Group.status == GroupStatus.ACTIVE)
        .scalar()
        or 0
    )

    # AI 처리 성공률 — documents.status 기준 DONE / (DONE + FAILED)
    done_count = (
        db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.DONE)
        .scalar()
        or 0
    )
    failed_count = (
        db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.FAILED)
        .scalar()
        or 0
    )
    total_finished = done_count + failed_count
    ai_success_rate = round(
        (done_count / total_finished * 100) if total_finished else 100.0, 1
    )

    # 전환률 추이 — 최근 7일 일별 PREMIUM ACTIVE 구독자 수 기반
    today = _today_naive()
    conversion_trend = []
    for i in range(7):
        day = today - timedelta(days=6 - i)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        day_premium = (
            db.query(func.count(Subscription.id))
            .join(User, User.id == Subscription.user_id)
            .filter(
                User.role == UserRole.GENERAL,
                Subscription.plan == SubscriptionPlan.PREMIUM,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.created_at <= day_end,
            )
            .scalar()
            or 0
        )
        day_total = (
            db.query(func.count(User.id))
            .filter(
                User.role == UserRole.GENERAL,
                User.created_at <= day_end,
            )
            .scalar()
            or 0
        )
        rate = round((day_premium / day_total * 100) if day_total else 0.0, 1)
        conversion_trend.append({"date": day.strftime("%Y-%m-%d"), "rate": rate})

    # AI 요청량/실패율 추이 — created_at 기준 전체 문서 수 (상태 무관)
    ai_trend = []
    for i in range(7):
        day = today - timedelta(days=6 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_requests = (
            db.query(func.count(Document.id))
            .filter(
                Document.created_at >= day_start,
                Document.created_at < day_end,
            )
            .scalar()
            or 0
        )
        day_failed = (
            db.query(func.count(Document.id))
            .filter(
                Document.status == DocumentStatus.FAILED,
                Document.created_at >= day_start,
                Document.created_at < day_end,
            )
            .scalar()
            or 0
        )
        failure_rate = round(
            (day_failed / day_requests * 100) if day_requests else 0.0, 1
        )
        ai_trend.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "requests": day_requests,
                "failure_rate": failure_rate,
            }
        )

    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "premium_conversion_rate": premium_conversion_rate,
        "active_groups": active_groups,
        "ai_success_rate": ai_success_rate,
        "conversion_trend": conversion_trend,
        "ai_trend": ai_trend,
    }


# ── 사용량 ────────────────────────────────────────────────────────────────────


def get_admin_usage(db: Session) -> dict:
    today = _today_naive()

    # storage.used_gb — Document에 파일 크기 필드 없음
    # TODO: S3/로컬 스토리지 크기 합산 연동 후 교체
    storage = {"used_gb": 0.0, "limit_gb": 200.0}

    # 최근 7일 일별 업로드 추이
    daily_uploads = []
    for i in range(7):
        day = today - timedelta(days=6 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        count = (
            db.query(func.count(Document.id))
            .filter(
                Document.created_at >= day_start,
                Document.created_at < day_end,
            )
            .scalar()
            or 0
        )
        daily_uploads.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    # 문서 처리 상태 분포
    document_jobs = {
        "DONE": db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.DONE)
        .scalar()
        or 0,
        "PROCESSING": db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.PROCESSING)
        .scalar()
        or 0,
        "FAILED": db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.FAILED)
        .scalar()
        or 0,
    }

    # RAG 판례 집계
    precedent_count = db.query(func.count(Precedent.id)).scalar() or 0
    index_jobs = {
        "DONE": db.query(func.count(Precedent.id))
        .filter(Precedent.processing_status == DocumentStatus.DONE)
        .scalar()
        or 0,
        "PROCESSING": db.query(func.count(Precedent.id))
        .filter(Precedent.processing_status == DocumentStatus.PROCESSING)
        .scalar()
        or 0,
        "FAILED": db.query(func.count(Precedent.id))
        .filter(Precedent.processing_status == DocumentStatus.FAILED)
        .scalar()
        or 0,
    }

    # vector_storage_mb — 벡터 DB 미연동
    # TODO: 벡터 DB(예: Qdrant/Weaviate) 크기 조회 API 연동 후 교체
    vector_storage_mb = 0.0

    return {
        "service_usage": {
            "storage": storage,
            "daily_uploads": daily_uploads,
            "document_jobs": document_jobs,
        },
        "rag_usage": {
            "precedent_count": precedent_count,
            "vector_storage_mb": vector_storage_mb,
            "index_jobs": index_jobs,
        },
    }


# ── 판례 ──────────────────────────────────────────────────────────────────────


def get_admin_precedents(db: Session, skip: int = 0, limit: int = 20) -> dict:
    base_query = db.query(Precedent)
    total = base_query.count()

    summary = {
        "total": total,
        "indexed": base_query.filter(
            Precedent.processing_status == DocumentStatus.DONE
        ).count(),
        "pending": base_query.filter(
            Precedent.processing_status.in_(
                [DocumentStatus.PENDING, DocumentStatus.PROCESSING]
            )
        ).count(),
        "failed": base_query.filter(
            Precedent.processing_status == DocumentStatus.FAILED
        ).count(),
    }

    items = (
        base_query.order_by(Precedent.updated_at.desc()).offset(skip).limit(limit).all()
    )

    return {"summary": summary, "items": items, "total": total}


def create_precedent(db: Session, admin_user: User, source_url: str) -> Precedent:
    _validate_precedent_domain(source_url)

    existing = db.query(Precedent).filter(Precedent.source_url == source_url).first()
    if existing:
        raise AppException(ErrorCode.PRECEDENT_DUPLICATE_URL)

    precedent = Precedent(
        source_url=source_url,
        processing_status=DocumentStatus.PENDING,
        uploaded_by_admin_id=admin_user.id,
    )
    db.add(precedent)
    db.commit()
    db.refresh(precedent)

    # TODO: 벡터화 파이프라인 background task 연결
    return precedent


def retry_precedent(db: Session, precedent_id: int) -> Precedent:
    precedent = db.query(Precedent).filter(Precedent.id == precedent_id).first()
    if not precedent:
        raise AppException(ErrorCode.PRECEDENT_NOT_FOUND)

    precedent.processing_status = DocumentStatus.PENDING
    precedent.error_message = None
    precedent.updated_at = _today_naive()
    db.commit()
    db.refresh(precedent)

    # TODO: 벡터화 파이프라인 background task 연결
    return precedent


def reindex_precedents(db: Session) -> dict:
    # TODO: 전체 재색인 background task 연결
    return {"message": "인덱스 재생성 요청이 접수되었습니다."}


# ── 회원 ──────────────────────────────────────────────────────────────────────


def get_admin_users(
    db: Session,
    search: str = "",
    plan: str = "",
    skip: int = 0,
    limit: int = 20,
) -> dict:
    query = (
        db.query(User, Subscription)
        .outerjoin(Subscription, Subscription.user_id == User.id)
        .filter(User.role == UserRole.GENERAL)
    )

    if search:
        query = query.filter(
            User.username.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )

    # plan 필터 — plan_value 계산 기준과 일치하도록 status도 함께 검사
    if plan == "PREMIUM":
        # ACTIVE PREMIUM만
        query = query.filter(
            Subscription.plan == SubscriptionPlan.PREMIUM,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    elif plan == "FREE":
        # 구독 없음 OR 비활성 구독 OR FREE 플랜
        # INACTIVE/CANCELLED 된 PREMIUM도 표시상 FREE이므로 여기에 포함
        query = query.filter(
            (Subscription.id == None)  # noqa: E711
            | (Subscription.status != SubscriptionStatus.ACTIVE)
            | (Subscription.plan == SubscriptionPlan.FREE)
        )

    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    # 사용자별 활성 그룹 수
    user_ids = [user.id for user, _ in rows]
    active_group_counts = {}
    if user_ids:
        counts = (
            db.query(GroupMember.user_id, func.count(GroupMember.id))
            .join(Group, Group.id == GroupMember.group_id)
            .filter(
                GroupMember.user_id.in_(user_ids),
                Group.status == GroupStatus.ACTIVE,
            )
            .group_by(GroupMember.user_id)
            .all()
        )
        active_group_counts = {uid: cnt for uid, cnt in counts}

    items = []
    for user, subscription in rows:
        # ACTIVE 구독이 PREMIUM일 때만 PREMIUM으로 표시 — 필터 기준과 동일
        plan_value = (
            subscription.plan.value
            if subscription
            and subscription.status == SubscriptionStatus.ACTIVE
            and subscription.plan == SubscriptionPlan.PREMIUM
            else "FREE"
        )
        items.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "is_active": user.is_active,
                "plan": plan_value,
                "active_group_count": active_group_counts.get(user.id, 0),
                "created_at": user.created_at,
            }
        )

    return {"items": items, "total": total}


def update_admin_user_status(
    db: Session, user_id: int, is_active: bool, current_admin: User
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)

    # ADMIN 계정 변경 차단 (자기 자신 포함)
    if user.role == UserRole.ADMIN:
        raise AppException(ErrorCode.AUTH_FORBIDDEN)

    # 자기 자신 비활성화 차단
    if user.id == current_admin.id:
        raise AppException(ErrorCode.AUTH_FORBIDDEN)

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
