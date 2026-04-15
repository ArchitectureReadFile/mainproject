"""
seed_admin.py — admin 화면 테스트용 초기 데이터 주입 스크립트

실행 방법:
    cd backend
    python seed_admin.py
    python seed_admin.py --with-admin
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

sys.path.insert(0, os.path.dirname(__file__))

from database import Base, SessionLocal, init_db
from domains.auth.service import AuthService
from models.model import (
    Document,
    DocumentLifecycleStatus,
    DocumentStatus,
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    UserRole,
)

_auth_service = AuthService()

# ── 설정 ──────────────────────────────────────────────────────────────────────

SEED_EMAIL_DOMAIN = "@seed.test"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "test1234"


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=n)


# ── 더미 데이터 정의 ──────────────────────────────────────────────────────────

SEED_USERS = [
    {
        "email": f"kim{SEED_EMAIL_DOMAIN}",
        "username": "김대표",
        "is_active": True,
        "days_ago": 30,
    },
    {
        "email": f"lee{SEED_EMAIL_DOMAIN}",
        "username": "이변호",
        "is_active": True,
        "days_ago": 25,
    },
    {
        "email": f"park{SEED_EMAIL_DOMAIN}",
        "username": "박사무",
        "is_active": True,
        "days_ago": 20,
    },
    {
        "email": f"choi{SEED_EMAIL_DOMAIN}",
        "username": "최팀장",
        "is_active": True,
        "days_ago": 18,
    },
    {
        "email": f"jung{SEED_EMAIL_DOMAIN}",
        "username": "정과장",
        "is_active": True,
        "days_ago": 15,
    },
    {
        "email": f"han{SEED_EMAIL_DOMAIN}",
        "username": "한변리",
        "is_active": True,
        "days_ago": 12,
    },
    {
        "email": f"yoon{SEED_EMAIL_DOMAIN}",
        "username": "윤사원",
        "is_active": False,
        "days_ago": 10,
    },
    {
        "email": f"lim{SEED_EMAIL_DOMAIN}",
        "username": "임인턴",
        "is_active": False,
        "days_ago": 7,
    },
    {
        "email": f"kwon{SEED_EMAIL_DOMAIN}",
        "username": "권대리",
        "is_active": True,
        "days_ago": 5,
    },
    {
        "email": f"shin{SEED_EMAIL_DOMAIN}",
        "username": "신주임",
        "is_active": True,
        "days_ago": 3,
    },
]

# (email, plan, status, days_ago)
SEED_SUBSCRIPTIONS = [
    (f"kim{SEED_EMAIL_DOMAIN}", "PREMIUM", "ACTIVE", 28),
    (f"lee{SEED_EMAIL_DOMAIN}", "PREMIUM", "ACTIVE", 23),
    (f"park{SEED_EMAIL_DOMAIN}", "PREMIUM", "ACTIVE", 18),
    (f"choi{SEED_EMAIL_DOMAIN}", "PREMIUM", "EXPIRED", 16),
    (f"jung{SEED_EMAIL_DOMAIN}", "FREE", "ACTIVE", 14),
    (f"han{SEED_EMAIL_DOMAIN}", "PREMIUM", "CANCELED", 10),
    (f"kwon{SEED_EMAIL_DOMAIN}", "FREE", "ACTIVE", 4),
    (f"shin{SEED_EMAIL_DOMAIN}", "PREMIUM", "ACTIVE", 2),
]

# (name, owner_email, status)
SEED_GROUPS = [
    ("법무법인 알파", f"kim{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("변호사 이팀", f"lee{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("박사무소 A", f"park{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("최팀장 그룹", f"choi{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("구 한변리 사무소", f"han{SEED_EMAIL_DOMAIN}", "DELETE_PENDING"),
]

# (group_name, member_emails)
SEED_GROUP_MEMBERS = [
    ("법무법인 알파", [f"lee{SEED_EMAIL_DOMAIN}", f"jung{SEED_EMAIL_DOMAIN}"]),
    ("변호사 이팀", [f"park{SEED_EMAIL_DOMAIN}", f"kwon{SEED_EMAIL_DOMAIN}"]),
    ("박사무소 A", [f"shin{SEED_EMAIL_DOMAIN}"]),
    ("최팀장 그룹", [f"jung{SEED_EMAIL_DOMAIN}", f"han{SEED_EMAIL_DOMAIN}"]),
]

# (user_email, processing_status, days_ago)
SEED_DOCUMENTS = [
    (f"kim{SEED_EMAIL_DOMAIN}", "DONE", 0),
    (f"lee{SEED_EMAIL_DOMAIN}", "DONE", 0),
    (f"park{SEED_EMAIL_DOMAIN}", "PROCESSING", 0),
    (f"choi{SEED_EMAIL_DOMAIN}", "FAILED", 0),
    (f"kim{SEED_EMAIL_DOMAIN}", "DONE", 1),
    (f"lee{SEED_EMAIL_DOMAIN}", "DONE", 1),
    (f"jung{SEED_EMAIL_DOMAIN}", "DONE", 1),
    (f"han{SEED_EMAIL_DOMAIN}", "FAILED", 1),
]


# ── reset ────────────────────────────────────────────────────────────────────


def reset_seed_data(db):
    print("  기존 seed 데이터 삭제 중...")
    _reset_rag_storage()

    tables = [table for table in reversed(Base.metadata.sorted_tables)]
    for table in tables:
        db.execute(delete(table))
    db.commit()
    print("  삭제 완료")


def _reset_rag_storage():
    try:
        from domains.rag import bm25_store, vector_store

        bm25_store.clear()
        vector_store.clear()
    except Exception as exc:
        print(f"  [WARN] RAG 저장소 초기화 실패: {exc}")


# ── users / subscriptions ────────────────────────────────────────────────────


def seed_users(db) -> dict[str, User]:
    user_map: dict[str, User] = {}

    for item in SEED_USERS:
        existing = db.query(User).filter(User.email == item["email"]).first()
        if existing:
            print(f"  [SKIP] user {item['email']}")
            user_map[item["email"]] = existing
            continue

        user = User(
            email=item["email"],
            username=item["username"],
            password=_auth_service.hash_password("Test1234!"),
            role=UserRole.GENERAL,
            is_active=item["is_active"],
            created_at=_days_ago(item["days_ago"]),
            updated_at=_days_ago(item["days_ago"]),
        )
        db.add(user)
        db.flush()
        user_map[item["email"]] = user
        print(f"  [OK]   user {item['email']} ({item['username']})")

    db.commit()
    return user_map


def seed_subscriptions(db, user_map: dict[str, User]):
    for email, plan, status, days_ago in SEED_SUBSCRIPTIONS:
        user = user_map.get(email)
        if not user:
            continue

        existing = (
            db.query(Subscription).filter(Subscription.user_id == user.id).first()
        )
        if existing:
            print(f"  [SKIP] subscription {email}")
            continue

        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan(plan),
            status=SubscriptionStatus(status),
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            created_at=_days_ago(days_ago),
            updated_at=_days_ago(days_ago),
        )
        db.add(sub)
        print(f"  [OK]   subscription {email} → {plan}/{status}")

    db.commit()


# ── groups ───────────────────────────────────────────────────────────────────


def seed_groups(db, user_map: dict[str, User]) -> dict[str, Group]:
    group_map: dict[str, Group] = {}

    for name, owner_email, status in SEED_GROUPS:
        owner = user_map.get(owner_email)
        if not owner:
            continue

        existing = (
            db.query(Group)
            .filter(Group.name == name, Group.owner_user_id == owner.id)
            .first()
        )
        if existing:
            print(f"  [SKIP] group '{name}'")
            group_map[name] = existing
            continue

        group = Group(
            owner_user_id=owner.id,
            name=name,
            status=GroupStatus(status),
        )
        db.add(group)
        db.flush()

        owner_membership = GroupMember(
            user_id=owner.id,
            group_id=group.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
            joined_at=group.created_at or _days_ago(0),
        )
        db.add(owner_membership)

        group_map[name] = group
        print(f"  [OK]   group '{name}' ({status})")

    db.commit()
    return group_map


def seed_group_members(db, user_map: dict[str, User], group_map: dict[str, Group]):
    for group_name, member_emails in SEED_GROUP_MEMBERS:
        group = group_map.get(group_name)
        if not group:
            continue

        for email in member_emails:
            user = user_map.get(email)
            if not user:
                continue

            existing = (
                db.query(GroupMember)
                .filter(
                    GroupMember.group_id == group.id,
                    GroupMember.user_id == user.id,
                )
                .first()
            )
            if existing:
                print(f"  [SKIP] member {email} → '{group_name}'")
                continue

            db.add(
                GroupMember(
                    group_id=group.id,
                    user_id=user.id,
                    role=MembershipRole.EDITOR,
                    status=MembershipStatus.ACTIVE,
                    invited_by_user_id=group.owner_user_id,
                    joined_at=_days_ago(0),
                )
            )
            print(f"  [OK]   member {email} → '{group_name}'")

    db.commit()


# ── documents ────────────────────────────────────────────────────────────────


def _pick_group_for_user(db, user_id: int) -> Group | None:
    membership = (
        db.query(GroupMember)
        .join(Group, Group.id == GroupMember.group_id)
        .filter(
            GroupMember.user_id == user_id,
            GroupMember.status == MembershipStatus.ACTIVE,
            Group.status == GroupStatus.ACTIVE,
        )
        .first()
    )
    if membership:
        return db.query(Group).filter(Group.id == membership.group_id).first()

    return db.query(Group).filter(Group.owner_user_id == user_id).first()


def seed_documents(db, user_map: dict[str, User]):
    for i, (email, status, days_ago) in enumerate(SEED_DOCUMENTS):
        user = user_map.get(email)
        if not user:
            continue

        group = _pick_group_for_user(db, user.id)
        if not group:
            print(f"  [SKIP] document seed_{i:03d} (group 없음: {email})")
            continue

        stored_path = f"https://storage.seed.test/docs/seed_{i:03d}.pdf"
        existing = (
            db.query(Document).filter(Document.stored_path == stored_path).first()
        )
        if existing:
            print(f"  [SKIP] document seed_{i:03d}")
            continue

        created = _days_ago(days_ago).replace(hour=9 + (i % 8), minute=i % 60)
        doc = Document(
            group_id=group.id,
            uploader_user_id=user.id,
            original_filename=f"seed_{i:03d}.pdf",
            stored_path=stored_path,
            title=f"seed_{i:03d}",
            processing_status=DocumentStatus(status),
            lifecycle_status=DocumentLifecycleStatus.ACTIVE,
            created_at=created,
            updated_at=created,
        )
        db.add(doc)
        print(f"  [OK]   document seed_{i:03d} ({status}, {days_ago}일 전)")

    db.commit()


# ── admin / precedents ───────────────────────────────────────────────────────


def seed_admin(db) -> User | None:
    existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if existing:
        print(f"  [SKIP] admin {ADMIN_EMAIL}")
        return existing

    admin = User(
        email=ADMIN_EMAIL,
        username="시드관리자",
        password=_auth_service.hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"  [OK]   admin {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    return admin


def seed_admin_subscription(db, admin: User):
    """admin 계정에 PREMIUM/ACTIVE 구독을 upsert 처리."""
    existing = db.query(Subscription).filter(Subscription.user_id == admin.id).first()

    if existing:
        changed = False
        if existing.plan != SubscriptionPlan.PREMIUM:
            existing.plan = SubscriptionPlan.PREMIUM
            changed = True
        if existing.status != SubscriptionStatus.ACTIVE:
            existing.status = SubscriptionStatus.ACTIVE
            changed = True

        if changed:
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            print("  [UPDATE] admin subscription → PREMIUM/ACTIVE (기존 구독 보정)")
        else:
            print("  [SKIP] admin subscription (이미 PREMIUM/ACTIVE)")
        return

    sub = Subscription(
        user_id=admin.id,
        plan=SubscriptionPlan.PREMIUM,
        status=SubscriptionStatus.ACTIVE,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(sub)
    db.commit()
    print("  [OK]   admin subscription → PREMIUM/ACTIVE (신규 생성)")


def get_any_admin(db) -> User | None:
    return db.query(User).filter(User.role == UserRole.ADMIN).first()


# ── main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Admin 초기 데이터 주입 스크립트")
    parser.add_argument(
        "--reset", action="store_true", help="기존 seed 데이터 삭제 후 재생성"
    )
    parser.add_argument(
        "--with-admin", action="store_true", help="ADMIN 계정도 함께 생성"
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        if args.reset:
            print("\n[ RESET ]")
            reset_seed_data(db)

        print("\n[ USERS ]")
        user_map = seed_users(db)

        print("\n[ SUBSCRIPTIONS ]")
        seed_subscriptions(db, user_map)

        print("\n[ GROUPS ]")
        group_map = seed_groups(db, user_map)

        print("\n[ GROUP MEMBERS ]")
        seed_group_members(db, user_map, group_map)

        print("\n[ DOCUMENTS ]")
        seed_documents(db, user_map)

        admin = None
        if args.with_admin:
            print("\n[ ADMIN ]")
            admin = seed_admin(db)
            seed_admin_subscription(db, admin)
        else:
            admin = get_any_admin(db)

        print("\n✅ seed 완료")

    finally:
        db.close()


if __name__ == "__main__":
    main()
