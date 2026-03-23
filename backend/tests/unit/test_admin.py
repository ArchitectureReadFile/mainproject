"""
admin API 검증 테스트

대상:
- GET  /api/admin/stats
- GET  /api/admin/usage
- GET  /api/admin/precedents
- POST /api/admin/precedents
- POST /api/admin/precedents/{id}/retry
- GET  /api/admin/users
- PATCH /api/admin/users/{id}

검증 항목:
1. ADMIN이 아닌 사용자 → 403
2. precedent 중복 URL → 409
3. precedent 허용되지 않은 도메인 → 422
4. precedent 허용되지 않은 scheme → 422
5. user status toggle에서 ADMIN 계정 차단 → 403
6. user status toggle에서 자기 자신 차단 → 403
7. stats/usage/users 정상 응답 shape 확인
"""

import pytest
from sqlalchemy.orm import Session

from main import app
from models.model import (
    DocumentStatus,
    Group,
    GroupMember,
    GroupStatus,
    Precedent,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
)
from routers.auth import get_current_user
from services.auth_service import AuthService

auth_service = AuthService()

# ── 픽스처 ────────────────────────────────────────────────────────────────────


def _make_user(
    db: Session,
    email: str,
    username: str,
    role: str = "GENERAL",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        username=username,
        password=auth_service.hash_password("password123!"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _override_user(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_override():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_user(db_session):
    return _make_user(db_session, "admin@example.com", "관리자", role="ADMIN")


@pytest.fixture
def general_user(db_session):
    return _make_user(db_session, "user@example.com", "일반유저", role="GENERAL")


@pytest.fixture
def admin_client(client, admin_user):
    _override_user(admin_user)
    yield client
    _clear_override()


@pytest.fixture
def general_client(client, general_user):
    _override_user(general_user)
    yield client
    _clear_override()


# ── 권한 차단 ─────────────────────────────────────────────────────────────────


class TestAdminAccessControl:
    def test_stats_forbidden_for_general(self, general_client):
        res = general_client.get("/api/admin/stats")
        assert res.status_code == 403

    def test_usage_forbidden_for_general(self, general_client):
        res = general_client.get("/api/admin/usage")
        assert res.status_code == 403

    def test_precedents_forbidden_for_general(self, general_client):
        res = general_client.get("/api/admin/precedents")
        assert res.status_code == 403

    def test_users_forbidden_for_general(self, general_client):
        res = general_client.get("/api/admin/users")
        assert res.status_code == 403


# ── stats 응답 shape ──────────────────────────────────────────────────────────


class TestAdminStats:
    def test_stats_response_shape(self, admin_client):
        res = admin_client.get("/api/admin/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total_users" in data
        assert "premium_users" in data
        assert "premium_conversion_rate" in data
        assert "active_groups" in data
        assert "ai_success_rate" in data
        assert isinstance(data["conversion_trend"], list)
        assert isinstance(data["ai_trend"], list)
        assert len(data["conversion_trend"]) == 7
        assert len(data["ai_trend"]) == 7

    def test_stats_counts_general_only(self, admin_client, db_session, admin_user):
        # GENERAL 유저 2명 추가 (admin_user는 ADMIN이라 집계 제외)
        _make_user(db_session, "u1@example.com", "유저1")
        _make_user(db_session, "u2@example.com", "유저2")
        res = admin_client.get("/api/admin/stats")
        assert res.json()["total_users"] == 2

    def test_stats_premium_conversion(self, admin_client, db_session):
        user = _make_user(db_session, "premium@example.com", "프리미엄유저")
        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
        )
        db_session.add(sub)
        db_session.commit()

        res = admin_client.get("/api/admin/stats")
        data = res.json()
        assert data["premium_users"] == 1
        assert data["premium_conversion_rate"] > 0

    def test_stats_active_groups(self, admin_client, db_session, admin_user):
        group = Group(
            name="테스트그룹", owner_id=admin_user.id, status=GroupStatus.ACTIVE
        )
        db_session.add(group)
        db_session.commit()

        res = admin_client.get("/api/admin/stats")
        assert res.json()["active_groups"] == 1


# ── usage 응답 shape ──────────────────────────────────────────────────────────


class TestAdminUsage:
    def test_usage_response_shape(self, admin_client):
        res = admin_client.get("/api/admin/usage")
        assert res.status_code == 200
        data = res.json()
        assert "service_usage" in data
        assert "rag_usage" in data
        assert "storage" in data["service_usage"]
        assert "daily_uploads" in data["service_usage"]
        assert "document_jobs" in data["service_usage"]
        assert "precedent_count" in data["rag_usage"]
        assert "index_jobs" in data["rag_usage"]
        assert len(data["service_usage"]["daily_uploads"]) == 7


# ── precedents ────────────────────────────────────────────────────────────────


class TestAdminPrecedents:
    VALID_URL = "https://www.law.go.kr/cases/001"
    DUPLICATE_URL = "https://www.law.go.kr/cases/duplicate"
    INVALID_DOMAIN_URL = "https://notallowed.com/cases/001"
    INVALID_SCHEME_URL = "ftp://www.law.go.kr/cases/001"

    def test_list_empty(self, admin_client):
        res = admin_client.get("/api/admin/precedents")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["failed_items"] == []
        assert data["pending_items"] == []
        assert data["recent_items"] == []
        assert data["summary"]["total"] == 0

    def test_list_includes_panel_items_outside_default_page(
        self, admin_client, db_session, admin_user
    ):
        for i in range(25):
            db_session.add(
                Precedent(
                    source_url=f"https://taxlaw.nts.go.kr/pd/ok-{i}",
                    title=f"정상 {i}",
                    processing_status=DocumentStatus.DONE,
                    uploaded_by_admin_id=admin_user.id,
                )
            )
        failed = Precedent(
            source_url="https://taxlaw.nts.go.kr/pd/failed-1",
            title="실패 판례",
            processing_status=DocumentStatus.FAILED,
            error_message="파싱 실패",
            uploaded_by_admin_id=admin_user.id,
        )
        db_session.add(failed)
        db_session.commit()

        res = admin_client.get("/api/admin/precedents")
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["failed"] == 1
        assert len(data["items"]) == 20
        assert len(data["failed_items"]) == 1
        assert data["failed_items"][0]["title"] == "실패 판례"

    def test_create_success(self, admin_client):
        res = admin_client.post(
            "/api/admin/precedents", json={"source_url": self.VALID_URL}
        )
        assert res.status_code == 201
        assert res.json()["source_url"] == self.VALID_URL

    def test_create_duplicate_url(self, admin_client, db_session, admin_user):
        db_session.add(
            Precedent(
                source_url=self.DUPLICATE_URL,
                processing_status=DocumentStatus.PENDING,
                uploaded_by_admin_id=admin_user.id,
            )
        )
        db_session.commit()

        res = admin_client.post(
            "/api/admin/precedents", json={"source_url": self.DUPLICATE_URL}
        )
        assert res.status_code == 409
        assert res.json()["code"] == "PRECEDENT_002"

    def test_create_invalid_domain(self, admin_client):
        res = admin_client.post(
            "/api/admin/precedents", json={"source_url": self.INVALID_DOMAIN_URL}
        )
        assert res.status_code == 422
        assert res.json()["code"] == "PRECEDENT_004"

    def test_create_invalid_scheme(self, admin_client):
        res = admin_client.post(
            "/api/admin/precedents", json={"source_url": self.INVALID_SCHEME_URL}
        )
        assert res.status_code == 422
        assert res.json()["code"] == "PRECEDENT_003"

    def test_retry_success(self, admin_client, db_session, admin_user):
        precedent = Precedent(
            source_url="https://www.law.go.kr/cases/retry",
            processing_status=DocumentStatus.FAILED,
            error_message="파싱 오류",
            uploaded_by_admin_id=admin_user.id,
        )
        db_session.add(precedent)
        db_session.commit()
        db_session.refresh(precedent)

        res = admin_client.post(f"/api/admin/precedents/{precedent.id}/retry")
        assert res.status_code == 200
        assert res.json()["processing_status"] == "PENDING"

        db_session.refresh(precedent)
        assert precedent.processing_status == DocumentStatus.PENDING
        assert precedent.error_message is None

    def test_retry_not_found(self, admin_client):
        res = admin_client.post("/api/admin/precedents/99999/retry")
        assert res.status_code == 404
        assert res.json()["code"] == "PRECEDENT_001"


# ── users ─────────────────────────────────────────────────────────────────────


class TestAdminUsers:
    def test_list_response_shape(self, admin_client):
        res = admin_client.get("/api/admin/users")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data

    def test_list_excludes_admin(self, admin_client, db_session):
        _make_user(db_session, "g@example.com", "일반유저")
        res = admin_client.get("/api/admin/users")
        # ADMIN 유저(admin_user fixture)는 제외되어야 함
        for item in res.json()["items"]:
            assert item["role"] == "GENERAL"

    def test_list_plan_field(self, admin_client, db_session):
        user = _make_user(db_session, "p@example.com", "프리미엄")
        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
        )
        db_session.add(sub)
        db_session.commit()

        res = admin_client.get("/api/admin/users")
        items = res.json()["items"]
        target = next(i for i in items if i["id"] == user.id)
        assert target["plan"] == "PREMIUM"

    def test_list_active_group_count(self, admin_client, db_session, admin_user):
        user = _make_user(db_session, "gc@example.com", "그룹유저")
        group = Group(name="그룹", owner_id=admin_user.id, status=GroupStatus.ACTIVE)
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)
        db_session.add(GroupMember(group_id=group.id, user_id=user.id))
        db_session.commit()

        res = admin_client.get("/api/admin/users")
        items = res.json()["items"]
        target = next(i for i in items if i["id"] == user.id)
        assert target["active_group_count"] == 1

    def test_search_by_username(self, admin_client, db_session):
        _make_user(db_session, "search@example.com", "검색대상유저")
        res = admin_client.get("/api/admin/users?search=검색대상")
        assert res.json()["total"] >= 1

    def test_plan_filter_premium(self, admin_client, db_session):
        user = _make_user(db_session, "pf@example.com", "플랜필터유저")
        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
        )
        db_session.add(sub)
        db_session.commit()

        res = admin_client.get("/api/admin/users?plan=PREMIUM")
        items = res.json()["items"]
        assert all(i["plan"] == "PREMIUM" for i in items)


# ── user status toggle 차단 ───────────────────────────────────────────────────


class TestAdminUserStatusToggle:
    def test_cannot_deactivate_admin(self, admin_client, db_session):
        other_admin = _make_user(
            db_session, "admin2@example.com", "다른관리자", role="ADMIN"
        )
        res = admin_client.patch(
            f"/api/admin/users/{other_admin.id}", json={"is_active": False}
        )
        assert res.status_code == 403

    def test_cannot_deactivate_self(self, client, db_session):
        # admin_user fixture 대신 직접 생성해서 자기 자신 테스트
        self_admin = _make_user(
            db_session, "self@example.com", "셀프관리자", role="ADMIN"
        )
        _override_user(self_admin)
        try:
            res = client.patch(
                f"/api/admin/users/{self_admin.id}", json={"is_active": False}
            )
            assert res.status_code == 403
        finally:
            _clear_override()

    def test_can_deactivate_general_user(self, admin_client, db_session):
        user = _make_user(db_session, "target@example.com", "대상유저")
        res = admin_client.patch(
            f"/api/admin/users/{user.id}", json={"is_active": False}
        )
        assert res.status_code == 200
        assert res.json()["is_active"] is False

    def test_toggle_not_found(self, admin_client):
        res = admin_client.patch("/api/admin/users/99999", json={"is_active": False})
        assert res.status_code == 404
