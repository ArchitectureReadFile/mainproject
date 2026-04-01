from typing import Optional

from sqlalchemy.orm import Session

from errors import AppException, ErrorCode
from models.model import (
    Group,
    GroupMember,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    NotificationType,
    utc_now_naive,
)
from repositories.group_repository import GroupRepository
from repositories.notification_repository import NotificationRepository
from schemas.group import (
    GroupDetailResponse,
    GroupSummaryResponse,
    InvitationResponse,
    InvitedMemberResponse,
    MemberListResponse,
    MemberResponse,
)
from services.auth_service import AuthService, SubscriptionAccessLevel
from services.notification_service import NotificationService


class GroupService:
    def __init__(self, repository: GroupRepository, db: Session):
        self.repository = repository
        self.db = db
        self.auth_service = AuthService()

    def _check_premium(self, user_id: int):
        """프리미엄 플랜 활성 여부를 검사한다."""
        if not self.auth_service.is_premium_active(self.db, user_id):
            raise AppException(ErrorCode.GROUP_NOT_PREMIUM)

    def _check_owner(self, user_id: int, group_id: int) -> Group:
        """사용자가 해당 그룹의 오너인지 검사한다."""
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.owner_user_id != user_id:
            raise AppException(ErrorCode.GROUP_NOT_OWNER)
        return group

    def _check_owner_or_admin(self, user_id: int, group_id: int):
        """사용자가 해당 그룹의 OWNER 또는 ADMIN인지 검사한다."""
        member = self.repository.get_active_member(user_id, group_id)
        if not member or member.role not in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ADMIN_OR_OWNER)
        return member

    def _assert_owner_or_admin_member(self, user_id: int, group_id: int) -> GroupMember:
        """사용자가 해당 그룹의 활성 OWNER 또는 ADMIN인지 확인한다."""
        member = self.repository.get_active_member(user_id, group_id)
        if not member:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        if member.role not in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ADMIN_OR_OWNER)

        return member

    def assert_upload_permission(self, user_id: int, group_id: int):
        """사용자의 업로드 권한을 검사하고 그룹과 역할을 반환한다."""
        result = self.repository.get_group_with_role(user_id, group_id)
        if not result:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group, role = result
        self._assert_group_writable(group)

        if group.status != GroupStatus.ACTIVE:
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)
        if role not in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.EDITOR,
        ):
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        return group, role

    def assert_view_permission(
        self, user_id: int, group_id: int
    ) -> tuple[Group, MembershipRole]:
        """사용자의 그룹 조회 권한을 검사하고 그룹과 역할을 반환한다."""
        result = self.repository.get_group_with_role(user_id, group_id)
        if not result:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group, role = result
        self._assert_group_readable(group)

        if group.status not in (
            GroupStatus.ACTIVE,
            GroupStatus.DELETE_PENDING,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

        return group, role

    def assert_reviewer_assignable(
        self, assignee_user_id: int, group_id: int
    ) -> GroupMember:
        """지정된 사용자가 담당 승인자로 지정 가능한지 확인한다."""
        return self._assert_owner_or_admin_member(assignee_user_id, group_id)

    def assert_review_view_permission(
        self, user_id: int, group_id: int
    ) -> tuple[Group, GroupMember]:
        """사용자가 승인 탭의 목록을 조회할 수 있는지 확인한다.

        FULL_ACCESS와 READ_ONLY에서는 조회를 허용하고,
        실제 승인/반려 처리는 별도 권한 검사에서 제한한다.
        """
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self._assert_group_readable(group)

        if group.status not in (
            GroupStatus.ACTIVE,
            GroupStatus.DELETE_PENDING,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

        member = self._assert_owner_or_admin_member(user_id, group_id)
        return group, member

    def assert_review_permission(self, user_id: int, group_id: int) -> GroupMember:
        """사용자가 해당 그룹에서 문서 승인/반려를 수행할 수 있는지 확인한다.

        실제 승인 처리는 FULL_ACCESS에서만 허용한다.
        """
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self._assert_group_writable(group)
        return self._assert_owner_or_admin_member(user_id, group_id)

    def _get_group_owner_access_level(self, group: Group) -> SubscriptionAccessLevel:
        """워크스페이스 owner의 현재 구독 접근 단계를 반환한다."""
        return self.auth_service.get_subscription_access_level(
            self.db, group.owner_user_id
        )

    def _to_group_summary_response(
        self,
        group: Group,
        role: MembershipRole,
        access_level: SubscriptionAccessLevel,
    ) -> GroupSummaryResponse:
        """그룹 목록 응답 스키마로 변환한다."""
        return GroupSummaryResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=group.status.value,
            my_role=role.value,
            owner_username=group.owner.username,
            member_count=self.repository.count_member(group.id),
            document_count=self.repository.count_document(group.id),
            access_level=access_level.value,
            delete_scheduled_at=group.delete_scheduled_at,
            created_at=group.created_at,
        )

    def _to_group_detail_response(
        self,
        group: Group,
        role: MembershipRole,
        access_level: SubscriptionAccessLevel,
    ) -> GroupDetailResponse:
        """그룹 상세 응답 스키마로 변환한다."""
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
            access_level=access_level.value,
            delete_scheduled_at=group.delete_scheduled_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def _assert_group_readable(self, group: Group) -> None:
        """그룹 조회 가능 여부를 검사한다. READ_ONLY까지 허용한다."""
        level = self._get_group_owner_access_level(group)
        if level == SubscriptionAccessLevel.BLOCKED:
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

    def _assert_group_writable(self, group: Group) -> None:
        """그룹 쓰기 가능 여부를 검사한다. FULL_ACCESS만 허용한다."""
        level = self._get_group_owner_access_level(group)
        if level != SubscriptionAccessLevel.FULL_ACCESS:
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

    def _assert_group_recoverable(self, group: Group) -> None:
        """그룹 복구/승계 가능 여부를 검사한다. READ_ONLY까지 허용한다."""
        level = self._get_group_owner_access_level(group)
        if level not in (
            SubscriptionAccessLevel.FULL_ACCESS,
            SubscriptionAccessLevel.READ_ONLY,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

    def create_group(
        self, owner_user_id: int, name: str, description: Optional[str]
    ) -> GroupDetailResponse:
        """그룹을 생성한다."""
        self._check_premium(owner_user_id)

        if self.repository.count_active_owner_groups(owner_user_id) >= 1:
            raise AppException(ErrorCode.GROUP_OWNER_LIMIT)

        group = self.repository.create_group(owner_user_id, name, description)
        access_level = self._get_group_owner_access_level(group)

        return self._to_group_detail_response(
            group=group,
            role=MembershipRole.OWNER,
            access_level=access_level,
        )

    def get_my_groups(self, user_id: int) -> list[GroupSummaryResponse]:
        """내가 속한 그룹 목록을 반환한다."""
        rows = self.repository.get_my_groups(user_id)
        result: list[GroupSummaryResponse] = []

        for group, role in rows:
            access_level = self._get_group_owner_access_level(group)
            if access_level == SubscriptionAccessLevel.BLOCKED:
                continue

            result.append(
                self._to_group_summary_response(
                    group=group,
                    role=role,
                    access_level=access_level,
                )
            )

        return result

    def get_group_detail(self, user_id: int, group_id: int) -> GroupDetailResponse:
        """그룹 상세 정보를 반환한다."""
        result = self.repository.get_group_with_role(user_id, group_id)
        if not result:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group, role = result
        self._assert_group_readable(group)
        access_level = self._get_group_owner_access_level(group)

        return self._to_group_detail_response(
            group=group,
            role=role,
            access_level=access_level,
        )

    def request_delete_group(self, user_id: int, group_id: int):
        """그룹 삭제를 요청한다."""
        group = self._check_owner(user_id, group_id)

        if group.status == GroupStatus.DELETE_PENDING:
            raise AppException(ErrorCode.GROUP_ALREADY_DELETE_PENDING)

        group = self.repository.request_delete_group(group)
        access_level = self._get_group_owner_access_level(group)

        notif_service = NotificationService()
        notif_repo = NotificationRepository(self.repository.db)
        active_members = self.repository.get_members(group_id)

        for _, user in active_members:
            if user.id == user_id:
                continue
            notif_service.create_notification_sync(
                repository=notif_repo,
                user_id=user.id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_DELETE_NOTICE,
                title=f"'{group.name}' 워크스페이스 삭제 알림",
                body=f"워크스페이스 '{group.name}'이 소유자에 의해 삭제 요청되었습니다. 예정일: {group.delete_scheduled_at}",
                target_type="group",
                target_id=group_id,
            )

        return self._to_group_detail_response(
            group=group,
            role=MembershipRole.OWNER,
            access_level=access_level,
        )


    def cancel_delete_group(self, user_id: int, group_id: int) -> GroupDetailResponse:
        """그룹 삭제 요청을 취소한다."""
        group = self._check_owner(user_id, group_id)

        if group.status != GroupStatus.DELETE_PENDING:
            raise AppException(ErrorCode.GROUP_NOT_DELETE_PENDING)

        if self.repository.count_active_owner_groups(user_id) >= 1:
            raise AppException(ErrorCode.GROUP_RESTORE_OWNER_LIMIT)

        group = self.repository.cancel_delete_group(group)
        access_level = self._get_group_owner_access_level(group)

        return self._to_group_detail_response(
            group=group,
            role=MembershipRole.OWNER,
            access_level=access_level,
        )

    def get_members(self, user_id: int, group_id: int) -> MemberListResponse:
        """멤버 목록 조회"""
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self._assert_group_readable(group)

        active_rows = self.repository.get_members(group_id)
        invited_rows = self.repository.get_invited_members(group_id)

        members = [
            MemberResponse(
                user_id=member.user_id,
                email=user.email,
                username=user.username,
                role=member.role,
                joined_at=member.joined_at,
                is_premium=self.repository.is_premium(user.id),
                has_owned_group=self.repository.exists_active_owned_group(user.id),
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

    def get_my_invitations(self, user_id: int) -> list[InvitationResponse]:
        rows = self.repository.get_my_invitations(user_id)

        return [
            InvitationResponse(
                group_id=group.id,
                group_name=group.name,
                owner_username=group.owner.username,
                role=membership.role,
                invited_at=membership.invited_at,
            )
            for membership, group in rows
        ]

    # 멤버 초대
    def invite_member(
        self, group_id: int, inviter_id: int, username: str, role: MembershipRole
    ) -> InvitedMemberResponse:
        self._check_owner_or_admin(inviter_id, group_id)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self._assert_group_writable(group)

        if group.status != GroupStatus.ACTIVE:
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

        target = self.repository.get_user_by_username(username)
        if not target:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        if target.id == inviter_id:
            raise AppException(ErrorCode.GROUP_CANNOT_INVITE_SELF)

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

        notif_service = NotificationService()
        notif_repo = NotificationRepository(self.repository.db)
        notif_service.create_notification_sync(
            repository=notif_repo,
            user_id=target.id,
            actor_user_id=inviter_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_INVITED,
            title=f"'{group.name}' 워크스페이스에 초대되었습니다.",
            body=f"{group.owner.username}님이 귀하를 '{group.name}' 워크스페이스에 초대했습니다.",
            target_type="group",
            target_id=group_id,
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

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self._assert_group_writable(group)

        if remover_id == target_id:
            raise AppException(ErrorCode.GROUP_CANNOT_REMOVE_SELF)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_CANNOT_REMOVE_OWNER)
        elif (
            target_membership.role == MembershipRole.ADMIN
            and remover.role == MembershipRole.ADMIN
        ):
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        self.repository.remove_member(target_membership)

        notif_service = NotificationService()
        notif_repo = NotificationRepository(self.repository.db)
        notif_service.create_notification_sync(
            repository=notif_repo,
            user_id=target_id,
            actor_user_id=remover_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_KICKED,
            title="워크스페이스 추방 알림",
            body=f"'{group.name}' 워크스페이스에서 추방되었습니다.",
            target_type="group",
            target_id=group_id,
        )

    # 멤버 권한 변경
    def change_member_role(
        self, changer_id: int, target_id: int, group_id: int, role: MembershipRole
    ) -> None:
        changer = self._check_owner_or_admin(changer_id, group_id)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self._assert_group_writable(group)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        if changer_id == target_id:
            raise AppException(ErrorCode.GROUP_CANNOT_CHANGE_SELF_ROLE)

        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_CANNOT_CHANGE_OWNER_ROLE)

        if (
            changer.role == MembershipRole.ADMIN
            and target_membership.role == MembershipRole.ADMIN
        ):
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        if role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        self.repository.change_member_role(target_membership, role)

    # 오너 양도
    def transfer_owner(self, user_id: int, group_id: int, target_id: int) -> None:
        group = self._check_owner(user_id, group_id)
        self._assert_group_recoverable(group)

        if user_id == target_id:
            raise AppException(ErrorCode.GROUP_TRANSFER_TO_SELF)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_MEMBER_ALREADY_EXISTS)

        if self.repository.exists_active_owned_group(target_id):
            raise AppException(ErrorCode.GROUP_TRANSFER_TARGET_ALREADY_OWNER)

        target_level = self.auth_service.get_subscription_access_level(
            self.db, target_id
        )
        if target_level != SubscriptionAccessLevel.FULL_ACCESS:
            raise AppException(ErrorCode.GROUP_NOT_PREMIUM)

        self.repository.transfer_owner(group, user_id, target_id)
