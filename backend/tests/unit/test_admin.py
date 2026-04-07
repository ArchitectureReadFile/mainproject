"""
admin API 검증 테스트

대상:
- GET  /api/admin/stats
- GET  /api/admin/usage
- GET  /api/admin/platform/summary
- POST /api/admin/platform/sync
- POST /api/admin/platform/sync/stop
- GET  /api/admin/platform/failures
- GET  /api/admin/users
- PATCH /api/admin/users/{id}

검증 항목:
1. ADMIN이 아닌 사용자 → 403
2. user status toggle에서 ADMIN 계정 차단 → 403
3. user status toggle에서 자기 자신 차단 → 403
4. stats/usage/users/platform 정상 응답 shape 확인
5. stop — queued/running 중단, cancelled 재확인 안전성
6. failure error_type 분류 — fetch/normalize/index
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from main import app
from models.model import (
    Group,
    GroupMember,
    GroupStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
)
from models.platform_knowledge import PlatformSyncFailure, PlatformSyncRun
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


def _make_sync_run(db: Session, source_type: str, status: str) -> PlatformSyncRun:
    run = PlatformSyncRun(
        source_type=source_type,
        status=status,
        message="테스트 run",
        fetched_count=0,
        created_count=0,
        skipped_count=0,
        failed_count=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


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


# ── platform sync ────────────────────────────────────────────────────────────


class TestAdminPlatformSync:
    def test_platform_summary_forbidden_for_general(self, general_client):
        res = general_client.get("/api/admin/platform/summary")
        assert res.status_code == 403

    def test_platform_sync_forbidden_for_general(self, general_client):
        res = general_client.post(
            "/api/admin/platform/sync",
            json={"source_type": "law"},
        )
        assert res.status_code == 403

    def test_platform_summary_response_shape(self, admin_client, monkeypatch):
        def _fake_summary(_db):
            return {
                "total_documents": 3,
                "total_chunks": 9,
                "sources": [
                    {
                        "source_type": "law",
                        "label": "현행 법령",
                        "document_count": 2,
                        "chunk_count": 6,
                        "last_synced_at": None,
                        "last_sync_status": "running",
                        "last_sync_message": "3페이지 처리 중 · 조회 250건 · 신규 12건 · 스킵 238건 · 실패 0건",
                        "fetched_count": 250,
                        "created_count": 12,
                        "skipped_count": 238,
                        "failed_count": 0,
                        "current_page": 3,
                        "total_count": 5575,
                        "last_external_id": "253527",
                        "last_display_title": "10·27법난 피해자의 명예회복 등에 관한 법률",
                    },
                    {
                        "source_type": "precedent",
                        "label": "판례",
                        "document_count": 1,
                        "chunk_count": 3,
                        "last_synced_at": None,
                        "last_sync_status": None,
                        "last_sync_message": None,
                        "fetched_count": 0,
                        "created_count": 0,
                        "skipped_count": 0,
                        "failed_count": 0,
                        "current_page": None,
                        "total_count": None,
                        "last_external_id": None,
                        "last_display_title": None,
                    },
                    {
                        "source_type": "interpretation",
                        "label": "법령해석례",
                        "document_count": 0,
                        "chunk_count": 0,
                        "last_synced_at": None,
                        "last_sync_status": None,
                        "last_sync_message": None,
                        "fetched_count": 0,
                        "created_count": 0,
                        "skipped_count": 0,
                        "failed_count": 0,
                        "current_page": None,
                        "total_count": None,
                        "last_external_id": None,
                        "last_display_title": None,
                    },
                    {
                        "source_type": "admin_rule",
                        "label": "행정규칙",
                        "document_count": 0,
                        "chunk_count": 0,
                        "last_synced_at": None,
                        "last_sync_status": None,
                        "last_sync_message": None,
                        "fetched_count": 0,
                        "created_count": 0,
                        "skipped_count": 0,
                        "failed_count": 0,
                        "current_page": None,
                        "total_count": None,
                        "last_external_id": None,
                        "last_display_title": None,
                    },
                ],
                "recent_items": [],
            }

        monkeypatch.setattr(
            "routers.admin.admin_platform_service.get_admin_platform_summary",
            _fake_summary,
        )

        res = admin_client.get("/api/admin/platform/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_documents"] == 3
        assert data["total_chunks"] == 9
        assert len(data["sources"]) == 4
        assert data["sources"][0]["current_page"] == 3
        assert data["sources"][0]["last_external_id"] == "253527"

    def test_platform_sync_response_shape(self, admin_client, monkeypatch):
        def _fake_sync(_db, *, source_type):
            assert source_type == "law"
            return {
                "run_id": 10,
                "source_type": source_type,
                "started_at": "2026-04-03T01:00:00",
                "finished_at": None,
                "status": "queued",
                "fetched": 0,
                "created": 0,
                "skipped": 0,
                "failed": 0,
                "message": "동기화 대기 중입니다.",
            }

        monkeypatch.setattr(
            "routers.admin.admin_platform_service.enqueue_platform_source_sync",
            _fake_sync,
        )

        res = admin_client.post(
            "/api/admin/platform/sync",
            json={"source_type": "law"},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["run_id"] == 10
        assert data["status"] == "queued"
        assert data["created"] == 0
        assert data["message"] == "동기화 대기 중입니다."


# ── platform sync stop ────────────────────────────────────────────────────────


class TestAdminPlatformSyncStop:
    def test_stop_queued_run(self, admin_client, db_session):
        """queued 상태 run을 stop하면 cancelled가 된다."""
        run = _make_sync_run(db_session, "law", "queued")
        res = admin_client.post(
            "/api/admin/platform/sync/stop",
            json={"source_type": "law"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "cancelled"
        assert data["run_id"] == run.id

        db_session.refresh(run)
        assert run.status == "cancelled"
        assert run.finished_at is not None

    def test_stop_running_run(self, admin_client, db_session):
        """running 상태 run을 stop하면 cancelled가 된다."""
        run = _make_sync_run(db_session, "precedent", "running")
        res = admin_client.post(
            "/api/admin/platform/sync/stop",
            json={"source_type": "precedent"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "cancelled"
        assert data["run_id"] == run.id

    def test_stop_when_no_active_run(self, admin_client, db_session):
        """진행 중인 run이 없으면 not_found를 반환한다."""
        _make_sync_run(db_session, "law", "success")
        res = admin_client.post(
            "/api/admin/platform/sync/stop",
            json={"source_type": "law"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "not_found"

    def test_stop_forbidden_for_general(self, general_client):
        res = general_client.post(
            "/api/admin/platform/sync/stop",
            json={"source_type": "law"},
        )
        assert res.status_code == 403

    def test_repeated_stop_is_safe(self, admin_client, db_session):
        """이미 cancelled인 run에 stop을 반복해도 not_found만 반환한다."""
        _make_sync_run(db_session, "law", "cancelled")
        res = admin_client.post(
            "/api/admin/platform/sync/stop",
            json={"source_type": "law"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "not_found"

    def test_cancelled_does_not_become_running(self, db_session):
        """cancelled run은 _update_run_progress를 호출해도 running으로 바뀌지 않는다."""
        from services.admin_platform_service import _update_run_progress

        run = _make_sync_run(db_session, "law", "cancelled")
        _update_run_progress(
            db_session,
            run,
            counts={"fetched": 10, "created": 5, "skipped": 5, "failed": 0},
            current_page=2,
            total_count=100,
        )
        db_session.refresh(run)
        assert run.status == "cancelled"


# ── platform sync failure error_type 분류 ────────────────────────────────────


class TestAdminPlatformSyncFailureType:
    """
    execute_platform_source_sync item-level 실패 시 error_type이
    올바르게 기록되는지 검증한다.

    실제 Celery/API 호출 없이 SessionLocal + client/ingestion_service를
    mock으로 교체해 단위 테스트한다.
    """

    def _run_sync(self, db_session, run, *, patch_client, patch_ingestion=None):
        """
        execute_platform_source_sync를 실제 DB session으로 실행한다.
        SessionLocal을 mock해서 db_session을 재사용한다.
        """
        from services.admin_platform_service import execute_platform_source_sync

        with patch(
            "services.admin_platform_service.SessionLocal",
            return_value=db_session,
        ):
            # db.close()가 session을 닫지 않도록 noop 처리
            db_session.close = lambda: None

            patches = [
                patch(
                    "services.admin_platform_service.KoreaLawOpenApiClient",
                    return_value=patch_client,
                ),
            ]
            if patch_ingestion is not None:
                patches.append(
                    patch(
                        "services.admin_platform_service.PlatformKnowledgeIngestionService",
                        return_value=patch_ingestion,
                    )
                )

            for p in patches:
                p.start()
            try:
                execute_platform_source_sync(run.id)
            except Exception:
                pass
            finally:
                for p in patches:
                    p.stop()

    def _make_client(self, *, extract_detail_link=None, fetch_detail=None):
        """KoreaLawOpenApiClient mock 생성 헬퍼."""
        c = MagicMock()
        c.search_page.return_value = (
            [{"id": "LAW-001", "title": "테스트 법령"}],
            1,
        )
        c.extract_external_id.return_value = "LAW-001"
        c.extract_display_title.return_value = "테스트 법령"

        if extract_detail_link is not None:
            c.extract_detail_link.side_effect = extract_detail_link
        else:
            c.extract_detail_link.return_value = (
                "https://api.example.com/detail/LAW-001"
            )

        if fetch_detail is not None:
            c.fetch_detail_from_link.side_effect = fetch_detail
        else:
            c.fetch_detail_from_link.return_value = {"법령ID": "LAW-001"}

        return c

    def test_detail_link_extract_failure_is_fetch_error(self, db_session):
        """detail_link 추출 실패 → fetch_error."""
        run = _make_sync_run(db_session, "law", "queued")
        mock_client = self._make_client(
            extract_detail_link=RuntimeError("링크 추출 실패")
        )

        self._run_sync(db_session, run, patch_client=mock_client)

        failures = (
            db_session.query(PlatformSyncFailure).filter_by(sync_run_id=run.id).all()
        )
        assert len(failures) == 1
        assert failures[0].error_type == "fetch_error"
        assert failures[0].external_id == "LAW-001"
        assert failures[0].page == 1

    def test_detail_fetch_failure_is_fetch_error(self, db_session):
        """상세 API 호출 실패 → fetch_error."""
        run = _make_sync_run(db_session, "law", "queued")
        mock_client = self._make_client(fetch_detail=ConnectionError("API 호출 실패"))

        self._run_sync(db_session, run, patch_client=mock_client)

        failures = (
            db_session.query(PlatformSyncFailure).filter_by(sync_run_id=run.id).all()
        )
        assert len(failures) == 1
        assert failures[0].error_type == "fetch_error"
        assert failures[0].detail_link == "https://api.example.com/detail/LAW-001"

    def test_normalize_failure_is_normalize_error(self, db_session):
        """PlatformNormalizeError → normalize_error."""
        from services.platform.platform_knowledge_ingestion_service import (
            PlatformNormalizeError,
        )

        run = _make_sync_run(db_session, "law", "queued")
        mock_client = self._make_client()
        mock_ingestion = MagicMock()
        mock_ingestion.ingest_from_payload.side_effect = PlatformNormalizeError(
            "normalize 실패"
        )

        self._run_sync(
            db_session, run, patch_client=mock_client, patch_ingestion=mock_ingestion
        )

        failures = (
            db_session.query(PlatformSyncFailure).filter_by(sync_run_id=run.id).all()
        )
        assert len(failures) == 1
        assert failures[0].error_type == "normalize_error"
        assert failures[0].external_id == "LAW-001"

    def test_index_failure_is_index_error(self, db_session):
        """normalize 이후 일반 Exception → index_error."""
        run = _make_sync_run(db_session, "law", "queued")
        mock_client = self._make_client()
        mock_ingestion = MagicMock()
        mock_ingestion.ingest_from_payload.side_effect = RuntimeError(
            "Qdrant 저장 실패"
        )

        self._run_sync(
            db_session, run, patch_client=mock_client, patch_ingestion=mock_ingestion
        )

        failures = (
            db_session.query(PlatformSyncFailure).filter_by(sync_run_id=run.id).all()
        )
        assert len(failures) == 1
        assert failures[0].error_type == "index_error"

    def test_failure_row_has_correct_fields(self, db_session):
        """failure row에 external_id / display_title / page / error_message가 저장된다."""
        run = _make_sync_run(db_session, "law", "queued")
        mock_client = self._make_client(extract_detail_link=ValueError("링크 없음"))

        self._run_sync(db_session, run, patch_client=mock_client)

        f = db_session.query(PlatformSyncFailure).filter_by(sync_run_id=run.id).first()
        assert f is not None
        assert f.external_id == "LAW-001"
        assert f.display_title == "테스트 법령"
        assert f.page == 1
        assert f.error_message is not None
        assert len(f.error_message) > 0

    def test_cancelled_run_no_failure_saved(self, db_session):
        """cancelled run은 failure row 저장 후 progress update가 running으로 바꾸지 않는다."""
        run = _make_sync_run(db_session, "law", "cancelled")
        mock_client = self._make_client(
            extract_detail_link=RuntimeError("링크 추출 실패")
        )

        self._run_sync(db_session, run, patch_client=mock_client)

        db_session.refresh(run)
        assert run.status == "cancelled"


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


# ── user update 차단/변경 ─────────────────────────────────────────────────────


class TestAdminUserUpdate:
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
        assert res.json()["plan"] == "FREE"

    def test_can_change_general_user_plan_to_premium(self, admin_client, db_session):
        user = _make_user(db_session, "plan-target@example.com", "플랜대상")
        res = admin_client.patch(
            f"/api/admin/users/{user.id}", json={"plan": "PREMIUM"}
        )
        assert res.status_code == 200
        assert res.json()["plan"] == "PREMIUM"

        sub = (
            db_session.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .first()
        )
        assert sub is not None
        assert sub.plan == SubscriptionPlan.PREMIUM
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_can_change_general_user_plan_to_free(self, admin_client, db_session):
        user = _make_user(db_session, "free-target@example.com", "무료전환대상")
        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
        )
        db_session.add(sub)
        db_session.commit()

        res = admin_client.patch(f"/api/admin/users/{user.id}", json={"plan": "FREE"})
        assert res.status_code == 200
        assert res.json()["plan"] == "FREE"

        db_session.refresh(sub)
        assert sub.plan == SubscriptionPlan.FREE
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_toggle_not_found(self, admin_client):
        res = admin_client.patch("/api/admin/users/99999", json={"is_active": False})
        assert res.status_code == 404
