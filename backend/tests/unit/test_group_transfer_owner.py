from datetime import timedelta

import pytest

from domains.auth.service import AuthService
from errors import ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    utc_now_naive,
)
from tests.dummy_data import groups, users

auth_service = AuthService(None)


# UT-GRP-013-01 OWNER는 프리미엄 활성 멤버에게 소유권을 정상 이전할 수 있다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_transfer_owner_success(client, db_session, logged_in_user):
    """OWNER는 프리미엄 활성 멤버에게 소유권을 정상 이전하는지 검증한다."""
    target_data = users[1].copy()
    target_data["password"] = auth_service.hash_password(target_data["password"])
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=target.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now,
            ended_at=now + timedelta(days=30),
        )
    )

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/1/members/{target.id}/transfer")
    assert res.status_code == 204

    group = db_session.query(Group).filter(Group.id == 1).first()
    assert group is not None
    assert group.owner_user_id == target.id

    old_owner_membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == logged_in_user.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert old_owner_membership is not None
    assert old_owner_membership.role == MembershipRole.ADMIN

    new_owner_membership = (
        db_session.query(GroupMember)
        .filter(
            GroupMember.user_id == target.id,
            GroupMember.group_id == 1,
        )
        .first()
    )
    assert new_owner_membership is not None
    assert new_owner_membership.role == MembershipRole.OWNER
    assert new_owner_membership.status == MembershipStatus.ACTIVE


# UT-GRP-013-02 OWNER가 아닌 사용자는 소유권을 이전할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_transfer_owner_forbidden_for_non_owner(client, db_session, logged_in_user):
    """OWNER가 아닌 사용자는 소유권 이전이 차단되는지 검증한다."""
    owner_data = users[1].copy()
    owner_data["password"] = auth_service.hash_password(owner_data["password"])
    owner = User(**owner_data)
    db_session.add(owner)
    db_session.flush()

    target_data = {
        "id": 3,
        "email": "premium_target@example.com",
        "username": "프리미엄대상",
        "password": auth_service.hash_password("password123!"),
        "role": "GENERAL",
        "is_active": True,
    }
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    now = utc_now_naive()
    db_session.add(
        Subscription(
            user_id=target.id,
            plan=SubscriptionPlan.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=True,
            started_at=now,
            ended_at=now + timedelta(days=30),
        )
    )

    db_session.add(
        Group(
            id=1,
            owner_user_id=owner.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=owner.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/1/members/{target.id}/transfer")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_OWNER.code


# UT-GRP-013-03 자기 자신에게는 소유권을 이전할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_transfer_owner_forbidden_to_self(client, db_session, logged_in_user):
    """자기 자신에게는 소유권을 이전할 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/1/members/{logged_in_user.id}/transfer")
    assert res.status_code == 400
    assert res.json()["code"] == ErrorCode.GROUP_TRANSFER_TO_SELF.code


# UT-GRP-013-04 활성 멤버가 아닌 사용자는 소유권 이전 대상이 될 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_transfer_owner_not_found_for_non_active_member(
    client, db_session, logged_in_user
):
    """활성 멤버가 아닌 사용자는 소유권 이전 대상이 될 수 없는지 검증한다."""
    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post("/api/groups/1/members/999/transfer")
    assert res.status_code == 404
    assert res.json()["code"] == ErrorCode.GROUP_MEMBER_NOT_FOUND.code


# UT-GRP-013-05 이미 다른 활성 워크스페이스의 OWNER인 사용자에게는 소유권을 이전할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_transfer_owner_conflict_when_target_already_owns_active_group(
    client, db_session, logged_in_user
):
    """이미 다른 활성 워크스페이스의 OWNER인 사용자에게는 소유권을 이전할 수 없는지 검증한다."""
    target_data = users[1].copy()
    target_data["password"] = auth_service.hash_password(target_data["password"])
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.add(
        Group(
            id=2,
            owner_user_id=target.id,
            name=groups[1]["name"],
            description=groups[1]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=2,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/1/members/{target.id}/transfer")
    assert res.status_code == 409
    assert res.json()["code"] == ErrorCode.GROUP_TRANSFER_TARGET_ALREADY_OWNER.code


# UT-GRP-013-06 프리미엄 구독자가 아닌 사용자에게는 소유권을 이전할 수 없다.
@pytest.mark.parametrize("logged_in_user", [users[0]], indirect=True)
def test_transfer_owner_forbidden_for_non_premium_target(
    client, db_session, logged_in_user
):
    """프리미엄 구독자가 아닌 사용자에게는 소유권을 이전할 수 없는지 검증한다."""
    target_data = users[1].copy()
    target_data["password"] = auth_service.hash_password(target_data["password"])
    target = User(**target_data)
    db_session.add(target)
    db_session.flush()

    db_session.add(
        Group(
            id=1,
            owner_user_id=logged_in_user.id,
            name=groups[0]["name"],
            description=groups[0]["description"],
            status=GroupStatus.ACTIVE,
        )
    )
    db_session.flush()

    db_session.add(
        GroupMember(
            user_id=logged_in_user.id,
            group_id=1,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.add(
        GroupMember(
            user_id=target.id,
            group_id=1,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    res = client.post(f"/api/groups/1/members/{target.id}/transfer")
    assert res.status_code == 403
    assert res.json()["code"] == ErrorCode.GROUP_NOT_PREMIUM.code
