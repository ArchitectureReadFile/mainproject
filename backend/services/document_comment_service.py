from errors import AppException, ErrorCode
from models.model import (
    MembershipRole,
)
from repositories.document_comment_repository import DocumentCommentRepository
from schemas.comment import (
    DocumentCommentAuthorResponse,
    DocumentCommentListResponse,
    DocumentCommentResponse,
)
from services.document_service import DocumentService


class DocumentCommentService:
    def __init__(
        self,
        comment_repository: DocumentCommentRepository,
        document_service: DocumentService,
    ):
        self.comment_repository = comment_repository
        self.document_service = document_service

    @staticmethod
    def _build_author_response(comment) -> DocumentCommentAuthorResponse | None:
        """
        댓글 작성자 응답 스키마를 구성합니다.
        """
        if not getattr(comment, "author", None):
            return None

        return DocumentCommentAuthorResponse(
            id=comment.author.id,
            username=comment.author.username,
        )

    def _build_comment_response(self, comment) -> DocumentCommentResponse:
        """
        댓글 엔티티를 API 응답 스키마로 변환합니다.
        soft delete 댓글은 표시용 본문으로 치환합니다.
        """
        is_deleted = comment.deleted_at is not None
        display_content = "삭제된 댓글입니다." if is_deleted else comment.content

        sorted_replies = sorted(
            comment.replies,
            key=lambda item: (item.created_at, item.id),
        )

        return DocumentCommentResponse(
            id=comment.id,
            document_id=comment.document_id,
            parent_id=comment.parent_id,
            content=display_content,
            is_deleted=is_deleted,
            author=self._build_author_response(comment),
            can_delete=False,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deleted_at=comment.deleted_at,
            replies=[self._build_comment_response(reply) for reply in sorted_replies],
        )

    def _apply_delete_permission_recursively(
        self,
        response: DocumentCommentResponse,
        comment,
        *,
        current_user_id: int,
        current_user_role: MembershipRole | None,
    ) -> DocumentCommentResponse:
        """
        댓글 트리 전체에 삭제 권한 정보를 재귀적으로 반영
        """
        is_owner_or_admin = current_user_role in (
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
        is_author = comment.author_user_id == current_user_id

        response.can_delete = (not response.is_deleted) and (
            is_owner_or_admin or is_author
        )

        sorted_replies = sorted(
            comment.replies,
            key=lambda item: (item.created_at, item.id),
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
    ) -> DocumentCommentListResponse:
        """
        문서의 루트 댓글과 대댓글 목록을 반환합니다.
        """
        self.document_service.get_document_in_group_with_permission(
            doc_id=doc_id,
            group_id=group_id,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )

        comments = self.comment_repository.get_root_comments_by_document_id(doc_id)

        items = [
            self._apply_delete_permission_recursively(
                self._build_comment_response(comment),
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
    ) -> DocumentCommentResponse:
        """
        문서 댓글 또는 대댓글을 생성합니다.
        대댓글은 같은 문서의 루트 댓글에만 달 수 있도록 제한합니다.
        """
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

        comment = self.comment_repository.create_comment(
            document_id=doc_id,
            author_user_id=current_user_id,
            content=content,
            parent_id=parent_id,
        )

        saved_comment = self.comment_repository.get_comment_by_id(comment.id)
        response = self._build_comment_response(saved_comment)

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
        """
        댓글을 soft delete 처리합니다.
        OWNER/ADMIN은 전체 삭제 가능, 그 외에는 본인 댓글만 삭제 가능합니다.
        """
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

        deleted_comment = self.comment_repository.soft_delete_comment(
            comment,
            deleted_by_user_id=current_user_id,
        )

        response = self._build_comment_response(deleted_comment)

        return self._apply_delete_permission_recursively(
            response,
            deleted_comment,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
        )
