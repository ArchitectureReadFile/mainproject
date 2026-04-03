from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager

from models.model import (
    Document,
    DocumentLifecycleStatus,
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    utc_now_naive,
)


class GroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_group(
        self, owner_user_id: int, name: str, description: Optional[str]
    ) -> Group:
        """그룹 생성"""
        group = Group(
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            status=GroupStatus.ACTIVE,
        )
        self.db.add(group)
        self.db.flush()

        membership = GroupMember(
            user_id=owner_user_id,
            group_id=group.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
            joined_at=utc_now_naive(),
        )
        self.db.add(membership)

        return group

    def get_group_by_id(self, group_id: int) -> Optional[Group]:
        """그룹 단순 조회 (권한 체크 x)"""
        return (
            self.db.query(Group)
            .join(Group.owner)
            .filter(Group.id == group_id)
            .options(contains_eager(Group.owner))
            .first()
        )

    def get_my_groups(self, user_id: int) -> list[tuple[Group, MembershipRole]]:
        """내가 속한 그룹 목록 조회"""
        return (
            self.db.query(Group, GroupMember.role)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .join(Group.owner)
            .filter(
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.ACTIVE,
                Group.status != GroupStatus.DELETED,
            )
            .options(contains_eager(Group.owner))
            .order_by(Group.created_at.desc())
            .all()
        )

    def get_group_with_role(
        self, user_id: int, group_id: int
    ) -> Optional[tuple[Group, MembershipRole]]:
        """그룹 상세 조회"""
        return (
            self.db.query(Group, GroupMember.role)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .join(Group.owner)
            .filter(
                Group.id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.ACTIVE,
            )
            .options(contains_eager(Group.owner))
            .first()
        )

    def count_active_owner_groups(self, user_id: int) -> int:
        """유저가 OWNER인 ACTIVE 그룹 수 (1개 제한 검사용)"""
        return (
            self.db.query(func.count(GroupMember.id))
            .join(Group, Group.id == GroupMember.group_id)
            .join(Group.owner)
            .filter(
                GroupMember.user_id == user_id,
                GroupMember.role == MembershipRole.OWNER,
                GroupMember.status == MembershipStatus.ACTIVE,
                Group.status == GroupStatus.ACTIVE,
            )
            .scalar()
        )

    def count_member(self, group_id: int) -> int:
        return (
            self.db.query(func.count(GroupMember.user_id))
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.status == MembershipStatus.ACTIVE,
            )
            .scalar()
            or 0
        )

    def count_document(self, group_id: int) -> int:
        return (
            self.db.query(func.count(Document.id))
            .filter(
                Document.group_id == group_id,
                Document.lifecycle_status == DocumentLifecycleStatus.ACTIVE,
            )
            .scalar()
            or 0
        )

    def get_owned_groups(self, user_id: int) -> list[Group]:
        """사용자가 소유한 삭제 전 워크스페이스 목록 조회"""
        return (
            self.db.query(Group)
            .filter(
                Group.owner_user_id == user_id,
                Group.status != GroupStatus.DELETED,
            )
            .all()
        )

    def request_delete_group(
        self,
        group: Group,
        reason: GroupPendingReason = GroupPendingReason.OWNER_DELETE_REQUEST,
        requested_at=None,
    ) -> Group:
        """그룹을 삭제 대기 상태로 전환"""
        base_time = requested_at or utc_now_naive()
        group.status = GroupStatus.DELETE_PENDING
        group.pending_reason = reason
        group.delete_requested_at = base_time
        group.delete_scheduled_at = base_time + timedelta(days=30)

        return group

    def cancel_delete_group(self, group: Group) -> Group:
        """그룹 삭제 대기를 취소하고 활성 상태로 복구"""
        group.status = GroupStatus.ACTIVE
        group.pending_reason = None
        group.delete_requested_at = None
        group.delete_scheduled_at = None

        return group

    def get_members(self, group_id: int) -> list[tuple[GroupMember, User]]:
        """ACTIVE 멤버 목록 조회(유저 정보 포함)"""
        return (
            self.db.query(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.status == MembershipStatus.ACTIVE,
            )
            .order_by(GroupMember.joined_at.asc())
            .all()
        )

    def get_active_member(self, user_id: int, group_id: int) -> Optional[GroupMember]:
        """ACTIVE 멤버만 단건 조회 (권한 체크용)"""
        return (
            self.db.query(GroupMember)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.ACTIVE,
            )
            .first()
        )

    def get_invited_members(self, group_id: int) -> list[tuple[GroupMember, User]]:
        """INVITED 멤버 목록 조회(유저 정보 포함)"""
        return (
            self.db.query(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.status == MembershipStatus.INVITED,
            )
            .order_by(GroupMember.joined_at.asc())
            .all()
        )

    def get_invited_member(self, user_id: int, group_id: int) -> Optional[GroupMember]:
        """INVITED 멤버 단건 조회"""
        return (
            self.db.query(GroupMember)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.INVITED,
            )
            .first()
        )

    def invite_member(
        self, user_id: int, group_id: int, inviter_id: int, role: MembershipRole
    ) -> GroupMember:
        """멤버 추가"""
        membership = GroupMember(
            user_id=user_id,
            group_id=group_id,
            role=role,
            status=MembershipStatus.INVITED,
            invited_by_user_id=inviter_id,
            invited_at=utc_now_naive(),
            joined_at=None,
        )
        self.db.add(membership)
        return membership

    def get_my_invitations(self, user_id: int) -> list[tuple[GroupMember, Group]]:
        """내가 INVITED 상태인 멤버십 목록"""
        return (
            self.db.query(GroupMember, Group)
            .join(Group, Group.id == GroupMember.group_id)
            .join(Group.owner)
            .filter(
                GroupMember.user_id == user_id,
                GroupMember.status == MembershipStatus.INVITED,
                Group.status == GroupStatus.ACTIVE,
            )
            .options(contains_eager(Group.owner))
            .all()
        )

    def accept_invite(self, membership: GroupMember) -> GroupMember:
        """초대 수락"""
        membership.status = MembershipStatus.ACTIVE
        membership.joined_at = utc_now_naive()
        return membership

    def decline_invite(self, membership: GroupMember) -> None:
        """초대 거절"""
        membership.status = MembershipStatus.REMOVED
        membership.removed_at = utc_now_naive()

    def is_premium(self, user_id: int) -> bool:
        """프리미엄 플랜 체크"""
        sub = (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.plan == SubscriptionPlan.PREMIUM,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .first()
        )
        return sub is not None

    def remove_member(self, membership: GroupMember) -> None:
        """멤버 삭제"""
        membership.status = MembershipStatus.REMOVED
        membership.removed_at = utc_now_naive()

    def change_member_role(
        self, membership: GroupMember, role: MembershipRole
    ) -> GroupMember:
        """권한 변경"""
        membership.role = role
        return membership

    def get_user_by_username(self, username: str) -> Optional[User]:
        """유저명으로 유저 조회"""
        return self.db.query(User).filter(User.username == username).first()

    def get_member_any_status(
        self, user_id: int, group_id: int
    ) -> Optional[GroupMember]:
        """REMOVED 포함 모든 상태의 멤버십 조회 (재초대)"""
        return (
            self.db.query(GroupMember)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
            .first()
        )

    def transfer_owner(
        self, group: Group, old_owner_id: int, new_owner_id: int
    ) -> None:
        locked_group = (
            self.db.query(Group).filter(Group.id == group.id).with_for_update().first()
        )

        if not locked_group:
            raise RuntimeError("transfer_owner: group not found")

        new_member = self.get_active_member(new_owner_id, locked_group.id)
        old_member = self.get_active_member(old_owner_id, locked_group.id)

        if not new_member or not old_member:
            raise RuntimeError("transfer_owner: membership not found")

        new_member.role = MembershipRole.OWNER
        old_member.role = MembershipRole.ADMIN

        locked_group.owner_user_id = new_owner_id

    def exists_active_owned_group(self, user_id: int) -> bool:
        return (
            self.db.query(Group)
            .filter(Group.owner_user_id == user_id, Group.status == GroupStatus.ACTIVE)
            .first()
            is not None
        )
