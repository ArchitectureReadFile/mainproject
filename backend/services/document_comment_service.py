from errors import AppException, ErrorCode
from models.model import MembershipRole, MembershipStatus
from repositories.document_comment_repository import DocumentCommentRepository
from repositories.group_repository import GroupRepository
from schemas.comment import (
    DocumentCommentAuthorResponse,
    DocumentCommentListResponse,
    DocumentCommentMentionRequest,
    DocumentCommentMentionResponse,
    DocumentCommentResponse,
)
from services.document_service import DocumentService


class DocumentCommentService:
    def __init__(
        self,
        comment_repository: DocumentCommentRepository,
        document_service: DocumentService,
        group_repository: GroupRepository,
    ):
        self.comment_repository = comment_repository
        self.document_service = document_service
        self.group_repository = group_repository

    @staticmethod
    def _build_user_display_name(
        user,
        member_status: MembershipStatus | None = None,
    ) -> str | None:
        if not user:
            return None
        is_deactivated = user.is_active is False
        is_removed_member = member_status == MembershipStatus.REMOVED
        return (
            f"{user.username}(탈퇴)"
            if is_deactivated or is_removed_member
            else user.username
        )

    def _build_author_response(
        self, comment, member_status_map: dict[int, MembershipStatus]
    ) -> DocumentCommentAuthorResponse | None:
        if not getattr(comment, "author", None):
            return None
        member_status = member_status_map.get(comment.author.id)
        return DocumentCommentAuthorResponse(
            id=comment.author.id,
            username=self._build_user_display_name(comment.author, member_status),
            is_active=comment.author.is_active,
        )

    def _build_mentions_response(
        self, comment, member_status_map: dict[int, MembershipStatus]
    ) -> list[DocumentCommentMentionResponse]:
        mentions = sorted(
            getattr(comment, "mentions", []),
            key=lambda item: (item.start_index, item.end_index, item.id),
        )
        return [
            DocumentCommentMentionResponse(
                user_id=mention.mentioned_user_id,
                snapshot_username=mention.snapshot_username,
                current_username=(
                    self._build_user_display_name(
                        mention.mentioned_user,
                        member_status_map.get(mention.mentioned_user.id)
                        if getattr(mention, "mentioned_user", None)
                        else None,
                    )
                    if getattr(mention, "mentioned_user", None)
                    else None
                ),
                start=mention.start_index,
                end=mention.end_index,
            )
            for mention in mentions
        ]

    def _collect_comment_user_ids(self, comments) -> list[int]:
        collected: set[int] = set()

        def walk(comment):
            if getattr(comment, "author_user_id", None):
                collected.add(comment.author_user_id)
            for mention in getattr(comment, "mentions", []):
                if getattr(mention, "mentioned_user_id", None):
                    collected.add(mention.mentioned_user_id)
            for reply in getattr(comment, "replies", []):
                walk(reply)

        for comment in comments:
            walk(comment)
        return list(collected)

    def _build_comment_response(
        self, comment, member_status_map: dict[int, MembershipStatus]
    ) -> DocumentCommentResponse:
        is_deleted = comment.deleted_at is not None
        display_content = "삭제된 댓글입니다." if is_deleted else comment.content
        sorted_replies = sorted(
            comment.replies, key=lambda item: (item.created_at, item.id)
        )
        return DocumentCommentResponse(
            id=comment.id,
            document_id=comment.document_id,
            parent_id=comment.parent_id,
            content=display_content,
            scope=comment.comment_scope,
            is_deleted=is_deleted,
            page=None if is_deleted else comment.page,
            x=None if is_deleted else comment.x,
            y=None if is_deleted else comment.y,
            author=self._build_author_response(comment, member_status_map),
            can_delete=False,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deleted_at=comment.deleted_at,
            mentions=[]
            if is_deleted
            else self._build_mentions_response(comment, member_status_map),
            replies=[
                self._build_comment_response(reply, member_status_map)
                for reply in sorted_replies
            ],
        )

    def _validate_and_normalize_mentions(
        self,
        *,
        group_id: int,
        content: str,
        mentions: list[DocumentCommentMentionRequest],
    ) -> list[dict]:
        if not mentions:
            return []

        ordered_mentions = sorted(
            mentions, key=lambda item: (item.start, item.end, item.user_id)
        )
        previous_end = -1
        mentioned_user_ids = sorted({mention.user_id for mention in ordered_mentions})
        users = self.group_repository.get_active_users_by_ids(
            group_id=group_id, user_ids=mentioned_user_ids
        )
        user_map = {user.id: user for user in users}
        normalized_mentions: list[dict] = []

        for mention in ordered_mentions:
            if mention.start < previous_end:
                raise AppException(ErrorCode.COMMENT_MENTION_INVALID)
            if mention.end > len(content):
                raise AppException(ErrorCode.COMMENT_MENTION_INVALID)
            user = user_map.get(mention.user_id)
            if not user:
                raise AppException(ErrorCode.COMMENT_MENTION_USER_NOT_FOUND)
            if content[mention.start : mention.end] != f"@{mention.snapshot_username}":
                raise AppException(ErrorCode.COMMENT_MENTION_INVALID)
            normalized_mentions.append(
                {
                    "mentioned_user_id": user.id,
                    "snapshot_username": mention.snapshot_username,
                    "start_index": mention.start,
                    "end_index": mention.end,
                }
            )
            previous_end = mention.end

        return normalized_mentions

    def _apply_delete_permission_recursively(
        self,
        response: DocumentCommentResponse,
        comment,
        *,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> DocumentCommentResponse:
        is_owner_or_admin = current_user_role in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
        is_author = comment.author_user_id == current_user_id
        response.can_delete = (not response.is_deleted) and (
            is_owner_or_admin or is_author
        )
        sorted_replies = sorted(
            comment.replies, key=lambda item: (item.created_at, item.id)
        )
        response.replies = [
            self._apply_delete_permission_recursively(
                reply_response,
                reply_comment,
                current_user_id=current_user_id,
                current_user_role=current_user_role,
            )
            for reply_response, reply_comment in zip(response.replies, sorted_replies)
        ]
        return response

    def list_comments(
        self,
        *,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
        scope: str,
    ) -> DocumentCommentListResponse:
        self.document_service.get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )
        comments = self.comment_repository.get_root_comments_by_document_id(
            doc_id, scope=scope
        )
        member_status_map = self.group_repository.get_member_status_map(
            group_id=group_id, user_ids=self._collect_comment_user_ids(comments)
        )
        items = [
            self._apply_delete_permission_recursively(
                self._build_comment_response(comment, member_status_map),
                comment,
                current_user_id=current_user_id,
                current_user_role=current_user_role,
            )
            for comment in comments
        ]
        return DocumentCommentListResponse(items=items)

    def create_comment(
        self,
        *,
        doc_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
        content: str,
        parent_id: int | None = None,
        page: int | None = None,
        x: float | None = None,
        y: float | None = None,
        scope: str = "GENERAL",
        mentions: list[DocumentCommentMentionRequest] | None = None,
    ) -> DocumentCommentResponse:
        self.document_service.get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        if parent_id is not None:
            parent_comment = self.comment_repository.get_comment_by_id(parent_id)
            if not parent_comment:
                raise AppException(ErrorCode.COMMENT_NOT_FOUND)
            if parent_comment.document_id != doc_id:
                raise AppException(ErrorCode.COMMENT_PARENT_MISMATCH)
            if parent_comment.parent_id is not None:
                raise AppException(ErrorCode.COMMENT_REPLY_DEPTH_EXCEEDED)
            if parent_comment.deleted_at is not None:
                raise AppException(ErrorCode.COMMENT_PARENT_DELETED)
            if parent_comment.comment_scope != scope:
                raise AppException(ErrorCode.COMMENT_PARENT_MISMATCH)

        normalized_mentions = self._validate_and_normalize_mentions(
            group_id=group_id, content=content, mentions=mentions or []
        )

        try:
            comment = self.comment_repository.create_comment(
                document_id=doc_id,
                author_user_id=current_user_id,
                content=content,
                parent_id=parent_id,
                page=page,
                x=x,
                y=y,
                scope=scope,
            )
            self.comment_repository.create_comment_mentions(
                comment_id=comment.id, mentions=normalized_mentions
            )
            self.comment_repository.db.commit()

            if normalized_mentions:
                from models.model import NotificationType
                from repositories.notification_repository import NotificationRepository
                from services.notification_service import NotificationService

                notification_repo = NotificationRepository(self.comment_repository.db)
                notification_service = NotificationService(notification_repo)  # ✅

                for mention_data in normalized_mentions:
                    mentioned_user_id = mention_data["mentioned_user_id"]
                    if mentioned_user_id == current_user_id:
                        continue

                    page_str = str(page) if page is not None else "1"
                    scope_str = scope.lower() if scope else "general"
                    short_content = (
                        content[:30] + "..." if len(content) > 30 else content
                    )

                    notification_service.create_notification_sync(
                        user_id=mentioned_user_id,  # ✅ repository= 제거
                        type=NotificationType.COMMENT_MENTIONED,
                        title="댓글 멘션 알림",
                        body=f"문서 댓글에서 회원님을 멘션했습니다: {short_content}",
                        actor_user_id=current_user_id,
                        group_id=group_id,
                        target_type=f"doc_comment:{page_str}:{scope_str}",
                        target_id=doc_id,
                    )

        except Exception:
            self.comment_repository.db.rollback()
            raise

        saved_comment = self.comment_repository.get_comment_by_id(comment.id)
        response = self._build_comment_response(saved_comment, {})
        return self._apply_delete_permission_recursively(
            response,
            saved_comment,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

    def delete_comment(
        self,
        *,
        comment_id: int,
        group_id: int,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> DocumentCommentResponse:
        comment = self.comment_repository.get_comment_by_id(comment_id)
        if not comment:
            raise AppException(ErrorCode.COMMENT_NOT_FOUND)

        self.document_service.get_document_in_group_with_permission(
            doc_id=comment.document_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        if comment.deleted_at is not None:
            raise AppException(ErrorCode.COMMENT_ALREADY_DELETED)

        is_owner_or_admin = current_user_role in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
        is_author = comment.author_user_id == current_user_id
        if not (is_owner_or_admin or is_author):
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        try:
            deleted_comment = self.comment_repository.soft_delete_comment(
                comment, deleted_by_user_id=current_user_id
            )
            self.comment_repository.db.commit()
        except Exception:
            self.comment_repository.db.rollback()
            raise

        response = self._build_comment_response(deleted_comment, {})
        return self._apply_delete_permission_recursively(
            response,
            deleted_comment,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )
