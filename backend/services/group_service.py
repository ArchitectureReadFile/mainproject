from typing import Optional

from errors import AppException, ErrorCode
from models.model import Group, GroupStatus, MembershipRole, utc_now_naive
from repositories.group_repository import GroupRepository
from schemas.group import (
    GroupDetailResponse,
    GroupSummaryResponse,
    InvitedMemberResponse,
    MemberListResponse,
    MemberResponse,
    MembershipStatus,
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
        member = self.repository.get_active_member(user_id, group_id)
        if not member or member.role not in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ADMIN_OR_OWNER)
        return member

    def assert_upload_permission(self, user_id: int, group_id: int):
        result = self.repository.get_group_with_role(user_id, group_id)
        if not result:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group, role = result
        if group.status != GroupStatus.ACTIVE:
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)
        if role not in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.EDITOR,
        ):
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        return group, role

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
        group = self._check_owner(user_id, group_id)

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
    def get_members(self, user_id: int, group_id: int) -> MemberListResponse:
        self._check_owner_or_admin(user_id, group_id)

        active_rows = self.repository.get_members(group_id)
        invited_rows = self.repository.get_invited_members(group_id)

        members = [
            MemberResponse(
                user_id=member.user_id,
                email=user.email,
                username=user.username,
                role=member.role,
                joined_at=member.joined_at,
            )
            for member, user in active_rows
        ]

        invited = [
            InvitedMemberResponse(
                user_id=member.user_id,
                username=user.username,
                role=member.role,
                invited_at=member.invited_at,
            )
            for member, user in invited_rows
        ]

        return MemberListResponse(members=members, invited=invited)

    # 멤버 초대
    def invite_member(
        self, group_id: int, inviter_id: int, username: str, role: MembershipRole
    ) -> InvitedMemberResponse:
        self._check_owner_or_admin(inviter_id, group_id)

        group = self.repository.get_group_by_id(group_id)

        if group.status != GroupStatus.ACTIVE:
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

        # 멤버 확인
        target = self.repository.get_user_by_username(username)
        if not target:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        # 본인 초대x
        if target.id == inviter_id:
            raise AppException(ErrorCode.GROUP_CANNOT_INVITE_SELF)

        # 이전 멤버였는지 체크(재초대)
        existing = self.repository.get_member_any_status(target.id, group_id)
        if existing:
            if existing.status == MembershipStatus.ACTIVE:
                raise AppException(ErrorCode.GROUP_MEMBER_ALREADY_EXISTS)
            elif existing.status == MembershipStatus.INVITED:
                raise AppException(ErrorCode.GROUP_MEMBER_ALREADY_EXISTS)

            existing.status = MembershipStatus.INVITED
            existing.role = role
            existing.invited_by_user_id = inviter_id
            existing.invited_at = utc_now_naive()
            existing.joined_at = None
            existing.removed_at = None

            membership = existing
        else:
            membership = self.repository.invite_member(
                target.id, group_id, inviter_id, role
            )

        return InvitedMemberResponse(
            user_id=target.id,
            username=target.username,
            role=membership.role,
            invited_at=membership.invited_at,
        )

    # 초대 수락
    def accept_invite(self, user_id: int, group_id: int) -> None:
        membership = self.repository.get_invited_member(user_id, group_id)

        if not membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        self.repository.accept_invite(membership)

    # 초대 거절
    def decline_invite(self, user_id: int, group_id: int) -> None:
        membership = self.repository.get_invited_member(user_id, group_id)

        if not membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        self.repository.decline_invite(membership)

    # 멤버 삭제
    def remove_member(self, target_id: int, group_id: int, remover_id: int) -> None:
        remover = self._check_owner_or_admin(remover_id, group_id)

        # 본인 추방x
        if remover_id == target_id:
            raise AppException(ErrorCode.GROUP_CANNOT_REMOVE_SELF)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        # 어드민은 오너, 어드민 추방x
        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_CANNOT_REMOVE_OWNER)
        elif (
            target_membership.role == MembershipRole.ADMIN
            and remover.role == MembershipRole.ADMIN
        ):
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        self.repository.remove_member(target_membership)

    # 멤버 권한 변경
    def change_member_role(
        self, changer_id: int, target_id: int, group_id: int, role: MembershipRole
    ) -> None:
        changer = self._check_owner_or_admin(changer_id, group_id)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        # 본인 변경x
        if changer_id == target_id:
            raise AppException(ErrorCode.GROUP_CANNOT_CHANGE_SELF_ROLE)

        # 오너 변경x
        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_CANNOT_CHANGE_OWNER_ROLE)

        # 어드민은 어드민 변경x
        if (
            changer.role == MembershipRole.ADMIN
            and target_membership.role == MembershipRole.ADMIN
        ):
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        # 오너 양도 불가(함수 분리)
        if role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        self.repository.change_member_role(target_membership, role)

    # 오너 양도
    def transfer_owner(self, user_id: int, group_id: int, target_id: int) -> None:
        group = self._check_owner(user_id, group_id)

        # 본인에게 양도 x
        if user_id == target_id:
            raise AppException(ErrorCode.GROUP_TRANSFER_TO_SELF)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        # 양도 대상 프리미엄 체크
        if not self.repository.is_premium(target_id):
            raise AppException(ErrorCode.GROUP_TRANSFER_TARGET_NOT_PREMIUM)

        # 오너 변경
        self.repository.change_member_role(target_membership, MembershipRole.OWNER)

        # 기존 오너 어드민으로 변경
        owner_membership = self.repository.get_active_member(user_id, group_id)
        self.repository.change_member_role(owner_membership, MembershipRole.ADMIN)

        # 그룹 정보 변경
        group.owner_user_id = target_id
