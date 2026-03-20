from typing import Optional

from errors import AppException, ErrorCode
from models.model import MembershipRole, Group, GroupStatus
from repositories.group_repository import GroupRepository
from schemas.group import (
    GroupDetailResponse,
    GroupSummaryResponse,
    InvitedMemberResponse,
    MemberListResponse,
    MemberResponse,
)

class GroupService:
    def __init__(self, repository: GroupRepository):
        self.repository = repository

    # PREMIUM 플랜 체크
    def _check_premium(self, user_id: int):
        if not self.repository.is_premium(user_id):
            raise AppException(ErrorCode.GROUP_NOT_PREMIUM)

    # OWNER 권한 체크
    def _check_owner(self, user_id: int, group_id: int) -> Group:
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.owner_user_id != user_id:
            raise AppException(ErrorCode.GROUP_NOT_OWNER)
        return group
        
    # OWNER/ADMIN 권한 체크
    def _check_owner_or_admin(self, user_id: int, group_id: int):
        member = self.repository.get_active_member(group_id, user_id)
        if not member or member.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
            raise AppException(ErrorCode.GROUP_NOT_ADMIN_OR_OWNER)
        return member     


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


    # 그룹 삭제
    def request_delete_group(self, user_id: int, group_id: int):
        group = self._check_owner(user_id, group_id)

        if group.status == GroupStatus.DELETE_PENDING:
            raise AppException(ErrorCode.GROUP_ALREADY_DELETE_PENDING)

        group = self.repository.request_delete_group(group)

        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=group.status.value,
            my_role=MembershipRole.OWNER.value,
            owner_id=group.owner_user_id,
            owner_username=group.owner.username,
            member_count=self.repository.count_member(group.id),
            document_count=self.repository.count_document(group.id),
            delete_scheduled_at=group.delete_scheduled_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )


    # 그룹 삭제 취소 
    def cancel_delete_group(self, user_id: int, group_id: int) -> GroupDetailResponse:
        self._check_owner(user_id, group_id)

        if group.status != GroupStatus.DELETE_PENDING:
            raise AppException(ErrorCode.GROUP_NOT_DELETE_PENDING)
        
        if self.repository.count_active_owner_groups(user_id) >= 1:
            raise AppException(ErrorCode.GROUP_RESTORE_OWNER_LIMIT)
        
        group = self.repository.cancel_delete_group(group)

        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=group.status.value,
            my_role=MembershipRole.OWNER.value,
            owner_id=group.owner_user_id,
            owner_username=group.owner.username,
            member_count=self.repository.count_member(group.id),
            document_count=self.repository.count_document(group.id),
            delete_scheduled_at=group.delete_scheduled_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
    
    # 멤버 목록 조회 
    def get_members(self, user_id, group_id):
        if not self.repository.get_active_member(user_id, group_id):
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        if not self._check_owner_or_admin(user_id, group_id):
            raise AppException(ErrorCode.GROUP_NOT_ADMIN_OR_OWNER)
        
        rows = self.repository.get_members(group_id)

        members = [
            MemberResponse(
                

            )
        ]


    # 멤버 초대


    # 수락 거절


    # 멤버 삭제


    # 멤버 권한 변경 


    # 오너 양도

        