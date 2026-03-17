"""
seed_admin.py — admin 화면 테스트용 더미 데이터 생성 스크립트

실행 방법:
    cd backend
    python seed_admin.py

    # ADMIN 계정도 함께 생성하고 싶을 때:
    python seed_admin.py --with-admin

    # 기존 seed 데이터 초기화 후 재생성:
    python seed_admin.py --reset

idempotent 전략:
    - User/Precedent: email/source_url 기준으로 이미 있으면 skip
    - Subscription/Group/GroupMember/Document: 소유 user 기준으로 없을 때만 생성
    - --reset 플래그 사용 시 seed 이메일 도메인(@seed.test) 기준으로 관련 데이터 삭제 후 재생성
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
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
from services.auth_service import hash_password

# ── 설정 ──────────────────────────────────────────────────────────────────────

SEED_EMAIL_DOMAIN = "@seed.test"
ADMIN_EMAIL = "admin@seed.test"
ADMIN_PASSWORD = "Admin1234!"


# 최근 7일 날짜 헬퍼
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
    (
        f"choi{SEED_EMAIL_DOMAIN}",
        "PREMIUM",
        "INACTIVE",
        16,
    ),  # 비활성 PREMIUM → FREE로 표시
    (f"jung{SEED_EMAIL_DOMAIN}", "FREE", "ACTIVE", 14),
    (
        f"han{SEED_EMAIL_DOMAIN}",
        "PREMIUM",
        "CANCELLED",
        10,
    ),  # 취소 PREMIUM → FREE로 표시
    (f"kwon{SEED_EMAIL_DOMAIN}", "FREE", "ACTIVE", 4),
    (f"shin{SEED_EMAIL_DOMAIN}", "PREMIUM", "ACTIVE", 2),
]

# (name, owner_email, status)
SEED_GROUPS = [
    ("법무법인 알파", f"kim{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("변호사 이팀", f"lee{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("박사무소 A", f"park{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("최팀장 그룹", f"choi{SEED_EMAIL_DOMAIN}", "ACTIVE"),
    ("구 한변리 사무소", f"han{SEED_EMAIL_DOMAIN}", "INACTIVE"),
]

# (group_name, member_emails) — 그룹에 추가할 멤버
SEED_GROUP_MEMBERS = [
    ("법무법인 알파", [f"lee{SEED_EMAIL_DOMAIN}", f"jung{SEED_EMAIL_DOMAIN}"]),
    ("변호사 이팀", [f"park{SEED_EMAIL_DOMAIN}", f"kwon{SEED_EMAIL_DOMAIN}"]),
    ("박사무소 A", [f"shin{SEED_EMAIL_DOMAIN}"]),
    ("최팀장 그룹", [f"jung{SEED_EMAIL_DOMAIN}", f"han{SEED_EMAIL_DOMAIN}"]),
]

# 최근 7일 문서 분산 — (user_email, status, days_ago) * N
SEED_DOCUMENTS = [
    # 오늘 ~ 1일 전
    (f"kim{SEED_EMAIL_DOMAIN}", "DONE", 0),
    (f"lee{SEED_EMAIL_DOMAIN}", "DONE", 0),
    (f"park{SEED_EMAIL_DOMAIN}", "PROCESSING", 0),
    (f"choi{SEED_EMAIL_DOMAIN}", "FAILED", 0),
    # 2일 전
    (f"kim{SEED_EMAIL_DOMAIN}", "DONE", 1),
    (f"lee{SEED_EMAIL_DOMAIN}", "DONE", 1),
    (f"jung{SEED_EMAIL_DOMAIN}", "DONE", 1),
    (f"han{SEED_EMAIL_DOMAIN}", "FAILED", 1),
    # 3일 전
    (f"park{SEED_EMAIL_DOMAIN}", "DONE", 2),
    (f"kwon{SEED_EMAIL_DOMAIN}", "DONE", 2),
    (f"shin{SEED_EMAIL_DOMAIN}", "PROCESSING", 2),
    (f"kim{SEED_EMAIL_DOMAIN}", "DONE", 2),
    # 4일 전
    (f"lee{SEED_EMAIL_DOMAIN}", "DONE", 3),
    (f"park{SEED_EMAIL_DOMAIN}", "FAILED", 3),
    (f"choi{SEED_EMAIL_DOMAIN}", "DONE", 3),
    # 5일 전
    (f"jung{SEED_EMAIL_DOMAIN}", "DONE", 4),
    (f"han{SEED_EMAIL_DOMAIN}", "DONE", 4),
    (f"kwon{SEED_EMAIL_DOMAIN}", "DONE", 4),
    (f"shin{SEED_EMAIL_DOMAIN}", "FAILED", 4),
    # 6일 전
    (f"kim{SEED_EMAIL_DOMAIN}", "DONE", 5),
    (f"lee{SEED_EMAIL_DOMAIN}", "DONE", 5),
    (f"park{SEED_EMAIL_DOMAIN}", "DONE", 5),
    # 7일 전
    (f"choi{SEED_EMAIL_DOMAIN}", "DONE", 6),
    (f"jung{SEED_EMAIL_DOMAIN}", "DONE", 6),
    (f"han{SEED_EMAIL_DOMAIN}", "DONE", 6),
    (f"kwon{SEED_EMAIL_DOMAIN}", "PROCESSING", 6),
]

SEED_PRECEDENTS = [
    # DONE — 최근 등록 패널에 보임
    {
        "source_url": "https://www.law.go.kr/cases/seed/001",
        "title": "대법원 2024다11001 손해배상(기)",
        "status": "DONE",
        "error": None,
        "created_days_ago": 6,
        "updated_days_ago": 5,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/002",
        "title": "서울고등법원 2024나22002 계약해지",
        "status": "DONE",
        "error": None,
        "created_days_ago": 5,
        "updated_days_ago": 4,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/003",
        "title": "대법원 2023다33003 임금청구",
        "status": "DONE",
        "error": None,
        "created_days_ago": 4,
        "updated_days_ago": 3,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/004",
        "title": "부산지방법원 2024가단44004 소유권이전",
        "status": "DONE",
        "error": None,
        "created_days_ago": 3,
        "updated_days_ago": 2,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/005",
        "title": "인천지방법원 2024나55005 불법행위",
        "status": "DONE",
        "error": None,
        "created_days_ago": 2,
        "updated_days_ago": 1,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/006",
        "title": "대법원 2024다66006 배당이의",
        "status": "DONE",
        "error": None,
        "created_days_ago": 1,
        "updated_days_ago": 0,
    },
    {
        "source_url": "https://glaw.scourt.go.kr/cases/seed/001",
        "title": "대법원 2023다77001 이혼 및 재산분할",
        "status": "DONE",
        "error": None,
        "created_days_ago": 7,
        "updated_days_ago": 6,
    },
    {
        "source_url": "https://glaw.scourt.go.kr/cases/seed/002",
        "title": "서울중앙지방법원 2024가합88002 어음금",
        "status": "DONE",
        "error": None,
        "created_days_ago": 8,
        "updated_days_ago": 7,
    },
    # PENDING — 대기 패널에 보임
    {
        "source_url": "https://www.law.go.kr/cases/seed/007",
        "title": None,
        "status": "PENDING",
        "error": None,
        "created_days_ago": 0,
        "updated_days_ago": 0,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/008",
        "title": None,
        "status": "PENDING",
        "error": None,
        "created_days_ago": 0,
        "updated_days_ago": 0,
    },
    {
        "source_url": "https://glaw.scourt.go.kr/cases/seed/003",
        "title": None,
        "status": "PENDING",
        "error": None,
        "created_days_ago": 1,
        "updated_days_ago": 1,
    },
    # PROCESSING — 대기/처리 중 패널에 보임
    {
        "source_url": "https://www.law.go.kr/cases/seed/009",
        "title": "처리 중인 판례 A",
        "status": "PROCESSING",
        "error": None,
        "created_days_ago": 0,
        "updated_days_ago": 0,
    },
    {
        "source_url": "https://glaw.scourt.go.kr/cases/seed/004",
        "title": "처리 중인 판례 B",
        "status": "PROCESSING",
        "error": None,
        "created_days_ago": 1,
        "updated_days_ago": 0,
    },
    # FAILED — 실패 패널에 보임
    {
        "source_url": "https://www.law.go.kr/cases/seed/010",
        "title": "대법원 2024다10010 파싱실패케이스",
        "status": "FAILED",
        "error": "HTML 파싱 오류: 예상치 못한 태그 구조",
        "created_days_ago": 3,
        "updated_days_ago": 3,
    },
    {
        "source_url": "https://www.law.go.kr/cases/seed/011",
        "title": "서울고등법원 2023나11011 타임아웃",
        "status": "FAILED",
        "error": "요청 타임아웃 (30s 초과)",
        "created_days_ago": 4,
        "updated_days_ago": 4,
    },
    {
        "source_url": "https://glaw.scourt.go.kr/cases/seed/005",
        "title": "대법원 2024다55005 인코딩 오류",
        "status": "FAILED",
        "error": "문서 인코딩 감지 실패 (EUC-KR)",
        "created_days_ago": 5,
        "updated_days_ago": 5,
    },
    {
        "source_url": "https://casenote.kr/cases/seed/001",
        "title": "casenote 수집 실패 케이스",
        "status": "FAILED",
        "error": "접근 차단 (403 Forbidden)",
        "created_days_ago": 2,
        "updated_days_ago": 2,
    },
]


# ── seed 실행 ─────────────────────────────────────────────────────────────────


def reset_seed_data(db):
    """seed 이메일 도메인 기준으로 관련 데이터 전부 삭제"""
    print("  기존 seed 데이터 삭제 중...")
    seed_users = db.query(User).filter(User.email.like(f"%{SEED_EMAIL_DOMAIN}")).all()
    for user in seed_users:
        db.delete(user)

    seed_precedents = (
        db.query(Precedent).filter(Precedent.source_url.like("%/seed/%")).all()
    )
    for p in seed_precedents:
        db.delete(p)

    db.commit()
    print("  삭제 완료")


def seed_users(db) -> dict[str, User]:
    """GENERAL 사용자 생성. 이미 있으면 skip. {email: user} 반환"""
    user_map = {}
    for u in SEED_USERS:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if existing:
            print(f"  [SKIP] user {u['email']}")
            user_map[u["email"]] = existing
            continue

        user = User(
            email=u["email"],
            username=u["username"],
            password=hash_password("Test1234!"),
            role=UserRole.GENERAL,
            is_active=u["is_active"],
            created_at=_days_ago(u["days_ago"]),
            updated_at=_days_ago(u["days_ago"]),
        )
        db.add(user)
        db.flush()
        user_map[u["email"]] = user
        print(f"  [OK]   user {u['email']} ({u['username']})")
    db.commit()
    return user_map


def seed_subscriptions(db, user_map: dict):
    """구독 생성. 이미 있으면 skip."""
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
            created_at=_days_ago(days_ago),
            updated_at=_days_ago(days_ago),
        )
        db.add(sub)
        print(f"  [OK]   subscription {email} → {plan}/{status}")
    db.commit()


def seed_groups(db, user_map: dict) -> dict[str, "Group"]:
    """그룹 생성. owner + name 조합으로 중복 체크."""
    group_map = {}
    for name, owner_email, status in SEED_GROUPS:
        owner = user_map.get(owner_email)
        if not owner:
            continue
        existing = (
            db.query(Group)
            .filter(Group.name == name, Group.owner_id == owner.id)
            .first()
        )
        if existing:
            print(f"  [SKIP] group '{name}'")
            group_map[name] = existing
            continue
        group = Group(
            name=name,
            owner_id=owner.id,
            status=GroupStatus(status),
        )
        db.add(group)
        db.flush()
        group_map[name] = group
        print(f"  [OK]   group '{name}' ({status})")
    db.commit()
    return group_map


def seed_group_members(db, user_map: dict, group_map: dict):
    """그룹 멤버 추가. 이미 있으면 skip."""
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
                    GroupMember.group_id == group.id, GroupMember.user_id == user.id
                )
                .first()
            )
            if existing:
                print(f"  [SKIP] member {email} → '{group_name}'")
                continue
            db.add(GroupMember(group_id=group.id, user_id=user.id))
            print(f"  [OK]   member {email} → '{group_name}'")
    db.commit()


def seed_documents(db, user_map: dict):
    """문서 생성. document_url로 중복 체크."""
    for i, (email, status, days_ago) in enumerate(SEED_DOCUMENTS):
        user = user_map.get(email)
        if not user:
            continue
        url = f"https://storage.seed.test/docs/seed_{i:03d}.pdf"
        existing = db.query(Document).filter(Document.document_url == url).first()
        if existing:
            print(f"  [SKIP] document seed_{i:03d}")
            continue

        # created_at을 특정 시각으로 고정 — 그래프 분산 목적
        created = _days_ago(days_ago).replace(hour=9 + (i % 8), minute=i % 60)
        doc = Document(
            user_id=user.id,
            document_url=url,
            status=DocumentStatus(status),
            created_at=created,
        )
        db.add(doc)
        print(f"  [OK]   document seed_{i:03d} ({status}, {days_ago}일 전)")
    db.commit()


def seed_precedents(db, admin_id: int | None):
    """판례 생성. source_url로 중복 체크."""
    for p in SEED_PRECEDENTS:
        existing = (
            db.query(Precedent).filter(Precedent.source_url == p["source_url"]).first()
        )
        if existing:
            print(f"  [SKIP] precedent {p['source_url']}")
            continue

        created_at = _days_ago(p["created_days_ago"])
        updated_at = _days_ago(p["updated_days_ago"])

        precedent = Precedent(
            source_url=p["source_url"],
            title=p["title"],
            processing_status=DocumentStatus(p["status"]),
            error_message=p["error"],
            uploaded_by_admin_id=admin_id,
            created_at=created_at,
            updated_at=updated_at,
        )
        db.add(precedent)
        print(f"  [OK]   precedent {p['source_url']} ({p['status']})")
    db.commit()


def seed_admin(db) -> User | None:
    """ADMIN 계정 생성. 이미 있으면 skip."""
    existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if existing:
        print(f"  [SKIP] admin {ADMIN_EMAIL}")
        return existing
    admin = User(
        email=ADMIN_EMAIL,
        username="시드관리자",
        password=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"  [OK]   admin {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    return admin


def get_any_admin(db) -> User | None:
    return db.query(User).filter(User.role == UserRole.ADMIN).first()


# ── 메인 ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Admin 화면 테스트용 seed 스크립트")
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

        if args.with_admin:
            print("\n[ ADMIN ]")
            seed_admin(db)

        admin = get_any_admin(db)
        admin_id = admin.id if admin else None

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

        print("\n[ PRECEDENTS ]")
        seed_precedents(db, admin_id)

        print("\n✅  seed 완료")
        print(f"    - 사용자: {len(user_map)}명")
        print(f"    - 구독: {len(SEED_SUBSCRIPTIONS)}건")
        print(f"    - 그룹: {len(SEED_GROUPS)}개")
        print(f"    - 문서: {len(SEED_DOCUMENTS)}건 (최근 7일 분산)")
        print(
            f"    - 판례: {len(SEED_PRECEDENTS)}건 (DONE/PENDING/PROCESSING/FAILED 혼합)"
        )
        if admin_id is None:
            print(
                "\n⚠️  ADMIN 계정이 없습니다. --with-admin 플래그로 생성하거나 직접 등록해주세요."
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
