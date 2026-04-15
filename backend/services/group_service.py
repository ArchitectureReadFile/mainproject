import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from errors import AppException, ErrorCode
from models.model import (
    DocumentLifecycleStatus,
    Group,
    GroupMember,
    GroupPendingReason,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    NotificationType,
    SubscriptionPlan,
    SubscriptionStatus,
    utc_now_naive,
)
from redis_client import redis_client
from repositories.group_repository import GroupRepository
from schemas.group import (
    GroupDetailResponse,
    GroupSummaryResponse,
    InvitationResponse,
    InvitedMemberResponse,
    MemberListResponse,
    MemberResponse,
    MyGroupsResponse,
)
from services.auth_service import AuthService
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class GroupService:
    def __init__(
        self,
        repository: GroupRepository,
        auth_service: AuthService,
        notification_service: NotificationService,
        db: Session,
    ):
        self.repository = repository
        self.auth_service = auth_service
        self.notification_service = notification_service
        self.db = db
        self._pending_group_rag_actions: list[tuple[int, str]] = []

    def _finalize_group_state_sync(
        self, original_error: Exception | None = None
    ) -> None:
        """접근 시 동기화된 그룹 상태를 확정하고, 원래 예외를 덮어쓰지 않는다."""
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

            if original_error is not None:
                logger.exception(
                    "[group state sync] 상태 동기화 commit 실패. 원래 예외를 유지합니다."
                )
                return

            raise

        try:
            self._flush_group_rag_actions()
        except Exception:
            logger.exception(
                "[group state sync] RAG 후처리 enqueue 실패. 다음 요청 또는 배치에서 재시도합니다."
            )

    def _check_premium(self, user_id: int):
        """프리미엄 플랜 활성 여부를 검사"""
        if not self.auth_service.has_full_workspace_access(user_id):
            raise AppException(ErrorCode.GROUP_NOT_PREMIUM)

    def _check_owner(self, user_id: int, group_id: int) -> Group:
        """사용자가 해당 그룹의 오너인지 검사"""
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.owner_user_id != user_id:
            raise AppException(ErrorCode.GROUP_NOT_OWNER)
        return group

    def _check_owner_or_admin(self, user_id: int, group_id: int):
        """사용자가 해당 그룹의 OWNER 또는 ADMIN인지 검사"""
        member = self.repository.get_active_member(user_id, group_id)
        if not member or member.role not in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ADMIN_OR_OWNER)
        return member

    def _assert_owner_or_admin_member(self, user_id: int, group_id: int) -> GroupMember:
        """사용자가 해당 그룹의 활성 OWNER 또는 ADMIN인지 확인"""
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
        """사용자의 업로드 권한을 검사하고 그룹과 역할을 반환"""
        result = self.repository.get_group_with_role(user_id, group_id)
        if not result:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        group, role = result
        self.assert_group_writable(group)

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
        original_error: Exception | None = None

        try:
            self._assert_group_readable(group)
            return group, role
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

    def assert_reviewer_assignable(
        self, assignee_user_id: int, group_id: int
    ) -> GroupMember:
        """지정된 사용자가 담당 승인자로 지정 가능한지 확인"""
        return self._assert_owner_or_admin_member(assignee_user_id, group_id)

    def assert_review_view_permission(
        self, user_id: int, group_id: int
    ) -> tuple[Group, GroupMember]:
        """사용자가 승인 탭 목록을 조회할 수 있는지 확인한다."""
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        original_error: Exception | None = None

        try:
            self._assert_group_readable(group)
            member = self._assert_owner_or_admin_member(user_id, group_id)
            return group, member
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

    def _get_workspace_access_state(self, user_id: int) -> tuple[bool, object | None]:
        """현재 시각 기준으로 사용자의 워크스페이스 전체 접근 가능 여부를 계산"""
        subscription = self.auth_service.get_effective_subscription(user_id)
        now = utc_now_naive()

        if not subscription or subscription.plan != SubscriptionPlan.PREMIUM:
            return False, subscription

        has_access = subscription.status == SubscriptionStatus.ACTIVE or (
            subscription.status
            in (
                SubscriptionStatus.CANCELED,
                SubscriptionStatus.EXPIRED,
            )
            and subscription.ended_at is not None
            and subscription.ended_at > now
        )
        return has_access, subscription

    def _queue_group_rag_action(self, group_id: int, action: str) -> None:
        """요청 중 발생한 워크스페이스 RAG 후처리를 메모리에 적재한다."""
        item = (group_id, action)
        if item not in self._pending_group_rag_actions:
            self._pending_group_rag_actions.append(item)

    def _flush_group_rag_actions(self) -> None:
        """commit 이후 중복 방지된 RAG 후처리를 비동기 큐에 적재한다."""
        if not self._pending_group_rag_actions:
            return

        pending = self._pending_group_rag_actions[:]
        handled_count = 0

        try:
            for group_id, action in pending:
                opposite_action = "reindex" if action == "deindex" else "deindex"
                redis_client.delete(f"group_rag:{opposite_action}:{group_id}")

                dedupe_key = f"group_rag:{action}:{group_id}"
                acquired = redis_client.set(dedupe_key, "1", nx=True, ex=600)
                if not acquired:
                    handled_count += 1
                    continue

                try:
                    if action == "deindex":
                        self._enqueue_group_rag_deindex(group_id)
                    elif action == "reindex":
                        self._enqueue_group_rag_reindex(group_id)
                except Exception:
                    redis_client.delete(dedupe_key)
                    raise

                handled_count += 1
        finally:
            if handled_count > 0:
                self._pending_group_rag_actions = self._pending_group_rag_actions[
                    handled_count:
                ]

    def _sync_group_state_if_needed(self, group: Group) -> Group:
        """구독 만료 기반 상태만 즉시 보정하고, RAG 후처리는 분리한다."""
        now = utc_now_naive()

        if group.status == GroupStatus.DELETED:
            return group

        if group.pending_reason == GroupPendingReason.OWNER_DELETE_REQUEST:
            return group

        has_access, subscription = self._get_workspace_access_state(group.owner_user_id)

        if has_access:
            if (
                group.status in (GroupStatus.DELETE_PENDING, GroupStatus.BLOCKED)
                and group.pending_reason == GroupPendingReason.SUBSCRIPTION_EXPIRED
            ):
                group.status = GroupStatus.ACTIVE
                group.pending_reason = None
                group.delete_requested_at = None
                group.delete_scheduled_at = None
                self._queue_group_rag_action(group.id, "reindex")
            return group

        if not subscription or subscription.ended_at is None:
            return group

        delete_requested_at = subscription.ended_at
        delete_scheduled_at = subscription.ended_at + timedelta(days=30)

        if delete_scheduled_at <= now:
            changed = not (
                group.status == GroupStatus.BLOCKED
                and group.pending_reason == GroupPendingReason.SUBSCRIPTION_EXPIRED
                and group.delete_requested_at == delete_requested_at
                and group.delete_scheduled_at == delete_scheduled_at
            )
            if changed:
                group.status = GroupStatus.BLOCKED
                group.pending_reason = GroupPendingReason.SUBSCRIPTION_EXPIRED
                group.delete_requested_at = delete_requested_at
                group.delete_scheduled_at = delete_scheduled_at
                self._queue_group_rag_action(group.id, "deindex")
            return group

        changed = not (
            group.status == GroupStatus.DELETE_PENDING
            and group.pending_reason == GroupPendingReason.SUBSCRIPTION_EXPIRED
            and group.delete_requested_at == delete_requested_at
            and group.delete_scheduled_at == delete_scheduled_at
        )
        if changed:
            group.status = GroupStatus.DELETE_PENDING
            group.pending_reason = GroupPendingReason.SUBSCRIPTION_EXPIRED
            group.delete_requested_at = delete_requested_at
            group.delete_scheduled_at = delete_scheduled_at
            self._queue_group_rag_action(group.id, "deindex")

        return group

    def _get_effective_group_state(self, group: Group):
        """저장 상태를 현재 시각 기준 최종 상태로 정리한다."""
        now = utc_now_naive()
        group = self._sync_group_state_if_needed(group)

        if (
            group.status == GroupStatus.DELETE_PENDING
            and group.pending_reason == GroupPendingReason.OWNER_DELETE_REQUEST
            and group.delete_scheduled_at is not None
            and group.delete_scheduled_at <= now
        ):
            return (
                GroupStatus.DELETED,
                GroupPendingReason.OWNER_DELETE_REQUEST,
                group.delete_scheduled_at,
            )

        if group.status in (GroupStatus.DELETE_PENDING, GroupStatus.BLOCKED):
            return (
                group.status,
                group.pending_reason or GroupPendingReason.OWNER_DELETE_REQUEST,
                group.delete_scheduled_at,
            )

        return group.status, None, group.delete_scheduled_at

    def _has_effective_owned_group(self, user_id: int) -> bool:
        """사용자가 현재 시각 기준 ACTIVE 워크스페이스를 소유하는지 확인한다."""
        original_error: Exception | None = None

        try:
            owned_groups = self.repository.get_owned_groups(user_id)
            return any(
                self._get_effective_group_state(group)[0] == GroupStatus.ACTIVE
                for group in owned_groups
            )
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

    def assert_review_permission(self, user_id: int, group_id: int) -> GroupMember:
        """사용자가 해당 그룹에서 문서 승인/반려를 수행할 수 있는지 확인"""
        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self.assert_group_writable(group)
        return self._assert_owner_or_admin_member(user_id, group_id)

    def _to_group_summary_response(
        self,
        group: Group,
        role: MembershipRole,
    ) -> GroupSummaryResponse:
        """그룹 목록 응답 스키마로 변환"""
        status, pending_reason, delete_scheduled_at = self._get_effective_group_state(
            group
        )
        return GroupSummaryResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=status,
            pending_reason=pending_reason,
            my_role=role,
            owner_username=group.owner.username,
            member_count=self.repository.count_member(group.id),
            document_count=self.repository.count_document(group.id),
            delete_scheduled_at=delete_scheduled_at,
            created_at=group.created_at,
        )

    def _to_group_detail_response(
        self,
        group: Group,
        role: MembershipRole,
    ) -> GroupDetailResponse:
        """그룹 상세 응답 스키마로 변환"""
        status, pending_reason, delete_scheduled_at = self._get_effective_group_state(
            group
        )
        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            status=status,
            pending_reason=pending_reason,
            my_role=role,
            owner_id=group.owner_user_id,
            owner_username=group.owner.username,
            member_count=self.repository.count_member(group.id),
            document_count=self.repository.count_document(group.id),
            delete_scheduled_at=delete_scheduled_at,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def _assert_group_readable(self, group: Group) -> None:
        """그룹 조회 가능 여부를 현재 시각 기준 상태로 검사"""
        status, _, _ = self._get_effective_group_state(group)
        if status not in (
            GroupStatus.ACTIVE,
            GroupStatus.DELETE_PENDING,
        ):
            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)

    def assert_group_writable(self, group: Group) -> None:
        """그룹 쓰기 가능 여부를 현재 시각 기준 상태로 검사한다."""
        original_error: Exception | None = None

        try:
            status, _, _ = self._get_effective_group_state(group)
            if status != GroupStatus.ACTIVE:
                raise AppException(ErrorCode.GROUP_NOT_ACTIVE)
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

    def _assert_group_recoverable(self, group: Group) -> None:
        """그룹 복구 및 오너 양도 가능 여부를 현재 시각 기준 상태로 검사한다."""
        original_error: Exception | None = None

        try:
            status, pending_reason, _ = self._get_effective_group_state(group)

            if status == GroupStatus.ACTIVE:
                return

            if status == GroupStatus.DELETE_PENDING:
                return

            if (
                status == GroupStatus.BLOCKED
                and pending_reason == GroupPendingReason.SUBSCRIPTION_EXPIRED
            ):
                return

            raise AppException(ErrorCode.GROUP_NOT_ACTIVE)
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

    def _enqueue_group_rag_deindex(self, group_id: int) -> None:
        """워크스페이스의 활성 승인 문서를 RAG 제거 큐에 적재한다."""
        from tasks.group_document_task import deindex_document

        group = self.repository.get_group_by_id(group_id)
        expected_group_status = group.status.value if group else None

        document_ids = self.repository.get_active_approved_document_ids(group_id)
        for document_id in document_ids:
            deindex_document.delay(document_id, None, expected_group_status)

    def _enqueue_group_rag_reindex(self, group_id: int) -> None:
        """복구된 워크스페이스의 활성 승인 문서를 재인덱싱 큐에 적재한다."""
        from tasks.group_document_task import index_approved_document

        document_ids = self.repository.get_active_approved_document_ids(group_id)
        for document_id in document_ids:
            index_approved_document.delay(
                document_id,
                DocumentLifecycleStatus.ACTIVE.value,
                GroupStatus.ACTIVE.value,
            )

    def _get_unique_notification_user_ids(self, *user_ids: int | None) -> list[int]:
        """알림 대상 사용자 ID 목록에서 빈 값과 중복을 제거한다."""
        result: list[int] = []

        for user_id in user_ids:
            if user_id is None:
                continue
            if user_id in result:
                continue
            result.append(user_id)

        return result

    def create_group(
        self, owner_user_id: int, name: str, description: Optional[str]
    ) -> GroupDetailResponse:
        """그룹 생성"""
        self._check_premium(owner_user_id)

        if self._has_effective_owned_group(owner_user_id):
            raise AppException(ErrorCode.GROUP_OWNER_LIMIT)

        group = self.repository.create_group(owner_user_id, name, description)

        self.db.commit()
        self.db.refresh(group)

        return self._to_group_detail_response(
            group=group,
            role=MembershipRole.OWNER,
        )

    def get_my_groups(self, user_id: int) -> MyGroupsResponse:
        """내가 속한 그룹 목록을 현재 시각 기준 상태로 반환한다."""
        rows = self.repository.get_my_groups(user_id)
        result: list[GroupSummaryResponse] = []
        has_blocked_owned_group = False
        blocked_owned_group_reason: GroupPendingReason | None = None

        for group, role in rows:
            status, pending_reason, _ = self._get_effective_group_state(group)

            if status == GroupStatus.BLOCKED:
                if role == MembershipRole.OWNER:
                    has_blocked_owned_group = True
                    blocked_owned_group_reason = pending_reason
                continue

            result.append(
                self._to_group_summary_response(
                    group=group,
                    role=role,
                )
            )

        self._finalize_group_state_sync()

        return MyGroupsResponse(
            groups=result,
            has_blocked_owned_group=has_blocked_owned_group,
            blocked_owned_group_reason=blocked_owned_group_reason,
        )

    def get_group_detail(self, user_id: int, group_id: int) -> GroupDetailResponse:
        """그룹 상세 정보를 반환한다."""
        group, role = self.assert_view_permission(user_id, group_id)

        return self._to_group_detail_response(
            group=group,
            role=role,
        )

    def request_delete_group(self, user_id: int, group_id: int):
        """그룹 삭제를 요청한다."""
        group = self._check_owner(user_id, group_id)
        original_error: Exception | None = None

        try:
            status, _, _ = self._get_effective_group_state(group)

            if status != GroupStatus.ACTIVE:
                raise AppException(ErrorCode.GROUP_ALREADY_DELETE_PENDING)
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

        group = self.repository.request_delete_group(
            group,
            reason=GroupPendingReason.OWNER_DELETE_REQUEST,
        )

        active_members = self.repository.get_members(group_id)

        for _, user in active_members:
            if user.id == user_id:
                continue
            self.notification_service.create_notification_sync(
                user_id=user.id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_DELETE_NOTICE,
                title=f"'{group.name}' 워크스페이스 삭제 알림",
                body=f"워크스페이스 '{group.name}'이 소유자에 의해 삭제 요청되었습니다. 삭제 예정일: {group.delete_scheduled_at}",
                target_type="group",
                target_id=group_id,
            )

        self._queue_group_rag_action(group_id, "deindex")
        self._finalize_group_state_sync()

        return self._to_group_detail_response(
            group=group,
            role=MembershipRole.OWNER,
        )

    def cancel_delete_group(self, user_id: int, group_id: int) -> GroupDetailResponse:
        """그룹 삭제 요청을 취소한다."""
        group = self._check_owner(user_id, group_id)
        original_error: Exception | None = None

        try:
            status, pending_reason, _ = self._get_effective_group_state(group)

            if status != GroupStatus.DELETE_PENDING or pending_reason not in (
                None,
                GroupPendingReason.OWNER_DELETE_REQUEST,
            ):
                raise AppException(ErrorCode.GROUP_NOT_DELETE_PENDING)

            if self._has_effective_owned_group(user_id):
                raise AppException(ErrorCode.GROUP_RESTORE_OWNER_LIMIT)
        except Exception as exc:
            original_error = exc
            raise
        finally:
            self._finalize_group_state_sync(original_error)

        group = self.repository.cancel_delete_group(group)

        active_members = self.repository.get_members(group_id)

        for _, user in active_members:
            if user.id == user_id:
                continue

            self.notification_service.create_notification_sync(
                user_id=user.id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_STATUS_UPDATE,
                title="워크스페이스 삭제 취소 알림",
                body=f"'{group.name}' 워크스페이스 삭제 요청이 취소되었습니다. 다시 정상적으로 이용할 수 있습니다.",
                target_type="group",
                target_id=group_id,
            )

        self._queue_group_rag_action(group_id, "reindex")
        self._finalize_group_state_sync()

        return self._to_group_detail_response(
            group=group,
            role=MembershipRole.OWNER,
        )

    def get_members(self, user_id: int, group_id: int) -> MemberListResponse:
        """멤버 목록 조회"""
        group, _ = self.assert_view_permission(user_id, group_id)

        active_rows = self.repository.get_members(group_id)
        invited_rows = self.repository.get_invited_members(group_id)

        members = [
            MemberResponse(
                user_id=member.user_id,
                email=user.email,
                username=user.username,
                role=member.role,
                joined_at=member.joined_at,
                is_premium=self.auth_service.has_full_workspace_access(user.id),
                has_owned_group=self._has_effective_owned_group(user.id),
                is_active=user.is_active,
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
        """내 초대 목록 조회"""
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

    def invite_member(
        self, group_id: int, inviter_id: int, username: str, role: MembershipRole
    ) -> InvitedMemberResponse:
        """멤버 초대"""
        self._check_owner_or_admin(inviter_id, group_id)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self.assert_group_writable(group)

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

        self.notification_service.create_notification_sync(
            user_id=target.id,
            actor_user_id=inviter_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_INVITED,
            title=f"'{group.name}' 워크스페이스에 초대되었습니다.",
            body=f"{group.owner.username}님이 귀하를 '{group.name}' 워크스페이스에 초대했습니다.",
            target_type="group",
            target_id=group_id,
        )

        response = InvitedMemberResponse(
            user_id=target.id,
            username=target.username,
            role=membership.role,
            invited_at=membership.invited_at,
        )
        self.db.commit()
        return response

    def accept_invite(self, user_id: int, group_id: int) -> None:
        """초대 수락"""
        membership = self.repository.get_invited_member(user_id, group_id)

        if not membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self.assert_group_writable(group)

        invited_user = self.repository.get_user_by_id(user_id)
        invited_by_user_id = membership.invited_by_user_id

        self.repository.accept_invite(membership)

        notification_user_ids = self._get_unique_notification_user_ids(
            invited_by_user_id,
            group.owner_user_id,
        )

        for notification_user_id in notification_user_ids:
            if notification_user_id == user_id:
                continue

            self.notification_service.create_notification_sync(
                user_id=notification_user_id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_MEMBER_UPDATE,
                title="워크스페이스 초대 수락 알림",
                body=f"{invited_user.username}님이 '{group.name}' 워크스페이스 초대를 수락했습니다.",
                target_type="group",
                target_id=group_id,
            )

        self.db.commit()

    def decline_invite(self, user_id: int, group_id: int) -> None:
        """초대 거절"""
        membership = self.repository.get_invited_member(user_id, group_id)

        if not membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        invited_user = self.repository.get_user_by_id(user_id)
        invited_by_user_id = membership.invited_by_user_id

        self.repository.decline_invite(membership)

        notification_user_ids = self._get_unique_notification_user_ids(
            invited_by_user_id,
            group.owner_user_id,
        )

        for notification_user_id in notification_user_ids:
            if notification_user_id == user_id:
                continue

            self.notification_service.create_notification_sync(
                user_id=notification_user_id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_MEMBER_UPDATE,
                title="워크스페이스 초대 거절 알림",
                body=f"{invited_user.username}님이 '{group.name}' 워크스페이스 초대를 거절했습니다.",
                target_type="group",
                target_id=group_id,
            )

        self.db.commit()

    def remove_member(self, target_id: int, group_id: int, remover_id: int) -> None:
        """활성 멤버를 추방하거나 초대 대기 멤버의 초대를 취소"""
        remover = self._check_owner_or_admin(remover_id, group_id)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self.assert_group_writable(group)

        if remover_id == target_id:
            raise AppException(ErrorCode.GROUP_CANNOT_REMOVE_SELF)

        is_invited_member = False
        target_membership = self.repository.get_active_member(target_id, group_id)

        if not target_membership:
            target_membership = self.repository.get_invited_member(target_id, group_id)
            is_invited_member = target_membership is not None

        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_CANNOT_REMOVE_OWNER)
        elif (
            target_membership.role == MembershipRole.ADMIN
            and remover.role == MembershipRole.ADMIN
        ):
            raise AppException(ErrorCode.GROUP_NOT_OWNER)

        if is_invited_member:
            self.repository.decline_invite(target_membership)

            self.notification_service.create_notification_sync(
                user_id=target_id,
                actor_user_id=remover_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_MEMBER_UPDATE,
                title="워크스페이스 초대 취소 알림",
                body=f"'{group.name}' 워크스페이스 초대가 취소되었습니다.",
                target_type="group",
                target_id=group_id,
            )

            self.db.commit()
            return

        self.repository.remove_member(target_membership)

        self.notification_service.create_notification_sync(
            user_id=target_id,
            actor_user_id=remover_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_KICKED,
            title="워크스페이스 추방 알림",
            body=f"'{group.name}' 워크스페이스에서 추방되었습니다.",
            target_type="group",
            target_id=group_id,
        )
        self.db.commit()

    def change_member_role(
        self, changer_id: int, target_id: int, group_id: int, role: MembershipRole
    ) -> None:
        """멤버 권한 변경"""
        changer = self._check_owner_or_admin(changer_id, group_id)

        group = self.repository.get_group_by_id(group_id)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)

        self.assert_group_writable(group)

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

        self.notification_service.create_notification_sync(
            user_id=target_id,
            actor_user_id=changer_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_MEMBER_UPDATE,
            title="워크스페이스 권한 변경 알림",
            body=f"'{group.name}' 워크스페이스 권한이 {role.value}(으)로 변경되었습니다.",
            target_type="group",
            target_id=group_id,
        )

        self.db.commit()

    def transfer_owner(self, user_id: int, group_id: int, target_id: int) -> None:
        """워크스페이스 오너를 양도"""
        group = self._check_owner(user_id, group_id)
        self._assert_group_recoverable(group)

        if user_id == target_id:
            raise AppException(ErrorCode.GROUP_TRANSFER_TO_SELF)

        target_membership = self.repository.get_active_member(target_id, group_id)
        if not target_membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        if target_membership.role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_MEMBER_ALREADY_EXISTS)

        if self._has_effective_owned_group(target_id):
            raise AppException(ErrorCode.GROUP_TRANSFER_TARGET_ALREADY_OWNER)

        if not self.auth_service.has_full_workspace_access(target_id):
            raise AppException(ErrorCode.GROUP_NOT_PREMIUM)

        self.repository.transfer_owner(group, user_id, target_id)

        self.notification_service.create_notification_sync(
            user_id=user_id,
            actor_user_id=user_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_MEMBER_UPDATE,
            title="워크스페이스 오너 양도 알림",
            body=f"'{group.name}' 워크스페이스 오너 권한을 양도했습니다. 이제 ADMIN 권한으로 참여합니다.",
            target_type="group",
            target_id=group_id,
        )

        self.notification_service.create_notification_sync(
            user_id=target_id,
            actor_user_id=user_id,
            group_id=group_id,
            type=NotificationType.WORKSPACE_MEMBER_UPDATE,
            title="워크스페이스 오너 양도 알림",
            body=f"'{group.name}' 워크스페이스의 새 OWNER가 되었습니다.",
            target_type="group",
            target_id=group_id,
        )

        self.db.commit()

    def leave_group(self, user_id: int, group_id: int) -> None:
        """현재 사용자가 OWNER가 아닌 경우 워크스페이스를 탈퇴"""
        group, role = self.assert_view_permission(user_id, group_id)

        if role == MembershipRole.OWNER:
            raise AppException(ErrorCode.GROUP_OWNER_CANNOT_LEAVE)

        membership = self.repository.get_active_member(user_id, group_id)
        if not membership:
            raise AppException(ErrorCode.GROUP_MEMBER_NOT_FOUND)

        leaving_user = self.repository.get_user_by_id(user_id)
        active_members = self.repository.get_members(group_id)

        self.repository.remove_member(membership)

        for member, user in active_members:
            if user.id == user_id:
                continue

            if member.role not in (
                MembershipRole.OWNER,
                MembershipRole.ADMIN,
            ):
                continue

            self.notification_service.create_notification_sync(
                user_id=user.id,
                actor_user_id=user_id,
                group_id=group_id,
                type=NotificationType.WORKSPACE_MEMBER_UPDATE,
                title="워크스페이스 멤버 탈퇴 알림",
                body=f"{leaving_user.username}님이 '{group.name}' 워크스페이스에서 탈퇴했습니다.",
                target_type="group",
                target_id=group_id,
            )

        self.db.commit()
