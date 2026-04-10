from datetime import timedelta

import pytest

from errors import ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    utc_now_naive,
)
from tests.dummy_data import users


# TC-GROUP-001-01 프리미엄 사용자는 정상적으로 워크스페이스를 생성한다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_success(client, db_session, logged_in_user):
    """프리미엄 사용자가 정상 payload로 워크스페이스를 생성하면 OWNER 멤버십이 함께 생성된다."""
    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now,
            ended_at=now + timedelta(days=30),
        )
    )
    db_session.commit()

    payload = {
        "name": "테스트 워크스페이스",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["status"] == "ACTIVE"
    assert data["my_role"] == "OWNER"
    assert data["owner_id"] == logged_in_user.id
    assert data["owner_username"] == users[0]["username"]
    assert data["member_count"] == 1
    assert data["document_count"] == 0

    group = (
        db_session.query(Group)
        .filter(
            Group.owner_user_id == logged_in_user.id,
            Group.name == payload["name"],
        )
        .first()
    )
    assert group is not None
    assert group.description == payload["description"]

    membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.group_id == group.id,
            GroupMember.user_id == logged_in_user.id,
        )
        .first()
    )
    assert membership is not None
    assert membership.role == MembershipRole.OWNER
    assert membership.status == MembershipStatus.ACTIVE


# TC-GROUP-001-02 프리미엄 구독이 없는 사용자는 워크스페이스를 생성할 수 없다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_forbidden_without_premium(client, logged_in_user):
    """무료 사용자는 워크스페이스를 생성할 수 없다."""
    payload = {
        "name": "테스트 워크스페이스",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_PREMIUM.code


# TC-GROUP-001-03 이미 활성 워크스페이스를 소유한 사용자는 새 워크스페이스를 생성할 수 없다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_conflict_when_owner_already_has_active_group(
    client, db_session, logged_in_user
):
    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now,
            ended_at=now + timedelta(days=30),
        )
    )
    db_session.flush()

    group = Group(
        owner_user_id=logged_in_user.id,
        name="기존 워크스페이스",
        description="기존 그룹",
        status=GroupStatus.ACTIVE,
    )
    db_session.add(group)
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=group.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    payload = {
        "name": "새 워크스페이스",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.GROUP_OWNER_LIMIT.code


# TC-GROUP-001-04 삭제 대기 중인 워크스페이스만 소유한 사용자는 새 워크스페이스를 생성할 수 있다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_success_when_owner_has_only_delete_pending_group(
    client, db_session, logged_in_user
):
    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now,
            ended_at=now + timedelta(days=30),
        )
    )
    db_session.flush()

    group = Group(
        owner_user_id=logged_in_user.id,
        name="삭제 대기 워크스페이스",
        description="기존 그룹",
        status=GroupStatus.DELETE_PENDING,
        pending_reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        delete_requested_at=now,
        delete_scheduled_at=now + timedelta(days=30),
    )
    db_session.add(group)
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=group.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    payload = {
        "name": "새 워크스페이스",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["name"] == payload["name"]
    assert data["status"] == "ACTIVE"
    assert data["my_role"] == "OWNER"
    assert data["owner_id"] == logged_in_user.id


# TC-GROUP-001-05 이름 앞뒤 공백이 포함된 경우 trim 후 생성된다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_success_with_trimmed_name(client, db_session, logged_in_user):
    """워크스페이스 이름의 앞뒤 공백은 제거된 뒤 저장된다."""
    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=logged_in_user.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now,
            ended_at=now + timedelta(days=30),
        )
    )
    db_session.commit()

    payload = {
        "name": "  테스트 워크스페이스  ",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["name"] == "테스트 워크스페이스"
    assert data["description"] == payload["description"]

    group = (
        db_session.query(Group)
        .filter(Group.owner_user_id == logged_in_user.id)
        .order_by(Group.id.desc())
        .first()
    )
    assert group is not None
    assert group.name == "테스트 워크스페이스"


# TC-GROUP-001-06 이름이 공백뿐이면 생성할 수 없다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_validation_error_with_blank_name(client, logged_in_user):
    payload = {
        "name": "   ",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 422


# TC-GROUP-001-07 이름 길이 제한을 초과하면 생성할 수 없다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_validation_error_with_too_long_name(client, logged_in_user):
    payload = {
        "name": "가" * 101,
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 422


# TC-GROUP-001-08 설명 길이 제한을 초과하면 생성할 수 없다
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_create_workspace_validation_error_with_too_long_description(
    client, logged_in_user
):
    payload = {
        "name": "테스트 워크스페이스",
        "description": "가" * 501,
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 422


# TC-GROUP-001-09 비로그인 사용자는 워크스페이스를 생성할 수 없다
def test_create_workspace_unauthenticated(client):
    payload = {
        "name": "테스트 워크스페이스",
        "description": "생성 테스트",
    }

    res = client.post("/api/groups", json=payload)
    assert res.status_code == 401
