from typing import Optional

from errors import AppException, ErrorCode
from models.model import MembershipRole, Subscription, SubscriptionPlan
from repositories.group_repository import GroupRepository
from schemas.group import GroupDetailResponse, GroupSummaryResponse


class GroupService:
    def __init__(self, repository: GroupRepository):
        self.repository = repository

    def _check_premium(self, user_id: int):
        sub = (
            self.repository.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .first()
        )

        if not sub or sub.plan != SubscriptionPlan.PREMIUM:
            raise AppException(ErrorCode.GROUP_NOT_PREMIUM)

    # 그룹 생성
    def create_group(
        self, owner_user_id: int, name: str, description: Optional[str]
    ) -> GroupDetailResponse:
        self._check_premium(owner_user_id)

        if self.repository.count_active_owner_groups(owner_user_id) >= 1:
            raise AppException(ErrorCode.GROUP_OWNER_LIMIT)

        group = self.repository.create_group(owner_user_id, name, description)

        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=group.status.value,
            my_role=MembershipRole.OWNER.value,
            owner_id=group.owner_user_id,
            owner_username=group.owner.username,
            member_count=1,
            document_count=0,
            delete_scheduled_at=group.delete_scheduled_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    # 내 목록 조회
    def get_my_groups(self, user_id: int) -> list[GroupSummaryResponse]:
        rows = self.repository.get_my_groups(user_id)

        return [
            GroupSummaryResponse(
                id=group.id,
                name=group.name,
                description=group.description,
                status=group.status.value,
                my_role=role.value,
                owner_username=group.owner.username,
                member_count=self.repository.count_member(group.id),
                document_count=self.repository.count_document(group.id),
                delete_scheduled_at=group.delete_scheduled_at,
                created_at=group.created_at,
            )
            for group, role in rows
        ]

    # 상세 조회
    def get_group_detail(self, user_id: int, group_id: int) -> GroupDetailResponse:
        result = self.repository.get_group_with_role(user_id, group_id)
        if not result:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group, role = result

        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=group.status.value,
            my_role=role.value,
            owner_id=group.owner_user_id,
            owner_username=group.owner.username,
            member_count=self.repository.count_member(group.id),
            document_count=self.repository.count_document(group.id),
            delete_scheduled_at=group.delete_scheduled_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
