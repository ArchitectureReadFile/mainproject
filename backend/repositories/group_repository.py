from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager

from models.model import (
    Document,
    DocumentLifecycleStatus,
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
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
