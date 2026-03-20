from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager
from datetime import timedelta

from models.model import (
    Document,
    DocumentLifecycleStatus,
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
    

    def get_group_by_id(self, group_id:int) -> Optional[Group]:
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


    def request_delete_group(self, group: Group) -> Group:
        """그룹 삭제 요청 — DELETE_PENDING으로 변경, 30일 유예"""
        now = utc_now_naive()
        group.status = GroupStatus.DELETE_PENDING
        group.delete_requested_at = now
        group.delete_scheduled_at = now + timedelta(days=30)
        
        return group

    def cancel_delete_group(self, group: Group) -> Group:
        """그룹 삭제 취소 — ACTIVE 복구"""
        group.status = GroupStatus.ACTIVE
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
    

    def add_member(self, user_id: int, group_id: int, inviter_id: int) -> GroupMember:
        """멤버 추가"""
        membership = GroupMember(
            user_id=user_id,
            group_id=group_id,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.INVITED,
            invited_by_user_id=inviter_id,
            invited_at=utc_now_naive(),
            joined_at=None,     
        )
        self.db.add(membership)
        return membership


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


    def change_member_role(self, membership: GroupMember, role: MembershipRole) -> GroupMember:   
        """권한 변경"""
        membership.role = role
        return membership

        